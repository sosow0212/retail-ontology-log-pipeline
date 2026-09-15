"""PyIceberg REST catalog connection and table inventory."""

from dataclasses import dataclass

from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.table import Table

from retail_pipeline.settings import LakehouseSettings, ObjectStorageSettings

CATALOG_NAME = "lakehouse"


@dataclass(frozen=True, slots=True)
class TableRecordCount:
    identifier: str
    records: int


def load_lakehouse_catalog(lakehouse: LakehouseSettings, storage: ObjectStorageSettings) -> Catalog:
    """Connect to the Lakekeeper warehouse, reading and writing data files with static S3 keys."""
    return load_catalog(
        CATALOG_NAME,
        **{
            "type": "rest",
            "uri": lakehouse.catalog_uri,
            "warehouse": lakehouse.warehouse,
            "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
            "s3.endpoint": storage.endpoint,
            "s3.region": storage.region,
            "s3.access-key-id": storage.access_key_id,
            "s3.secret-access-key": storage.secret_access_key.get_secret_value(),
        },
    )


def current_record_count(table: Table) -> int:
    """Return the record count of the current snapshot, or 0 when the table has no snapshot."""
    snapshot = table.current_snapshot()
    if snapshot is None or snapshot.summary is None:
        return 0
    return int(snapshot.summary.get("total-records", "0"))


def list_table_record_counts(catalog: Catalog) -> list[TableRecordCount]:
    """Return every table in the catalog with its current record count."""
    counts: list[TableRecordCount] = []
    for namespace in sorted(catalog.list_namespaces()):
        for identifier in sorted(catalog.list_tables(namespace)):
            table = catalog.load_table(identifier)
            counts.append(
                TableRecordCount(
                    identifier=".".join(identifier), records=current_record_count(table)
                )
            )
    return counts
