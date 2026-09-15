from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pyiceberg.catalog import Catalog

from retail_pipeline.errors import SchemaMismatchError, VerificationError
from retail_pipeline.ingestion.bronze import (
    BATCH_ID_COLUMN,
    BRONZE_NAMESPACE,
    INGESTED_AT_COLUMN,
    SOURCE_URI_COLUMN,
    bronze_identifier,
    load_bronze_table,
    verify_bronze,
)
from retail_pipeline.ingestion.landing import LandingManifest, land_source_files
from retail_pipeline.lakehouse.catalog import current_record_count
from retail_pipeline.lakehouse.object_storage import ObjectStorage
from retail_pipeline.sources.table_spec import SourceTable

CsvWriter = Callable[[str, list[str]], Path]
Lander = Callable[[list[str], str], LandingManifest]
INGESTED_AT = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
HEADER = "ORDER_ID,AMOUNT,NOTE"


@pytest.fixture(autouse=True)
def bronze_namespace(catalog: Catalog) -> None:
    catalog.create_namespace(BRONZE_NAMESPACE)


@pytest.fixture
def land(orders_table: SourceTable, storage: ObjectStorage, write_csv: CsvWriter) -> Lander:
    def land_rows(rows: list[str], batch_id: str) -> LandingManifest:
        path = write_csv(orders_table.file_name, [HEADER, *rows])
        return land_source_files(
            storage, "raw", orders_table.source, [orders_table], path.parent, batch_id, INGESTED_AT
        )

    return land_rows


def _bronze_rows(catalog: Catalog, table: SourceTable) -> list[dict[str, Any]]:
    rows = catalog.load_table(bronze_identifier(table)).scan().to_arrow().to_pylist()
    return sorted(rows, key=lambda row: row["order_id"])


def test_load_bronze_table_with_landed_file_adds_lineage_columns(
    orders_table: SourceTable, storage: ObjectStorage, catalog: Catalog, land: Lander
) -> None:
    manifest = land(["1,9.5,first", "2,3.0,second"], "batch-1")

    written_rows = load_bronze_table(catalog, storage, "raw", manifest, orders_table, INGESTED_AT)

    rows = _bronze_rows(catalog, orders_table)
    assert written_rows == 2
    assert [row["note"] for row in rows] == ["first", "second"]
    assert rows[0][BATCH_ID_COLUMN] == "batch-1"
    assert rows[0][SOURCE_URI_COLUMN] == "s3://raw/demo/batch_id=batch-1/orders.csv"
    assert rows[0][INGESTED_AT_COLUMN] == INGESTED_AT


def test_load_bronze_table_run_twice_keeps_only_latest_batch(
    orders_table: SourceTable, storage: ObjectStorage, catalog: Catalog, land: Lander
) -> None:
    first = land(["1,9.5,first", "2,3.0,second"], "batch-1")
    load_bronze_table(catalog, storage, "raw", first, orders_table, INGESTED_AT)
    second = land(["3,1.0,third"], "batch-2")

    load_bronze_table(catalog, storage, "raw", second, orders_table, INGESTED_AT)

    rows = _bronze_rows(catalog, orders_table)
    assert [row["order_id"] for row in rows] == [3]
    assert {row[BATCH_ID_COLUMN] for row in rows} == {"batch-2"}


def test_load_bronze_table_with_invalid_value_keeps_previous_snapshot(
    orders_table: SourceTable, storage: ObjectStorage, catalog: Catalog, land: Lander
) -> None:
    valid = land(["1,9.5,first"], "batch-1")
    load_bronze_table(catalog, storage, "raw", valid, orders_table, INGESTED_AT)
    broken = land(["not-a-number,9.5,broken"], "batch-2")

    with pytest.raises(SchemaMismatchError, match=r"orders\.csv"):
        load_bronze_table(catalog, storage, "raw", broken, orders_table, INGESTED_AT)

    assert [row[BATCH_ID_COLUMN] for row in _bronze_rows(catalog, orders_table)] == ["batch-1"]


def test_load_bronze_table_with_many_blocks_commits_every_row_once(
    orders_table: SourceTable, storage: ObjectStorage, catalog: Catalog, land: Lander
) -> None:
    manifest = land([f"{index},{index}.25,note-{index}" for index in range(3_000)], "batch-1")

    written_rows = load_bronze_table(
        catalog, storage, "raw", manifest, orders_table, INGESTED_AT, block_size_bytes=8_192
    )

    iceberg_table = catalog.load_table(bronze_identifier(orders_table))
    assert written_rows == 3_000
    assert current_record_count(iceberg_table) == 3_000
    assert iceberg_table.scan().to_arrow().num_rows == 3_000


def test_load_bronze_table_with_header_only_file_leaves_table_empty(
    orders_table: SourceTable, storage: ObjectStorage, catalog: Catalog, land: Lander
) -> None:
    previous = land(["1,9.5,first"], "batch-1")
    load_bronze_table(catalog, storage, "raw", previous, orders_table, INGESTED_AT)
    empty = land([], "batch-2")

    written_rows = load_bronze_table(catalog, storage, "raw", empty, orders_table, INGESTED_AT)

    assert written_rows == 0
    assert _bronze_rows(catalog, orders_table) == []


def test_load_bronze_table_with_header_only_file_on_new_table_writes_nothing(
    orders_table: SourceTable, storage: ObjectStorage, catalog: Catalog, land: Lander
) -> None:
    manifest = land([], "batch-1")

    written_rows = load_bronze_table(catalog, storage, "raw", manifest, orders_table, INGESTED_AT)

    assert written_rows == 0
    assert verify_bronze(catalog, manifest, [orders_table])[0].is_consistent()


def test_verify_bronze_with_matching_counts_returns_counts(
    orders_table: SourceTable, storage: ObjectStorage, catalog: Catalog, land: Lander
) -> None:
    manifest = land(["1,9.5,first"], "batch-1")
    load_bronze_table(catalog, storage, "raw", manifest, orders_table, INGESTED_AT)

    counts = verify_bronze(catalog, manifest, [orders_table])

    assert [(count.landed_rows, count.committed_rows) for count in counts] == [(1, 1)]


def test_verify_bronze_with_missing_rows_raises_verification_error(
    orders_table: SourceTable, storage: ObjectStorage, catalog: Catalog, land: Lander
) -> None:
    manifest = land(["1,9.5,first"], "batch-1")
    load_bronze_table(catalog, storage, "raw", manifest, orders_table, INGESTED_AT)
    inflated = replace(manifest, files=(replace(manifest.files[0], row_count=5),))

    with pytest.raises(VerificationError, match="orders"):
        verify_bronze(catalog, inflated, [orders_table])
