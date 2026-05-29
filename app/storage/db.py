import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger(__name__)

# Connection string
DATABASE_URL = (
    f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    f"?sslmode={settings.POSTGRES_SSLMODE}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 15,
    },
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency generator for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database schemas, extensions, and tables.

    Specifically registers 'uuid-ossp' and 'vector' extensions, then creates tables and FTS indexes.
    """
    from app.storage.models import Base

    logger.info("Initializing database and enabling vector extension...")
    with engine.begin() as conn:
        # Enable postgres extensions
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Create all tables declared on models Base
        Base.metadata.create_all(bind=conn)
    logger.info("Database base tables initialized successfully.")

    # Create the GIN index for full-text search with a Czech language stemming or 'simple' fallback
    # Check if 'cs' is in pg_ts_config first to avoid raising database exceptions and log warnings
    cs_exists = False
    try:
        with engine.connect() as conn:
            cs_exists = conn.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_ts_config WHERE cfgname = 'cs');"))
    except Exception as e:
        logger.warning(f"Could not query pg_ts_config catalog: {e}")

    cfg = "cs" if cs_exists else "simple"
    logger.info(f"Creating GIN full-text search index on chunks.content using '{cfg}' configuration...")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin(to_tsvector('{cfg}', content));")
            )
        logger.info(f"Created GIN full-text index using '{cfg}' configuration.")
    except Exception as e:
        logger.error(f"Failed to create GIN full-text index: {e}")

    logger.info("Database initialization complete.")


def clear_db() -> None:
    """Wipe database schemas and drop all registered tables."""
    from app.storage.models import Base

    logger.info("Wiping database tables clean...")
    with engine.begin() as conn:
        Base.metadata.drop_all(bind=conn)
    logger.info("Database wiped clean.")
