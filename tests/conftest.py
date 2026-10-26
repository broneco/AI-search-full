import os
from pathlib import Path

# Import application settings in an isolated profile before any application module loads.
os.environ["APP_ENV"] = "test"

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.storage.db as db_module
from app.storage.models import Base


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Keep numbered, lock-protected pytest workspaces out of the repo root."""
    if config.option.basetemp is not None or "PYTEST_DEBUG_TEMPROOT" in os.environ:
        return
    root = Path(__file__).resolve().parents[1] / ".local" / "tmp" / "pytest"
    root.mkdir(parents=True, exist_ok=True)
    patch = pytest.MonkeyPatch()
    patch.setenv("PYTEST_DEBUG_TEMPROOT", str(root))
    config.add_cleanup(patch.undo)


# Create isolated in-memory SQLite engine for pytest
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@event.listens_for(test_engine, "connect")
def enable_sqlite_foreign_keys(connection, record):
    connection.execute("PRAGMA foreign_keys=ON")

# Globally patch engine & SessionLocal at test collection time
db_module.engine = test_engine
db_module.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_test_database():
    """Ensure Base tables exist in the in-memory SQLite instance for every test."""
    with test_engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
    yield


@pytest.fixture(scope="session", autouse=True)
def isolated_tenant_overlay(tmp_path_factory):
    """A test run must not inherit JSON left by previous developer/test runs."""
    import app.core.tenant_config as tenant_config
    original_root = tenant_config.LOCAL_TENANTS_DIR
    tenant_config.LOCAL_TENANTS_DIR = str(tmp_path_factory.mktemp("tenant-overlay"))
    try:
        yield
    finally:
        tenant_config.LOCAL_TENANTS_DIR = original_root


@pytest.fixture(scope="module")
def manager_headers():
    """A real server-side privileged account for existing API regression tests."""
    import uuid
    from app.core.config import settings
    from app.storage.models import DBUser
    from app.api.routes.auth import create_token, hash_password
    Base.metadata.create_all(test_engine)
    with TestingSessionLocal() as session:
        manager = DBUser(tenant_id=settings.TENANT_ID, email=f"manager-{uuid.uuid4().hex}@example.test",
                         username="Test manager", role="Management", groups=["User", "Management"],
                         password_hash=hash_password("test-only"))
        session.add(manager)
        session.commit()
        return {"Authorization": "Bearer " + create_token(manager)}
