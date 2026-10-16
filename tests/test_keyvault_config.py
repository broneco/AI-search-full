"""Isolated Key Vault resolution; never call Azure or persist secret values."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import azure.identity
import azure.keyvault.secrets

from app.core.config import Settings


def configured_env_keys(root):
    """Check configured targets only; placeholder tenants need no real credentials."""
    from dotenv import dotenv_values
    def filled(value):
        return bool(value and value.strip() and not value.strip().lower().startswith(
            ("<", "your_", "your-", "replace", "todo", "required")))
    file_keys = {}
    for path in root.rglob(".env*"):
        if not path.is_file():
            continue
        values = dotenv_values(path, encoding="utf-8-sig", interpolate=False)
        sql = all(filled(values.get(key)) for key in ("AZURE_SQL_HOST", "AZURE_SQL_DB"))
        pg = all(filled(values.get(key)) for key in ("POSTGRES_HOST", "POSTGRES_DB"))
        if filled(values.get("TENANT_ID")) and values.get("APP_ENV") in {"dev", "prod"} and (sql or pg):
            file_keys[path] = set(values)
    return file_keys


def assert_env_key_parity(file_keys):
    assert file_keys, "Provide at least one configured tenant for the optional real-env check."
    all_keys = set().union(*file_keys.values())
    for path, keys in file_keys.items():
        assert keys == all_keys, f"Key parity mismatch in {path}: {all_keys - keys}"


def test_tenant_env_structural_key_parity():
    files = configured_env_keys(Path("tenants"))
    if not files:
        pytest.skip("No configured private tenant env; synthetic one-tenant regression remains active.")
    assert_env_key_parity(files)


def test_one_configured_tenant_is_sufficient(tmp_path):
    tenant = tmp_path / "alpha"
    tenant.mkdir()
    (tenant / ".env.dev").write_text("APP_ENV=dev\nTENANT_ID=alpha-dev\nAZURE_SQL_HOST=sql.example.test\nAZURE_SQL_DB=test\n", encoding="utf-8")
    placeholders = tmp_path / "unconfigured"
    placeholders.mkdir()
    (placeholders / ".env.prod").write_text("APP_ENV=prod\nTENANT_ID=other-prod\nAZURE_SQL_HOST=<REQUIRED>\n", encoding="utf-8")
    files = configured_env_keys(tmp_path)
    assert len(files) == 1
    assert_env_key_parity(files)


def test_configured_tenant_key_mismatch_is_rejected():
    with pytest.raises(AssertionError, match="Key parity mismatch"):
        assert_env_key_parity({Path("alpha"): {"TENANT_ID"}, Path("beta"): {"TENANT_ID", "EXTRA"}})


@pytest.fixture
def vault(monkeypatch):
    client = MagicMock()
    client.get_secret.side_effect = lambda name, **kw: SimpleNamespace(value="value-for-" + name)
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", MagicMock())
    monkeypatch.setattr(azure.keyvault.secrets, "SecretClient", constructor)
    return client, constructor


def config(**overrides):
    values = dict(_env_file=None, APP_ENV="prod", DATABASE_BACKEND="postgresql",
        AZURE_KEY_VAULT_NAME="unit-test-vault", JWT_SECRET="", LEGACY_PASSWORD_SECRET=None,
        AZURE_SQL_PASSWORD=None, AZURE_OPENAI_API_KEY=None, AZURE_STORAGE_CONNECTION_STRING=None,
        POSTGRES_PASSWORD=None, AZURE_KEY_VAULT_SECRET_SQL_PASSWORD=None,
        AZURE_KEY_VAULT_SECRET_OPENAI_KEY=None, AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR=None,
        AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD=None,
        AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY=None,
        AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY_VERSION=None,
        AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD=None)
    return Settings(**(values | overrides))


def test_keyvault_dynamic_secret_fetching(vault):
    result = config(AZURE_KEY_VAULT_SECRET_SQL_PASSWORD="sql", AZURE_KEY_VAULT_SECRET_OPENAI_KEY="openai",
        AZURE_KEY_VAULT_SECRET_STORAGE_CONNSTR="storage", AZURE_KEY_VAULT_SECRET_POSTGRES_PASSWORD="pg")
    for field, name in (("AZURE_SQL_PASSWORD", "sql"), ("AZURE_OPENAI_API_KEY", "openai"),
                        ("AZURE_STORAGE_CONNECTION_STRING", "storage"), ("POSTGRES_PASSWORD", "pg")):
        assert getattr(result, field) == "value-for-" + name


@pytest.mark.parametrize("initial", ["", "dolphin-ai-search-secret-key-2026"])
def test_jwt_and_legacy_are_separate_and_jwt_version_is_pinned(vault, initial):
    client, constructor = vault
    result = config(JWT_SECRET=initial, AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY="jwt-new",
        AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY_VERSION="version-id",
        AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD="password-old")
    assert result.JWT_SECRET == "value-for-jwt-new"
    assert result.LEGACY_PASSWORD_SECRET == "value-for-password-old"
    client.get_secret.assert_any_call("jwt-new", version="version-id")
    client.get_secret.assert_any_call("password-old")
    constructor.assert_called_once()
    assert result.JWT_SECRET not in repr(result)
    assert result.LEGACY_PASSWORD_SECRET not in repr(result)
    assert "JWT_SECRET" not in result.model_dump()
    assert "LEGACY_PASSWORD_SECRET" not in result.model_dump()


def test_explicit_private_runtime_keys_win_over_keyvault(vault):
    client, _ = vault
    result = config(JWT_SECRET="explicit-private-key", LEGACY_PASSWORD_SECRET="explicit-old-key",
        AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY="jwt-new", AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD="old")
    assert result.JWT_SECRET == "explicit-private-key"
    assert result.LEGACY_PASSWORD_SECRET == "explicit-old-key"
    client.get_secret.assert_not_called()


@pytest.mark.parametrize("environment", ["local", "test"])
def test_local_and_test_never_contact_keyvault(vault, environment):
    _, constructor = vault
    result = config(APP_ENV=environment, AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY="jwt",
                    AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD="legacy")
    assert result.JWT_SECRET == ""
    assert result.LEGACY_PASSWORD_SECRET is None
    constructor.assert_not_called()


@pytest.mark.parametrize("failure", ["denied", "empty", "default"])
def test_failed_jwt_resolution_never_uses_legacy_key(vault, monkeypatch, capsys, failure):
    from fastapi import HTTPException
    from app.api.routes import auth
    client, _ = vault
    def resolve(name, **kwargs):
        if name == "legacy":
            return SimpleNamespace(value="legacy-not-for-signing")
        if failure == "denied":
            raise RuntimeError("private-provider-error-must-not-leak")
        return SimpleNamespace(value="" if failure == "empty" else "dolphin-ai-search-secret-key-2026")
    client.get_secret.side_effect = resolve
    result = config(AZURE_KEY_VAULT_SECRET_JWT_SIGNING_KEY="jwt", AZURE_KEY_VAULT_SECRET_LEGACY_PASSWORD="legacy")
    monkeypatch.setattr(auth, "settings", result)
    with pytest.raises(HTTPException) as error:
        auth._signing_key()
    assert error.value.status_code == 503
    assert result.LEGACY_PASSWORD_SECRET == "legacy-not-for-signing"
    captured = capsys.readouterr()
    assert "private-provider-error" not in captured.out + captured.err
