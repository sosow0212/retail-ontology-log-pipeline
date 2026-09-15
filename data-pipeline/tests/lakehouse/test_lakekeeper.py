import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import SecretStr

from retail_pipeline.errors import LakekeeperError
from retail_pipeline.lakehouse.lakekeeper import CreateWarehouseRequest, LakekeeperAdminClient

BASE_URL = "http://lakekeeper:8181"
SECRET = "s3cr3t-value"


@dataclass
class FakeResponse:
    status_code: int
    payload: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def content(self) -> bytes:
        return b"" if self.payload is None else json.dumps(self.payload).encode()

    @property
    def text(self) -> str:
        return self.content.decode()

    def json(self) -> dict[str, Any]:
        return self.payload or {}


@dataclass
class FakeSession:
    responses: dict[tuple[str, str], FakeResponse]
    calls: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)

    def request(
        self, method: str, url: str, *, json: dict[str, Any] | None, timeout: float
    ) -> FakeResponse:
        path = url.removeprefix(BASE_URL)
        self.calls.append((method, path, json))
        return self.responses[(method, path)]


def _warehouse_request() -> CreateWarehouseRequest:
    return CreateWarehouseRequest.for_s3_compatible_storage(
        warehouse_name="lakehouse",
        bucket="lakehouse",
        key_prefix="warehouse",
        endpoint="http://seaweedfs:8333",
        region="local-01",
        access_key_id="lakehouse-key",
        secret_access_key=SecretStr(SECRET),
    )


def test_create_warehouse_request_dumped_as_json_uses_api_field_names() -> None:
    payload = _warehouse_request().model_dump(mode="json")

    assert payload["warehouse-name"] == "lakehouse"
    assert payload["storage-profile"] == {
        "type": "s3",
        "bucket": "lakehouse",
        "key-prefix": "warehouse",
        "endpoint": "http://seaweedfs:8333",
        "region": "local-01",
        "path-style-access": True,
        "flavor": "s3-compat",
        "sts-enabled": False,
        "remote-signing-enabled": False,
    }
    assert payload["storage-credential"]["aws-secret-access-key"] == SECRET


def test_create_warehouse_request_repr_masks_secret() -> None:
    assert SECRET not in repr(_warehouse_request())


def test_bootstrap_with_new_server_posts_bootstrap_request() -> None:
    session = FakeSession(
        {
            ("GET", "/management/v1/info"): FakeResponse(200, {"bootstrapped": False}),
            ("POST", "/management/v1/bootstrap"): FakeResponse(204),
        }
    )

    assert LakekeeperAdminClient(BASE_URL, session).bootstrap() is True
    assert session.calls[-1] == ("POST", "/management/v1/bootstrap", {"accept-terms-of-use": True})


def test_bootstrap_with_bootstrapped_server_skips_bootstrap_request() -> None:
    session = FakeSession(
        {("GET", "/management/v1/info"): FakeResponse(200, {"bootstrapped": True})}
    )

    assert LakekeeperAdminClient(BASE_URL, session).bootstrap() is False
    assert [method for method, _, _ in session.calls] == ["GET"]


def test_has_warehouse_with_matching_name_returns_true() -> None:
    session = FakeSession(
        {
            ("GET", "/management/v1/warehouse"): FakeResponse(
                200, {"warehouses": [{"name": "lakehouse"}]}
            )
        }
    )

    assert LakekeeperAdminClient(BASE_URL, session).has_warehouse("lakehouse") is True


def test_create_warehouse_with_error_status_raises_lakekeeper_error() -> None:
    session = FakeSession(
        {("POST", "/management/v1/warehouse"): FakeResponse(400, {"error": "bucket missing"})}
    )

    with pytest.raises(LakekeeperError, match="HTTP 400"):
        LakekeeperAdminClient(BASE_URL, session).create_warehouse(_warehouse_request())
