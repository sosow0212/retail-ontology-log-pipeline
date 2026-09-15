"""Bronze layer: typed copies of landed source files in Iceberg with lineage columns."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import pyarrow as pa
import pyarrow.compute as pc
from pyiceberg.catalog import Catalog

from retail_pipeline.errors import SchemaMismatchError, VerificationError
from retail_pipeline.ingestion.csv_reader import DEFAULT_BLOCK_SIZE_BYTES, read_source_batches
from retail_pipeline.ingestion.landing import LandingManifest
from retail_pipeline.lakehouse.catalog import current_record_count
from retail_pipeline.lakehouse.object_storage import ObjectStorage
from retail_pipeline.sources.table_spec import SourceTable

logger = logging.getLogger(__name__)

BRONZE_NAMESPACE = "bronze"
BATCH_ID_COLUMN = "_batch_id"
SOURCE_URI_COLUMN = "_source_uri"
INGESTED_AT_COLUMN = "_ingested_at"
_INGESTED_AT_TYPE = pa.timestamp("us", tz="UTC")


@dataclass(frozen=True, slots=True)
class BronzeTableCount:
    table: str
    landed_rows: int
    committed_rows: int

    def is_consistent(self) -> bool:
        return self.landed_rows == self.committed_rows


def bronze_identifier(table: SourceTable) -> tuple[str, str]:
    return (BRONZE_NAMESPACE, table.bronze_name)


def bronze_schema(table: SourceTable) -> pa.Schema:
    """Return the source columns followed by the lineage columns."""
    return (
        table.arrow_schema()
        .append(pa.field(BATCH_ID_COLUMN, pa.string()))
        .append(pa.field(SOURCE_URI_COLUMN, pa.string()))
        .append(pa.field(INGESTED_AT_COLUMN, _INGESTED_AT_TYPE))
    )


def with_lineage(
    batch: pa.RecordBatch,
    schema: pa.Schema,
    batch_id: str,
    source_uri: str,
    ingested_at: datetime,
) -> pa.Table:
    """Append constant lineage columns to a batch of source rows."""
    row_count = batch.num_rows
    lineage_columns = [
        pc.fill_null(pa.nulls(row_count, pa.string()), batch_id),
        pc.fill_null(pa.nulls(row_count, pa.string()), source_uri),
        pc.fill_null(
            pa.nulls(row_count, _INGESTED_AT_TYPE), pa.scalar(ingested_at, type=_INGESTED_AT_TYPE)
        ),
    ]
    return pa.Table.from_arrays([*batch.columns, *lineage_columns], schema=schema)


def load_bronze_table(
    catalog: Catalog,
    storage: ObjectStorage,
    raw_bucket: str,
    manifest: LandingManifest,
    table: SourceTable,
    ingested_at: datetime,
    block_size_bytes: int = DEFAULT_BLOCK_SIZE_BYTES,
) -> int:
    """Replace a bronze table with one landed file in a single commit and return the rows written.

    Raises:
        SchemaMismatchError: The landed file does not match the table specification. The
            previous snapshot stays current because nothing is committed.
    """
    landed_file = manifest.file_for(table)
    schema = bronze_schema(table)
    iceberg_table = catalog.create_table_if_not_exists(bronze_identifier(table), schema=schema)
    source_uri = f"s3://{raw_bucket}/{landed_file.object_key}"
    # Overwriting a table without rows only produces a no-op delete, so append in that case.
    must_replace_previous_rows = current_record_count(iceberg_table) > 0

    written_rows = 0
    with (
        storage.open_input_stream(raw_bucket, landed_file.object_key) as stream,
        iceberg_table.transaction() as transaction,
    ):
        try:
            for batch in read_source_batches(stream, table, block_size_bytes):
                data = with_lineage(batch, schema, manifest.batch_id, source_uri, ingested_at)
                if must_replace_previous_rows:
                    transaction.overwrite(data)
                    must_replace_previous_rows = False
                else:
                    transaction.append(data)
                written_rows += data.num_rows
            if must_replace_previous_rows:
                transaction.overwrite(schema.empty_table())
        except pa.ArrowInvalid as error:
            raise SchemaMismatchError(f"{table.file_name}: {error}") from error

    logger.info("committed %d rows to %s", written_rows, ".".join(bronze_identifier(table)))
    return written_rows


def verify_bronze(
    catalog: Catalog, manifest: LandingManifest, tables: Sequence[SourceTable]
) -> list[BronzeTableCount]:
    """Compare committed row counts with the landed row counts of every table.

    Raises:
        VerificationError: At least one table has a different number of rows.
    """
    counts = [
        BronzeTableCount(
            table=table.name,
            landed_rows=manifest.file_for(table).row_count,
            committed_rows=current_record_count(catalog.load_table(bronze_identifier(table))),
        )
        for table in tables
    ]
    inconsistent_counts = [count for count in counts if not count.is_consistent()]
    if inconsistent_counts:
        raise VerificationError(f"row counts differ from landed files: {inconsistent_counts}")
    return counts
