import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.storage.db as db_module
from app.storage.models import Base

# Create isolated in-memory SQLite engine for pytest
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Globally patch engine & SessionLocal at test collection time
db_module.engine = test_engine
db_module.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_test_database():
    """Ensure Base tables exist in the in-memory SQLite instance for every test."""
    with test_engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
    yield
