from collections.abc import Callable
from pathlib import Path

import pytest
from pyiceberg.catalog.sql import SqlCatalog

from retail_pipeline.lakehouse.pyarrow_storage import PyArrowObjectStorage
from retail_pipeline.sources.table_spec import ColumnType, SourceColumn, SourceTable


@pytest.fixture
def orders_table() -> SourceTable:
    return SourceTable(
        source="demo",
        name="orders",
        columns=(
            SourceColumn.of("ORDER_ID", ColumnType.INTEGER),
            SourceColumn.of("AMOUNT", ColumnType.FLOAT),
            SourceColumn.of("NOTE", ColumnType.STRING),
        ),
    )


@pytest.fixture
def storage(tmp_path: Path) -> PyArrowObjectStorage:
    return PyArrowObjectStorage.for_local_directory(tmp_path / "object-storage")


@pytest.fixture
def catalog(tmp_path: Path) -> SqlCatalog:
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()
    return SqlCatalog(
        "test", uri=f"sqlite:///{tmp_path / 'catalog.db'}", warehouse=warehouse.as_uri()
    )


@pytest.fixture
def write_csv(tmp_path: Path) -> Callable[[str, list[str]], Path]:
    input_dir = tmp_path / "input"

    def write(file_name: str, lines: list[str]) -> Path:
        input_dir.mkdir(parents=True, exist_ok=True)
        path = input_dir / file_name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return write
