import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.storage.models import Base


@pytest.fixture(autouse=True)
def setup_test_database(monkeypatch):
    """Force all pytest tests to execute against an isolated in-memory SQLite database.
    This guarantees that unit tests never touch or insert test users into the live Azure SQL database.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    import app.storage.db as db_module
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(db_module, "SessionLocal", TestingSessionLocal)

    with test_engine.begin() as conn:
        Base.metadata.create_all(bind=conn)

    yield
