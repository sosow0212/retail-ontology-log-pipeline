"""End-to-end ingestion of one source: raw landing, bronze load, and verification."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pyiceberg.catalog import Catalog

from retail_pipeline.ingestion.bronze import (
    BRONZE_NAMESPACE,
    BronzeTableCount,
    load_bronze_table,
    verify_bronze,
)
from retail_pipeline.ingestion.landing import LandingManifest, land_source_files
from retail_pipeline.lakehouse.object_storage import ObjectStorage
from retail_pipeline.sources.table_spec import SourceTable

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestionReport:
    manifest: LandingManifest
    counts: tuple[BronzeTableCount, ...]


def ingest_source(
    storage: ObjectStorage,
    connect_catalog: Callable[[], Catalog],
    raw_bucket: str,
    source: str,
    tables: Sequence[SourceTable],
    input_dir: Path,
    batch_id: str,
    ingested_at: datetime,
) -> IngestionReport:
    """Land the source files, replace the bronze tables, and verify their row counts."""
    manifest = land_source_files(
        storage, raw_bucket, source, tables, input_dir, batch_id, landed_at=ingested_at
    )
    catalog = connect_catalog()
    catalog.create_namespace_if_not_exists(BRONZE_NAMESPACE)
    for table in tables:
        load_bronze_table(catalog, storage, raw_bucket, manifest, table, ingested_at)
    counts = verify_bronze(catalog, manifest, tables)
    logger.info("verified %d bronze tables for batch %s", len(counts), batch_id)
    return IngestionReport(manifest=manifest, counts=tuple(counts))
