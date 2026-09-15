"""Idempotent creation of buckets, the Lakekeeper warehouse, and Iceberg namespaces."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from pyiceberg.catalog import Catalog

from retail_pipeline.lakehouse.lakekeeper import CreateWarehouseRequest
from retail_pipeline.lakehouse.object_storage import ObjectStorage

MEDALLION_NAMESPACES = ("bronze", "silver", "gold")


class CatalogAdmin(Protocol):
    def bootstrap(self) -> bool:
        """Bootstrap the catalog server once and return False when it was already bootstrapped."""
        ...

    def has_warehouse(self, name: str) -> bool:
        """Return True when a warehouse with this name exists."""
        ...

    def create_warehouse(self, request: CreateWarehouseRequest) -> None:
        """Create a warehouse."""
        ...


@dataclass(frozen=True, slots=True)
class BootstrapReport:
    created_buckets: tuple[str, ...]
    bootstrapped_server: bool
    created_warehouse: bool
    created_namespaces: tuple[str, ...]


def bootstrap_lakehouse(
    storage: ObjectStorage,
    admin: CatalogAdmin,
    connect_catalog: Callable[[], Catalog],
    buckets: tuple[str, ...],
    warehouse_request: CreateWarehouseRequest,
    namespaces: tuple[str, ...] = MEDALLION_NAMESPACES,
) -> BootstrapReport:
    """Create whatever is missing; running it again leaves everything unchanged.

    The catalog is connected only after the warehouse exists, because the REST catalog
    resolves the warehouse while connecting.
    """
    created_buckets = tuple(bucket for bucket in buckets if storage.ensure_bucket(bucket))
    bootstrapped_server = admin.bootstrap()
    created_warehouse = not admin.has_warehouse(warehouse_request.warehouse_name)
    if created_warehouse:
        admin.create_warehouse(warehouse_request)

    catalog = connect_catalog()
    existing_namespaces = {namespace[0] for namespace in catalog.list_namespaces()}
    created_namespaces = tuple(
        namespace for namespace in namespaces if namespace not in existing_namespaces
    )
    for namespace in created_namespaces:
        catalog.create_namespace(namespace)

    return BootstrapReport(
        created_buckets=created_buckets,
        bootstrapped_server=bootstrapped_server,
        created_warehouse=created_warehouse,
        created_namespaces=created_namespaces,
    )
