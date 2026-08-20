import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger(__name__)

# Connection string
import logging
import urllib.parse
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

logger = logging.getLogger(__name__)

# Connection string setup
if settings.USE_AZURE_SQL:
    logger.info(f"Connecting to Azure SQL Database at {settings.AZURE_SQL_HOST}/{settings.AZURE_SQL_DB}...")
    import pyodbc
    available_drivers = pyodbc.drivers()
    selected_driver = settings.AZURE_SQL_DRIVER
    if selected_driver not in available_drivers:
        for candidate in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"]:
            if candidate in available_drivers:
                selected_driver = candidate
                break
    logger.info(f"Using ODBC driver: '{selected_driver}'")

    if settings.AZURE_SQL_PASSWORD:
        params = urllib.parse.quote_plus(
            f"DRIVER={{{selected_driver}}};"
            f"SERVER=tcp:{settings.AZURE_SQL_HOST},{settings.AZURE_SQL_PORT};"
            f"DATABASE={settings.AZURE_SQL_DB};"
            f"UID={settings.AZURE_SQL_USER};"
            f"PWD={settings.AZURE_SQL_PASSWORD};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Login Timeout=30;"
        )
        DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            fast_executemany=True,
        )
    else:
        logger.info("Using Azure Managed Identity / Entra ID authentication for Azure SQL...")
        params = urllib.parse.quote_plus(
            f"DRIVER={{{selected_driver}}};"
            f"SERVER=tcp:{settings.AZURE_SQL_HOST},{settings.AZURE_SQL_PORT};"
            f"DATABASE={settings.AZURE_SQL_DB};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Login Timeout=30;"
        )
        DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"
        from azure.identity import DefaultAzureCredential
        import struct

        credential = DefaultAzureCredential()

        def _get_azure_sql_token():
            raw_token = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
            return struct.pack(f"<I{len(raw_token)}s", len(raw_token), raw_token)

        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"attrs_before": {1256: _get_azure_sql_token}},
            fast_executemany=True,
        )
else:
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
    """Connect to default database and create target database if it does not exist (PostgreSQL only)."""
    if settings.USE_AZURE_SQL:
        # Azure SQL Databases are created via Azure Portal / ARM / Bicep
        return

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
    """Initialize database schemas, extensions, and tables."""
    from app.storage.models import Base

    if settings.USE_AZURE_SQL:
        logger.info("Initializing Azure SQL Database tables...")
        for attempt in range(1, 4):
            try:
                with engine.begin() as conn:
                    Base.metadata.create_all(bind=conn)
                logger.info("Azure SQL base tables initialized successfully.")
                break
            except Exception as e:
                logger.warning(f"Azure SQL table creation attempt {attempt}/3 failed: {e}")
                if attempt < 3:
                    time.sleep(5)
                else:
                    raise e

        # Attempt to create T-SQL Full-Text Search Catalog & Index
        try:
            autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
            with autocommit_engine.connect() as conn:
                conn.execute(text(
                    "IF NOT EXISTS (SELECT * FROM sys.fulltext_catalogs WHERE name = 'ftCatalog') "
                    "CREATE FULLTEXT CATALOG ftCatalog AS DEFAULT;"
                ))
                conn.execute(text("""
                    IF NOT EXISTS (SELECT * FROM sys.fulltext_indexes WHERE object_id = OBJECT_ID('chunks'))
                    BEGIN
                        DECLARE @pk_name NVARCHAR(128);
                        SELECT TOP 1 @pk_name = name FROM sys.indexes WHERE object_id = OBJECT_ID('chunks') AND is_primary_key = 1;
                        IF @pk_name IS NOT NULL
                        BEGIN
                            EXEC('CREATE FULLTEXT INDEX ON chunks(content) KEY INDEX [' + @pk_name + '] ON ftCatalog WITH STOPLIST = SYSTEM;');
                        END
                    END
                """))
            logger.info("Azure SQL Full-Text Search catalog and index verified.")
        except Exception as e:
            logger.warning(f"Note on Azure SQL Full-Text Search initialization: {e}")
    else:
        # PostgreSQL initialization
        ensure_database_exists()

        logger.info("Initializing database and enabling vector extension...")
        with engine.begin() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            Base.metadata.create_all(bind=conn)

            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS tenant_id VARCHAR DEFAULT 'dolphin';"))
            conn.execute(text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tenant_id VARCHAR DEFAULT 'dolphin';"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_tenant_id ON documents(tenant_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_tenant_id ON chunks(tenant_id);"))
        logger.info("Database base tables initialized successfully.")

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


def clear_document_data() -> None:
    """Clear chunks and documents data without dropping tables or user accounts."""
    from app.storage.models import DBChunk, DBDocument

    logger.info("Clearing document chunks and document metadata from database...")
    for attempt in range(1, 4):
        try:
            with SessionLocal() as db_session:
                db_session.query(DBChunk).delete()
                db_session.query(DBDocument).delete()
                db_session.commit()
            logger.info("Document chunks and document metadata cleared. User accounts preserved.")
            return
        except Exception as e:
            logger.warning(f"Clear document data attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(5)
            else:
                raise e
