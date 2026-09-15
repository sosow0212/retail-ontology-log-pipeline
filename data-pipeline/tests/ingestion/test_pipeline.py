from datetime import UTC, datetime
from pathlib import Path

from pyiceberg.catalog import Catalog

from retail_pipeline.ingestion.pipeline import ingest_source
from retail_pipeline.lakehouse.object_storage import ObjectStorage
from retail_pipeline.samples.dunnhumby import SampleSize, write_dunnhumby_sample
from retail_pipeline.sources.dunnhumby import DUNNHUMBY_SOURCE, DUNNHUMBY_TABLES

INGESTED_AT = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def test_ingest_source_with_dunnhumby_sample_loads_every_table_consistently(
    tmp_path: Path, storage: ObjectStorage, catalog: Catalog
) -> None:
    input_dir = tmp_path / "dunnhumby-sample"
    row_counts = write_dunnhumby_sample(input_dir, seed=11, size=SampleSize(baskets=120))

    report = ingest_source(
        storage=storage,
        connect_catalog=lambda: catalog,
        raw_bucket="raw",
        source=DUNNHUMBY_SOURCE,
        tables=DUNNHUMBY_TABLES,
        input_dir=input_dir,
        batch_id="20260915T120000Z",
        ingested_at=INGESTED_AT,
    )

    assert {count.table: count.committed_rows for count in report.counts} == {
        table.name: row_counts[table.file_name] for table in DUNNHUMBY_TABLES
    }
    assert all(count.is_consistent() for count in report.counts)
