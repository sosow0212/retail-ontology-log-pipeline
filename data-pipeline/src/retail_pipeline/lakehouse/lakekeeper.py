"""Lakekeeper management API: server bootstrap and warehouse creation."""

import logging
from typing import Any, Literal, Protocol, Self

import requests
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_serializer

from retail_pipeline.errors import LakekeeperError

logger = logging.getLogger(__name__)

_API_MODEL_CONFIG = ConfigDict(
    validate_by_name=True, validate_by_alias=True, serialize_by_alias=True
)


class S3StorageProfile(BaseModel):
    model_config = _API_MODEL_CONFIG

    type: Literal["s3"] = "s3"
    bucket: str
    key_prefix: str = Field(alias="key-prefix")
    endpoint: str
    region: str
    path_style_access: bool = Field(default=True, alias="path-style-access")
    flavor: Literal["s3-compat", "aws"] = "s3-compat"
    sts_enabled: bool = Field(default=False, alias="sts-enabled")
    # Engines bring their own static credentials, so Lakekeeper does not sign requests.
    remote_signing_enabled: bool = Field(default=False, alias="remote-signing-enabled")


class S3AccessKeyCredential(BaseModel):
    model_config = _API_MODEL_CONFIG

    type: Literal["s3"] = "s3"
    credential_type: Literal["access-key"] = Field(default="access-key", alias="credential-type")
    aws_access_key_id: str = Field(alias="aws-access-key-id")
    aws_secret_access_key: SecretStr = Field(alias="aws-secret-access-key")

    @field_serializer("aws_secret_access_key", when_used="json")
    def _reveal_secret_for_api(self, value: SecretStr) -> str:
        return value.get_secret_value()


class CreateWarehouseRequest(BaseModel):
    model_config = _API_MODEL_CONFIG

    warehouse_name: str = Field(alias="warehouse-name")
    storage_profile: S3StorageProfile = Field(alias="storage-profile")
    storage_credential: S3AccessKeyCredential = Field(alias="storage-credential")

    @classmethod
    def for_s3_compatible_storage(
        cls,
        *,
        warehouse_name: str,
        bucket: str,
        key_prefix: str,
        endpoint: str,
        region: str,
        access_key_id: str,
        secret_access_key: SecretStr,
    ) -> Self:
        return cls(
            warehouse_name=warehouse_name,
            storage_profile=S3StorageProfile(
                bucket=bucket, key_prefix=key_prefix, endpoint=endpoint, region=region
            ),
            storage_credential=S3AccessKeyCredential(
                aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key
            ),
        )


class HttpResponse(Protocol):
    status_code: int
    content: bytes
    text: str

    @property
    def ok(self) -> bool:
        """Return True for 2xx and 3xx responses."""
        ...

    def json(self) -> Any:  # noqa: ANN401 - mirrors requests.Response.json
        """Decode the response body as JSON."""
        ...


class HttpSession(Protocol):
    def request(
        self, method: str, url: str, *, json: dict[str, Any] | None, timeout: float
    ) -> HttpResponse:
        """Send an HTTP request."""
        ...


class LakekeeperAdminClient:
    """Management API client for a Lakekeeper server running without authentication."""

    def __init__(
        self, base_url: str, session: HttpSession | None = None, timeout_seconds: float = 30.0
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session: HttpSession = session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def bootstrap(self) -> bool:
        """Bootstrap the server once and return False when it was already bootstrapped."""
        if self._request("GET", "/management/v1/info").get("bootstrapped", False):
            return False
        self._request("POST", "/management/v1/bootstrap", body={"accept-terms-of-use": True})
        logger.info("bootstrapped Lakekeeper at %s", self._base_url)
        return True

    def has_warehouse(self, name: str) -> bool:
        """Return True when a warehouse with this name exists in the default project."""
        payload = self._request("GET", "/management/v1/warehouse")
        return any(warehouse.get("name") == name for warehouse in payload.get("warehouses", []))

    def create_warehouse(self, request: CreateWarehouseRequest) -> None:
        """Create a warehouse; Lakekeeper checks storage access before accepting it."""
        self._request("POST", "/management/v1/warehouse", body=request.model_dump(mode="json"))
        logger.info("created warehouse %s", request.warehouse_name)

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            response = self._session.request(method, url, json=body, timeout=self._timeout_seconds)
        except requests.RequestException as error:
            raise LakekeeperError(f"{method} {path} failed: {error}") from error
        if not response.ok:
            raise LakekeeperError(
                f"{method} {path} returned HTTP {response.status_code}: {response.text[:500]}"
            )
        return response.json() if response.content else {}
