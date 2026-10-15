import pytest

from app.core.config import Settings


def test_local_sqlserver_backend_is_explicit_and_uses_a_local_database():
    local_settings = Settings(
        _env_file=(),
        APP_ENV="local",
        DATABASE_BACKEND="sqlserver",
        AZURE_SQL_HOST="127.0.0.1",
        AZURE_SQL_DB="ai_search_local",
        AZURE_SQL_USER="sa",
        AZURE_SQL_PASSWORD="local-test-password",
    )

    assert local_settings.DATABASE_BACKEND == "sqlserver"
    assert local_settings.USE_AZURE_SQL is True
    assert local_settings.AZURE_SQL_DB == "ai_search_local"


def test_local_sqlserver_requires_explicit_credentials():
    with pytest.raises(ValueError, match="AZURE_SQL_PASSWORD"):
        Settings(
            _env_file=(),
            APP_ENV="local",
            DATABASE_BACKEND="sqlserver",
            AZURE_SQL_HOST="127.0.0.1",
            AZURE_SQL_USER="sa",
            AZURE_SQL_PASSWORD=None,
        )


def test_local_sqlserver_rejects_nonlocal_hosts():
    with pytest.raises(ValueError, match="reserved for a SQL Server on this computer"):
        Settings(
            _env_file=(),
            APP_ENV="local",
            DATABASE_BACKEND="sqlserver",
            AZURE_SQL_HOST="example.database.windows.net",
            AZURE_SQL_USER="sa",
            AZURE_SQL_PASSWORD="local-test-password",
        )
