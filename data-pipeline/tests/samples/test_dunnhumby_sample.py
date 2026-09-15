import csv
from pathlib import Path

import pyarrow as pa

from retail_pipeline.ingestion.csv_reader import read_source_batches
from retail_pipeline.samples.dunnhumby import SampleSize, write_dunnhumby_sample
from retail_pipeline.sources.dunnhumby import DUNNHUMBY_TABLES

SEED = 7
SMALL_SAMPLE = SampleSize(households=30, demographic_households=10, products=60, baskets=80)


def _column(path: Path, column: str) -> set[str]:
    with path.open(encoding="utf-8", newline="") as file:
        return {row[column] for row in csv.DictReader(file)}


def test_write_dunnhumby_sample_produces_files_readable_with_table_specs(tmp_path: Path) -> None:
    row_counts = write_dunnhumby_sample(tmp_path, seed=SEED, size=SMALL_SAMPLE)

    for table in DUNNHUMBY_TABLES:
        with (tmp_path / table.file_name).open("rb") as stream:
            loaded = pa.Table.from_batches(list(read_source_batches(stream, table)))
        assert loaded.num_rows == row_counts[table.file_name] > 0


def test_write_dunnhumby_sample_with_same_seed_writes_identical_files(tmp_path: Path) -> None:
    write_dunnhumby_sample(tmp_path / "first", seed=SEED, size=SMALL_SAMPLE)
    write_dunnhumby_sample(tmp_path / "second", seed=SEED, size=SMALL_SAMPLE)

    for table in DUNNHUMBY_TABLES:
        first = (tmp_path / "first" / table.file_name).read_bytes()
        assert first == (tmp_path / "second" / table.file_name).read_bytes()


def test_write_dunnhumby_sample_keeps_references_between_tables(tmp_path: Path) -> None:
    write_dunnhumby_sample(tmp_path, seed=SEED, size=SMALL_SAMPLE)

    product_ids = _column(tmp_path / "product.csv", "PRODUCT_ID")
    campaign_ids = _column(tmp_path / "campaign_desc.csv", "CAMPAIGN")
    assert _column(tmp_path / "transaction_data.csv", "PRODUCT_ID") <= product_ids
    assert _column(tmp_path / "causal_data.csv", "PRODUCT_ID") <= product_ids
    assert _column(tmp_path / "coupon.csv", "PRODUCT_ID") <= product_ids
    assert _column(tmp_path / "campaign_table.csv", "CAMPAIGN") <= campaign_ids
    assert _column(tmp_path / "coupon_redempt.csv", "COUPON_UPC") <= _column(
        tmp_path / "coupon.csv", "COUPON_UPC"
    )
