import os
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine environment: 'dev', 'prod', or 'local' and tenant ID
_APP_ENV = os.getenv("APP_ENV", "dev").lower()
_RAW_TENANT = os.getenv("TENANT_ID", "jhu").strip().lower()
_TENANT_BASE = _RAW_TENANT.split("-")[0] if _RAW_TENANT else "default"
if _TENANT_BASE == "ju":
    _TENANT_BASE = "jhu"

_TENANTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tenants"))

# Priority sequence for loading env files (lowest priority first, highest priority last):
# Pydantic Settings loads in sequence where LATER entries overwrite EARLIER entries.
_ENV_FILES = (
    ".env",
    f".env.{_APP_ENV}",
    os.path.join(_TENANTS_DIR, "default", ".env"),
    os.path.join(_TENANTS_DIR, "default", f".env.{_APP_ENV}"),
    os.path.join(_TENANTS_DIR, _TENANT_BASE, ".env"),
    os.path.join(_TENANTS_DIR, _TENANT_BASE, f".env.{_APP_ENV}"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    APP_ENV: str = _APP_ENV
    APP_NAME: str = "ai-search-app"
    APP_VERSION: str = "v0.1.3"
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

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: Optional[str] = None
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: Optional[str] = None
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

    # Azure Infrastructure Configuration
    AZURE_RESOURCE_GROUP: Optional[str] = None
    AZURE_CONTAINER_REGISTRY: Optional[str] = None
    AZURE_CONTAINER_APP_NAME: Optional[str] = None
    AZURE_SWA_USER_NAME: Optional[str] = None
    AZURE_SWA_ADMIN_NAME: Optional[str] = None

    # Azure Key Vault Configuration
    AZURE_KEY_VAULT_NAME: Optional[str] = None
    AZURE_KEY_VAULT_SECRET_SQL_PASSWORD: Optional[str] = None
    AZURE_KEY_VAULT_SECRET_OPENAI_KEY: Optional[str] = None
    AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR: Optional[str] = None
    AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD: Optional[str] = None

    # Observability
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional[str] = None

    @model_validator(mode="after")
    def set_environment_defaults(self):
        # Dynamically fetch missing secrets from Azure Key Vault if configured
        if self.AZURE_KEY_VAULT_NAME and self.AZURE_KEY_VAULT_NAME.strip():
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                kv_uri = f"https://{self.AZURE_KEY_VAULT_NAME.strip()}.vault.azure.net"
                credential = DefaultAzureCredential()
                client = SecretClient(vault_url=kv_uri, credential=credential)

                # Fetch Azure SQL Password
                if not self.AZURE_SQL_PASSWORD and self.AZURE_KEY_VAULT_SECRET_SQL_PASSWORD:
                    try:
                        secret = client.get_secret(self.AZURE_KEY_VAULT_SECRET_SQL_PASSWORD)
                        if secret and secret.value:
                            self.AZURE_SQL_PASSWORD = secret.value
                    except Exception:
                        pass

                # Fetch Azure OpenAI API Key
                if not self.AZURE_OPENAI_API_KEY and self.AZURE_KEY_VAULT_SECRET_OPENAI_KEY:
                    try:
                        secret = client.get_secret(self.AZURE_KEY_VAULT_SECRET_OPENAI_KEY)
                        if secret and secret.value:
                            self.AZURE_OPENAI_API_KEY = secret.value
                    except Exception:
                        pass

                # Fetch Azure Storage Connection String
                if not self.AZURE_STORAGE_CONNECTION_STRING and self.AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR:
                    try:
                        secret = client.get_secret(self.AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR)
                        if secret and secret.value:
                            self.AZURE_STORAGE_CONNECTION_STRING = secret.value
                    except Exception:
                        pass

                # Fetch PostgreSQL Password
                if not self.POSTGRES_PASSWORD and self.AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD:
                    try:
                        secret = client.get_secret(self.AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD)
                        if secret and secret.value:
                            self.POSTGRES_PASSWORD = secret.value
                    except Exception:
                        pass
            except Exception:
                pass

        if not self.POSTGRES_PASSWORD:
            self.POSTGRES_PASSWORD = "postgres"

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
