"""Command-line entrypoint for pipeline jobs: ``retail-pipeline <command>``."""

import argparse
import logging
import resource
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from retail_pipeline.errors import PipelineError
from retail_pipeline.ingestion.landing import new_batch_id
from retail_pipeline.ingestion.pipeline import ingest_source
from retail_pipeline.lakehouse.bootstrap import bootstrap_lakehouse
from retail_pipeline.lakehouse.catalog import list_table_record_counts, load_lakehouse_catalog
from retail_pipeline.lakehouse.lakekeeper import CreateWarehouseRequest, LakekeeperAdminClient
from retail_pipeline.lakehouse.pyarrow_storage import PyArrowObjectStorage
from retail_pipeline.samples.dunnhumby import write_dunnhumby_sample
from retail_pipeline.settings import LakehouseSettings, ObjectStorageSettings
from retail_pipeline.sources import SOURCE_TABLES

logger = logging.getLogger("retail_pipeline")


def main(argv: Sequence[str] | None = None) -> int:
    """Run a pipeline command and return the process exit code."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        args.handler(args)
    except PipelineError as error:
        logger.error("%s", error)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="retail-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    sample = commands.add_parser("sample", help="generate a sample dataset")
    sample.add_argument("source", choices=["dunnhumby"])
    sample.add_argument("--output-dir", type=Path, required=True)
    sample.add_argument("--seed", type=int, default=20260915)
    sample.set_defaults(handler=_run_sample)

    lakehouse = commands.add_parser("lakehouse", help="manage the lakehouse")
    lakehouse_commands = lakehouse.add_subparsers(dest="lakehouse_command", required=True)
    lakehouse_commands.add_parser(
        "bootstrap", help="create buckets, the warehouse, and namespaces"
    ).set_defaults(handler=_run_bootstrap)
    lakehouse_commands.add_parser("tables", help="list tables with record counts").set_defaults(
        handler=_run_list_tables
    )

    ingest = commands.add_parser("ingest", help="land raw files and load bronze tables")
    ingest.add_argument("source", choices=sorted(SOURCE_TABLES))
    ingest.add_argument("--input-dir", type=Path, required=True)
    ingest.set_defaults(handler=_run_ingest)
    return parser


def _run_sample(args: argparse.Namespace) -> None:
    row_counts = write_dunnhumby_sample(args.output_dir, seed=args.seed)
    for file_name, row_count in row_counts.items():
        logger.info("wrote %s (%d rows)", args.output_dir / file_name, row_count)


def _run_bootstrap(_: argparse.Namespace) -> None:
    storage_settings = ObjectStorageSettings()
    lakehouse_settings = LakehouseSettings()
    report = bootstrap_lakehouse(
        storage=_object_storage(storage_settings),
        admin=LakekeeperAdminClient(lakehouse_settings.lakekeeper_url),
        connect_catalog=lambda: load_lakehouse_catalog(lakehouse_settings, storage_settings),
        buckets=(storage_settings.raw_bucket, storage_settings.warehouse_bucket),
        warehouse_request=CreateWarehouseRequest.for_s3_compatible_storage(
            warehouse_name=lakehouse_settings.warehouse,
            bucket=storage_settings.warehouse_bucket,
            key_prefix=lakehouse_settings.warehouse_key_prefix,
            endpoint=storage_settings.endpoint,
            region=storage_settings.region,
            access_key_id=storage_settings.access_key_id,
            secret_access_key=storage_settings.secret_access_key,
        ),
    )
    logger.info("bootstrap finished: %s", report)


def _run_list_tables(_: argparse.Namespace) -> None:
    catalog = load_lakehouse_catalog(LakehouseSettings(), ObjectStorageSettings())
    for table_count in list_table_record_counts(catalog):
        logger.info("%-45s %12d rows", table_count.identifier, table_count.records)


def _run_ingest(args: argparse.Namespace) -> None:
    storage_settings = ObjectStorageSettings()
    lakehouse_settings = LakehouseSettings()
    ingested_at = datetime.now(UTC)
    report = ingest_source(
        storage=_object_storage(storage_settings),
        connect_catalog=lambda: load_lakehouse_catalog(lakehouse_settings, storage_settings),
        raw_bucket=storage_settings.raw_bucket,
        source=args.source,
        tables=SOURCE_TABLES[args.source],
        input_dir=args.input_dir,
        batch_id=new_batch_id(ingested_at),
        ingested_at=ingested_at,
    )
    for count in report.counts:
        logger.info(
            "bronze %-24s landed=%d committed=%d",
            count.table,
            count.landed_rows,
            count.committed_rows,
        )
    logger.info("peak memory %.0f MiB", _measure_peak_memory_mib())


def _object_storage(settings: ObjectStorageSettings) -> PyArrowObjectStorage:
    return PyArrowObjectStorage.for_s3(
        endpoint=settings.endpoint,
        region=settings.region,
        access_key_id=settings.access_key_id,
        secret_access_key=settings.secret_access_key.get_secret_value(),
    )


def _measure_peak_memory_mib() -> float:
    peak_resident_size = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is reported in bytes on macOS and in kibibytes on Linux.
    if sys.platform == "darwin":
        return peak_resident_size / 1024 / 1024
    return peak_resident_size / 1024
