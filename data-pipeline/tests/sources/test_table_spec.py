import pyarrow as pa
import pytest

from retail_pipeline.errors import SchemaMismatchError
from retail_pipeline.sources.table_spec import SourceTable


def test_validate_headers_with_declared_order_passes(orders_table: SourceTable) -> None:
    orders_table.validate_headers(["ORDER_ID", "AMOUNT", "NOTE"])


def test_validate_headers_with_reordered_columns_raises_schema_mismatch(
    orders_table: SourceTable,
) -> None:
    with pytest.raises(SchemaMismatchError, match=r"orders\.csv"):
        orders_table.validate_headers(["AMOUNT", "ORDER_ID", "NOTE"])


def test_arrow_schema_with_uppercase_headers_uses_lowercase_names(
    orders_table: SourceTable,
) -> None:
    assert orders_table.arrow_schema() == pa.schema(
        [("order_id", pa.int64()), ("amount", pa.float64()), ("note", pa.string())]
    )


def test_bronze_name_with_source_prefix_joins_source_and_table(orders_table: SourceTable) -> None:
    assert orders_table.bronze_name == "demo_orders"
