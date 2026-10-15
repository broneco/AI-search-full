"""Argon2 storage and tenant-scoped transactional legacy login upgrades."""
import hashlib
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core import passwords
from app.core.config import settings
from app.api.routes import auth
from app.storage.models import DBUser
from test_search_access import access_engine, access_db, api_client


OLD_SECRET = "test-old-key-distinct-from-new-signing-key"
NEW_SECRET = "test-private-new-signing-key-with-enough-entropy"
PASSWORD = "Příliš žluťoučké heslo 123"


def legacy_hash(password=PASSWORD):
    return hashlib.sha256(f"{password}:{OLD_SECRET}".encode()).hexdigest()


def account(db, *, tenant="alpha", encoded=None):
    item = DBUser(user_id=uuid.uuid4(), tenant_id=tenant, email="migration@example.test",
                  username="test", role="User", groups=["User"], password_hash=encoded or legacy_hash())
    db.add(item)
    db.commit()
    return item


@pytest.fixture
def cloud_keys(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "JWT_SECRET", NEW_SECRET)
    monkeypatch.setattr(settings, "LEGACY_PASSWORD_SECRET", OLD_SECRET)


def login(client, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": "migration@example.test", "password": password})


def test_argon2_hashes_have_random_salts_and_no_signing_dependency(monkeypatch):
    first, second = passwords.hash_password(PASSWORD), passwords.hash_password(PASSWORD)
    assert first != second
    assert first.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert len(first) <= 255
    monkeypatch.setattr(settings, "JWT_SECRET", "rotated")
    assert passwords.verify_password(PASSWORD, first) == (True, False)
    assert passwords.verify_password("wrong", first) == (False, False)
    assert passwords.verify_password(PASSWORD, legacy_hash()) == (False, False)
    assert passwords.verify_password(PASSWORD, legacy_hash(), legacy_secret=OLD_SECRET) == (True, True)
    assert passwords.verify_password(legacy_hash(), legacy_hash(), legacy_secret=OLD_SECRET) == (False, False)


@pytest.mark.parametrize("value", ["", "not-a-hash", "a" * 256,
    "$argon2id$v=19$m=999999999,t=2,p=1$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "$argon2id$v=19$m=19456,t=999999999,p=1$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"])
def test_invalid_or_excessive_hash_parameters_are_rejected(value):
    assert passwords.verify_password(PASSWORD, value, legacy_secret=OLD_SECRET) == (False, False)


def test_legacy_login_upgrades_only_current_tenant_and_survives_jwt_rotation(access_db, api_client, cloud_keys, monkeypatch):
    current = account(access_db)
    foreign = account(access_db, tenant="beta")
    current_id, foreign_id = current.user_id, foreign.user_id
    # Knowing the old password pepper must never authorize old-signed tokens.
    monkeypatch.setattr(settings, "JWT_SECRET", OLD_SECRET)
    old_signed_token = auth.create_token(current)
    monkeypatch.setattr(settings, "JWT_SECRET", NEW_SECRET)
    assert api_client.get("/api/auth/me", headers={"Authorization": "Bearer " + old_signed_token}).status_code == 401
    result = login(api_client)
    assert result.status_code == 200, result.text
    upgraded = access_db.get(DBUser, current_id).password_hash
    assert upgraded.startswith("$argon2id$")
    assert access_db.get(DBUser, foreign_id).password_hash == legacy_hash()
    first_token = result.json()["access_token"]
    monkeypatch.setattr(settings, "LEGACY_PASSWORD_SECRET", None)
    monkeypatch.setattr(settings, "JWT_SECRET", NEW_SECRET + "-rotated")
    assert api_client.get("/api/auth/me", headers={"Authorization": "Bearer " + first_token}).status_code == 401
    assert login(api_client).status_code == 200
    assert access_db.get(DBUser, current_id).password_hash == upgraded


@pytest.mark.parametrize("failure", ["wrong-password", "no-legacy-key", "wrong-legacy-key", "signing-unavailable"])
def test_failed_login_never_changes_legacy_hash(access_db, api_client, cloud_keys, monkeypatch, failure):
    current = account(access_db)
    user_id = current.user_id
    if failure == "no-legacy-key": monkeypatch.setattr(settings, "LEGACY_PASSWORD_SECRET", None)
    if failure == "wrong-legacy-key": monkeypatch.setattr(settings, "LEGACY_PASSWORD_SECRET", "incorrect-key")
    if failure == "signing-unavailable": monkeypatch.setattr(settings, "JWT_SECRET", "")
    result = login(api_client, "wrong" if failure == "wrong-password" else PASSWORD)
    assert result.status_code == (503 if failure == "signing-unavailable" else 401)
    assert "access_token" not in result.json()
    assert access_db.get(DBUser, user_id).password_hash == legacy_hash()


def test_failed_upgrade_commit_rolls_back_and_returns_no_token(access_db, api_client, cloud_keys, monkeypatch):
    current = account(access_db)
    user_id = current.user_id
    def fail():
        raise SQLAlchemyError("private-database-message")
    monkeypatch.setattr(access_db, "commit", fail)
    result = login(api_client)
    assert result.status_code == 503
    assert "access_token" not in result.json()
    assert "private-database-message" not in result.text
    access_db.expire_all()
    assert access_db.get(DBUser, user_id).password_hash == legacy_hash()


def test_credential_change_during_upgrade_is_not_overwritten(access_db, api_client, cloud_keys, monkeypatch):
    account(access_db)
    original = access_db.execute
    def no_match(statement, *args, **kwargs):
        if getattr(statement, "is_update", False):
            from types import SimpleNamespace
            return SimpleNamespace(rowcount=0)
        return original(statement, *args, **kwargs)
    monkeypatch.setattr(access_db, "execute", no_match)
    result = login(api_client)
    assert result.status_code == 401
    assert "access_token" not in result.json()
    assert access_db.scalar(select(DBUser.password_hash)) == legacy_hash()


def test_new_registration_uses_argon2_and_survives_key_rotation(access_db, api_client, monkeypatch):
    # Local/test self-registration does not need a seeded privileged account.
    result = api_client.post("/api/auth/register", json={
        "email": "migration@example.test", "username": "new", "password": PASSWORD,
        "role": "Management", "groups": ["Management"],
    })
    assert result.status_code == 200
    assert result.json()["user"]["groups"] == ["User"]
    encoded = access_db.scalar(select(DBUser.password_hash))
    assert encoded.startswith("$argon2id$")
    monkeypatch.setattr(settings, "JWT_SECRET", NEW_SECRET)
    monkeypatch.setattr(settings, "LEGACY_PASSWORD_SECRET", None)
    assert login(api_client).status_code == 200
    assert access_db.scalar(select(DBUser.password_hash)) == encoded
