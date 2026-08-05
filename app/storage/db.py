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


def ensure_database_exists() -> None:
    """Connect to default 'postgres' database and create target database if it does not exist."""
    base_url = (
        f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/postgres"
        f"?sslmode={settings.POSTGRES_SSLMODE}"
    )
    target_db = settings.POSTGRES_DB
    logger.info(f"Checking if database '{target_db}' exists on server...")
    try:
        temp_engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
        with temp_engine.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": target_db}
            )
            if not exists:
                logger.info(f"Database '{target_db}' does not exist. Creating database...")
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
                logger.info(f"Database '{target_db}' created successfully.")
        temp_engine.dispose()
    except Exception as e:
        logger.warning(f"Could not verify/create database '{target_db}': {e}")


def init_db() -> None:
    """Initialize database schemas, extensions, and tables.

    Specifically registers 'uuid-ossp' and 'vector' extensions, then creates tables and FTS indexes.
    """
    from app.storage.models import Base

    # Ensure target database exists on PostgreSQL server before main pool connects
    ensure_database_exists()

    logger.info("Initializing database and enabling vector extension...")
    with engine.begin() as conn:
        # Enable postgres extensions
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Create all tables declared on models Base
        Base.metadata.create_all(bind=conn)

        # Migration: Ensure tenant_id column exists on existing documents and chunks tables
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS tenant_id VARCHAR DEFAULT 'dolphin';"))
        conn.execute(text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tenant_id VARCHAR DEFAULT 'dolphin';"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_tenant_id ON documents(tenant_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_tenant_id ON chunks(tenant_id);"))
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

    # Seed demo user for tenant if missing
    try:
        import hashlib
        from app.storage.models import DBUser
        with SessionLocal() as db_session:
            demo_email = "user@dolphin.cz"
            existing = db_session.query(DBUser).filter(
                DBUser.tenant_id == settings.TENANT_ID,
                DBUser.email == demo_email
            ).first()
            if not existing:
                logger.info(f"Seeding demo user '{demo_email}' for tenant '{settings.TENANT_ID}'...")
                hashed = hashlib.sha256(f"password123:{settings.JWT_SECRET}".encode("utf-8")).hexdigest()
                demo_user = DBUser(
                    tenant_id=settings.TENANT_ID,
                    email=demo_email,
                    username="Dolphin Demo Uživatel",
                    password_hash=hashed,
                    role="User",
                    groups=["User", "Management", "Admin"],
                )
                db_session.add(demo_user)
                db_session.commit()
    except Exception as e:
        logger.warning(f"Could not seed demo user: {e}")


def clear_db() -> None:
    """Wipe database schemas and drop all registered tables."""
    from app.storage.models import Base

    logger.info("Wiping database tables clean...")
    with engine.begin() as conn:
        Base.metadata.drop_all(bind=conn)
    logger.info("Database wiped clean.")
