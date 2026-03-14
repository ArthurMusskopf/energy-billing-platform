from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "energy-billing-platform"
    app_env: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: List[str] = ["http://localhost:8080"]

    upload_dir: str = "/app/data/uploads"
    generated_dir: str = "/app/data/generated"

    gcp_project_id: str = "football-data-science"
    gcp_dataset_id: str = "erb_tech"
    gcp_location: str = "southamerica-east1"
    google_application_credentials: str = "/app/secrets/gcp-service-account.json"

    sicoob_base_url: str = "https://sandbox.sicoob.com.br/sicoob/sandbox/cobranca-bancaria/v3"
    sicoob_client_id: str = ""
    sicoob_access_token: str = ""
    sicoob_numero_cliente: int | None = None
    sicoob_codigo_modalidade: int = 1
    sicoob_numero_contrato_cobranca: int = 1
    sicoob_numero_conta_corrente: int = 0

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def split_cors(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()