from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General
    APP_ENV: str = "local"
    APP_NAME: str = "ai-search-app"
    LOG_LEVEL: str = "INFO"

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
    POSTGRES_DB: str = "ai_search"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SSLMODE: str = "disable"

    # Blob Storage
    AZURE_STORAGE_ACCOUNT: Optional[str] = None
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None
    AZURE_BLOB_CONTAINER_ORIGINALS: Optional[str] = None
    AZURE_BLOB_CONTAINER_ARTIFACTS: Optional[str] = None

    # Observability
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional[str] = None


settings = Settings()
