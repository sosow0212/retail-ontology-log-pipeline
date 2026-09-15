"""Runtime configuration read from ``RETAIL_PIPELINE_*`` environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ObjectStorageSettings(BaseSettings):
    """S3-compatible storage that holds the raw zone and the Iceberg warehouse."""

    model_config = SettingsConfigDict(env_prefix="RETAIL_PIPELINE_S3_")

    endpoint: str = "http://localhost:8333"
    region: str = "local-01"
    access_key_id: str = ""
    secret_access_key: SecretStr = SecretStr("")
    raw_bucket: str = "raw"
    warehouse_bucket: str = "lakehouse"


class LakehouseSettings(BaseSettings):
    """Lakekeeper REST catalog location and warehouse layout."""

    model_config = SettingsConfigDict(env_prefix="RETAIL_PIPELINE_LAKEHOUSE_")

    lakekeeper_url: str = "http://localhost:8181"
    warehouse: str = "lakehouse"
    warehouse_key_prefix: str = "warehouse"

    @property
    def catalog_uri(self) -> str:
        return f"{self.lakekeeper_url.rstrip('/')}/catalog"
