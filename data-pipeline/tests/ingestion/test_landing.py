import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from retail_pipeline.errors import ManifestError, MissingSourceFileError
from retail_pipeline.ingestion.landing import (
    LandingManifest,
    describe_csv_file,
    land_source_files,
    new_batch_id,
)
from retail_pipeline.lakehouse.pyarrow_storage import PyArrowObjectStorage
from retail_pipeline.sources.table_spec import SourceTable

CsvWriter = Callable[[str, list[str]], Path]
LANDED_AT = datetime(2026, 9, 15, 10, 30, tzinfo=UTC)
BATCH_ID = "20260915T103000Z"


def test_new_batch_id_with_utc_time_returns_sortable_identifier() -> None:
    assert new_batch_id(LANDED_AT) == BATCH_ID


def test_describe_csv_file_without_trailing_newline_counts_last_row(tmp_path: Path) -> None:
    content = b"A,B\n1,2\n3,4"
    path = tmp_path / "rows.csv"
    path.write_bytes(content)

    stats = describe_csv_file(path)

    assert stats.row_count == 2
    assert stats.size_bytes == len(content)
    assert stats.sha256 == hashlib.sha256(content).hexdigest()


def test_describe_csv_file_with_header_only_counts_zero_rows(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_bytes(b"A,B\n")

    assert describe_csv_file(path).row_count == 0


def test_land_source_files_with_all_files_uploads_them_and_writes_manifest(
    orders_table: SourceTable, storage: PyArrowObjectStorage, write_csv: CsvWriter
) -> None:
    path = write_csv("orders.csv", ["ORDER_ID,AMOUNT,NOTE", "1,9.5,first"])

    manifest = land_source_files(
        storage, "raw", "demo", [orders_table], path.parent, BATCH_ID, LANDED_AT
    )

    prefix = f"demo/batch_id={BATCH_ID}"
    assert storage.exists("raw", f"{prefix}/orders.csv")
    assert (
        LandingManifest.from_json(storage.read_text("raw", f"{prefix}/_manifest.json")) == manifest
    )
    assert manifest.file_for(orders_table).row_count == 1


def test_land_source_files_with_missing_file_uploads_nothing(
    orders_table: SourceTable, storage: PyArrowObjectStorage, tmp_path: Path
) -> None:
    with pytest.raises(MissingSourceFileError, match=r"orders\.csv"):
        land_source_files(
            storage, "raw", "demo", [orders_table], tmp_path / "missing", BATCH_ID, LANDED_AT
        )

    assert not storage.exists("raw", f"demo/batch_id={BATCH_ID}/_manifest.json")


def test_landing_manifest_from_json_with_missing_fields_raises_manifest_error() -> None:
    with pytest.raises(ManifestError):
        LandingManifest.from_json('{"source": "demo"}')
