from collections.abc import Callable
from pathlib import Path

import pyarrow as pa
import pytest

from retail_pipeline.errors import SchemaMismatchError
from retail_pipeline.ingestion.csv_reader import read_source_batches
from retail_pipeline.sources.table_spec import SourceTable

CsvWriter = Callable[[str, list[str]], Path]


def test_read_source_batches_with_valid_csv_returns_typed_bronze_columns(
    orders_table: SourceTable, write_csv: CsvWriter
) -> None:
    path = write_csv("orders.csv", ["ORDER_ID,AMOUNT,NOTE", "1,9.5,first", "2,,"])

    with path.open("rb") as stream:
        table = pa.Table.from_batches(list(read_source_batches(stream, orders_table)))

    assert table.schema == orders_table.arrow_schema()
    assert table.to_pylist() == [
        {"order_id": 1, "amount": 9.5, "note": "first"},
        {"order_id": 2, "amount": None, "note": ""},
    ]


def test_read_source_batches_with_renamed_header_raises_schema_mismatch(
    orders_table: SourceTable, write_csv: CsvWriter
) -> None:
    path = write_csv("orders.csv", ["ORDER_ID,TOTAL,NOTE", "1,9.5,first"])

    with path.open("rb") as stream, pytest.raises(SchemaMismatchError, match="TOTAL"):
        list(read_source_batches(stream, orders_table))


def test_read_source_batches_with_small_block_size_yields_several_batches(
    orders_table: SourceTable, write_csv: CsvWriter
) -> None:
    rows = [f"{index},{index}.5,note-{index}" for index in range(2_000)]
    path = write_csv("orders.csv", ["ORDER_ID,AMOUNT,NOTE", *rows])

    with path.open("rb") as stream:
        batches = list(read_source_batches(stream, orders_table, block_size_bytes=4_096))

    assert len(batches) > 1
    assert sum(batch.num_rows for batch in batches) == 2_000
