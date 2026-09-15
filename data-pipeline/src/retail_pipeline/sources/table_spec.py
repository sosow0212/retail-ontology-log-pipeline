"""Declarative specifications of source CSV tables."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

import pyarrow as pa

from retail_pipeline.errors import SchemaMismatchError


class ColumnType(StrEnum):
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"

    def to_arrow(self) -> pa.DataType:
        return _ARROW_TYPES[self]


_ARROW_TYPES: dict[ColumnType, pa.DataType] = {
    ColumnType.INTEGER: pa.int64(),
    ColumnType.FLOAT: pa.float64(),
    ColumnType.STRING: pa.string(),
}


@dataclass(frozen=True, slots=True)
class SourceColumn:
    source_name: str
    name: str
    type: ColumnType

    @classmethod
    def of(cls, source_name: str, column_type: ColumnType) -> Self:
        """Declare a column whose bronze name is the lower-cased source header."""
        return cls(source_name=source_name, name=source_name.lower(), type=column_type)


@dataclass(frozen=True, slots=True)
class SourceTable:
    source: str
    name: str
    columns: tuple[SourceColumn, ...]

    @property
    def file_name(self) -> str:
        return f"{self.name}.csv"

    @property
    def bronze_name(self) -> str:
        return f"{self.source}_{self.name}"

    @property
    def source_headers(self) -> list[str]:
        return [column.source_name for column in self.columns]

    def validate_headers(self, headers: Sequence[str]) -> None:
        """Raise SchemaMismatchError unless the headers equal the declared columns in order."""
        if list(headers) != self.source_headers:
            raise SchemaMismatchError(
                f"{self.file_name}: expected columns {self.source_headers}, found {list(headers)}"
            )

    def csv_column_types(self) -> dict[str, pa.DataType]:
        return {column.source_name: column.type.to_arrow() for column in self.columns}

    def arrow_schema(self) -> pa.Schema:
        return pa.schema([pa.field(column.name, column.type.to_arrow()) for column in self.columns])
