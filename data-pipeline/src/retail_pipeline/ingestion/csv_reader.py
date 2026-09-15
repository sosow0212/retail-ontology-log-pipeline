"""Streaming CSV reader that enforces a SourceTable specification."""

from collections.abc import Iterator
from typing import BinaryIO

import pyarrow as pa
from pyarrow import csv as pa_csv

from retail_pipeline.sources.table_spec import SourceTable

# Loading the 36.8M-row causal_data.csv peaked at 1.9GiB RSS with 64MiB blocks and 1.2GiB with
# 16MiB blocks at the same speed, and 64MiB blocks were OOM-killed under a 2GiB Job limit.
DEFAULT_BLOCK_SIZE_BYTES = 16 * 1024 * 1024


def read_source_batches(
    stream: BinaryIO | pa.NativeFile,
    table: SourceTable,
    block_size_bytes: int = DEFAULT_BLOCK_SIZE_BYTES,
) -> Iterator[pa.RecordBatch]:
    """Yield typed record batches with bronze column names after validating the CSV header.

    Raises:
        SchemaMismatchError: The header differs from the table specification.
        pyarrow.ArrowInvalid: A value cannot be converted to its declared type.
    """
    reader = pa_csv.open_csv(
        stream,
        read_options=pa_csv.ReadOptions(block_size=block_size_bytes),
        convert_options=pa_csv.ConvertOptions(column_types=table.csv_column_types()),
    )
    table.validate_headers(reader.schema.names)
    target_schema = table.arrow_schema()
    for batch in reader:
        yield pa.RecordBatch.from_arrays(batch.columns, schema=target_schema)
