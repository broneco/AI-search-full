import os
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine environment: 'dev', 'prod', or 'local'
_APP_ENV = os.getenv("APP_ENV", "dev").lower()
_ENV_FILES = (f".env.{_APP_ENV}", ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    APP_ENV: str = _APP_ENV
    APP_NAME: str = "ai-search-app"
    LOG_LEVEL: str = "INFO"
    TENANT_ID: str = "dolphin"
    JWT_SECRET: str = "dolphin-ai-search-secret-key-2026"

    # OpenAI Deployments
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_FLASH_DEPLOYMENT: str = "gpt-5.4-mini"
    AZURE_OPENAI_THINKING_DEPLOYMENT: str = "gpt-5.4-mini"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-large"
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_TIMEOUT: float = 30.0
    RRF_WEIGHT_VECTOR: float = 0.6
    RRF_WEIGHT_KEYWORD: float = 0.4

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: Optional[str] = None
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SSLMODE: str = "disable"

    # Azure SQL Database (Microsoft SQL Server)
    AZURE_SQL_HOST: Optional[str] = None
    AZURE_SQL_PORT: int = 1433
    AZURE_SQL_DB: Optional[str] = None
    AZURE_SQL_USER: Optional[str] = None
    AZURE_SQL_PASSWORD: Optional[str] = None
    AZURE_SQL_DRIVER: str = "ODBC Driver 18 for SQL Server"
    USE_AZURE_SQL: bool = False

    # Blob Storage
    AZURE_STORAGE_ACCOUNT: Optional[str] = None
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None
    AZURE_BLOB_CONTAINER_ORIGINALS: Optional[str] = None
    AZURE_BLOB_CONTAINER_ARTIFACTS: Optional[str] = None

    # Observability
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional[str] = None

    @model_validator(mode="after")
    def set_environment_defaults(self):
        # Determine if Azure SQL is active
        if self.AZURE_SQL_HOST and self.AZURE_SQL_HOST.strip():
            self.USE_AZURE_SQL = True
            if not self.AZURE_SQL_DB:
                self.AZURE_SQL_DB = "dolphin-ai-search-sqldb"

        # Set default DB name if not explicitly set
        if not self.POSTGRES_DB:
            if self.APP_ENV == "prod":
                self.POSTGRES_DB = "ai_search_prod"
            else:
                self.POSTGRES_DB = "ai_search_dev"

        # Set default blob container name if not explicitly set
        if not self.AZURE_BLOB_CONTAINER_ORIGINALS:
            if self.APP_ENV == "prod":
                self.AZURE_BLOB_CONTAINER_ORIGINALS = "dolphin-originals-prod"
            else:
                self.AZURE_BLOB_CONTAINER_ORIGINALS = "dolphin-originals-dev"

        if not self.AZURE_BLOB_CONTAINER_ARTIFACTS:
            if self.APP_ENV == "prod":
                self.AZURE_BLOB_CONTAINER_ARTIFACTS = "dolphin-artifacts-prod"
            else:
                self.AZURE_BLOB_CONTAINER_ARTIFACTS = "dolphin-artifacts-dev"

        return self


settings = Settings()
