from pydantic import SecretStr
from pyiceberg.catalog import Catalog

from retail_pipeline.lakehouse.bootstrap import BootstrapReport, bootstrap_lakehouse
from retail_pipeline.lakehouse.lakekeeper import CreateWarehouseRequest
from retail_pipeline.lakehouse.object_storage import ObjectStorage


class FakeCatalogAdmin:
    def __init__(self) -> None:
        self.is_bootstrapped = False
        self.warehouse_names: list[str] = []

    def bootstrap(self) -> bool:
        if self.is_bootstrapped:
            return False
        self.is_bootstrapped = True
        return True

    def has_warehouse(self, name: str) -> bool:
        return name in self.warehouse_names

    def create_warehouse(self, request: CreateWarehouseRequest) -> None:
        self.warehouse_names.append(request.warehouse_name)


def _bootstrap(
    storage: ObjectStorage, admin: FakeCatalogAdmin, catalog: Catalog
) -> BootstrapReport:
    return bootstrap_lakehouse(
        storage=storage,
        admin=admin,
        connect_catalog=lambda: catalog,
        buckets=("raw", "lakehouse"),
        warehouse_request=CreateWarehouseRequest.for_s3_compatible_storage(
            warehouse_name="lakehouse",
            bucket="lakehouse",
            key_prefix="warehouse",
            endpoint="http://seaweedfs:8333",
            region="local-01",
            access_key_id="lakehouse-key",
            secret_access_key=SecretStr("secret"),
        ),
    )


def test_bootstrap_lakehouse_on_empty_environment_creates_every_resource(
    storage: ObjectStorage, catalog: Catalog
) -> None:
    report = _bootstrap(storage, FakeCatalogAdmin(), catalog)

    assert report == BootstrapReport(
        created_buckets=("raw", "lakehouse"),
        bootstrapped_server=True,
        created_warehouse=True,
        created_namespaces=("bronze", "silver", "gold"),
    )


def test_bootstrap_lakehouse_run_twice_creates_nothing_the_second_time(
    storage: ObjectStorage, catalog: Catalog
) -> None:
    admin = FakeCatalogAdmin()
    _bootstrap(storage, admin, catalog)

    report = _bootstrap(storage, admin, catalog)

    assert report == BootstrapReport(
        created_buckets=(),
        bootstrapped_server=False,
        created_warehouse=False,
        created_namespaces=(),
    )
