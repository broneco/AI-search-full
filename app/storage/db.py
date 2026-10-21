
import time
import logging
import urllib.parse
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.retrieval.filters import exact_value

logger = logging.getLogger(__name__)

# Ensure Key Vault and default settings are resolved before database engine initialization
settings.set_environment_defaults()


def _select_odbc_driver() -> str:
    import pyodbc

    available_drivers = pyodbc.drivers()
    selected_driver = settings.AZURE_SQL_DRIVER
    if selected_driver not in available_drivers:
        selected_driver = next(
            (candidate for candidate in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"] if candidate in available_drivers),
            selected_driver,
        )
    if selected_driver not in available_drivers:
        raise RuntimeError("Install an ODBC driver for SQL Server on this computer (recommended: Microsoft ODBC Driver 17 or 18).")
    return selected_driver

# Connection string setup
if settings.USE_AZURE_SQL:
    target_label = "Azure SQL Database" if settings.DATABASE_BACKEND == "azure_sql" else "local SQL Server"
    logger.info(f"Connecting to {target_label} at {settings.AZURE_SQL_HOST}/{settings.AZURE_SQL_DB}...")
    selected_driver = _select_odbc_driver()
    logger.info(f"Using ODBC driver: '{selected_driver}'")

    if settings.AZURE_SQL_PASSWORD or settings.DATABASE_BACKEND == "sqlserver":
        trust_server_certificate = "yes" if settings.DATABASE_BACKEND == "sqlserver" else "no"
        params = urllib.parse.quote_plus(
            f"DRIVER={{{selected_driver}}};"
            f"SERVER=tcp:{settings.AZURE_SQL_HOST},{settings.AZURE_SQL_PORT};"
            f"DATABASE={settings.AZURE_SQL_DB};"
            f"UID={settings.AZURE_SQL_USER};"
            f"PWD={settings.AZURE_SQL_PASSWORD};"
            f"Encrypt=yes;"
            f"TrustServerCertificate={trust_server_certificate};"
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
        from sqlalchemy import event

        credential = DefaultAzureCredential()

        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            fast_executemany=True,
        )

        @event.listens_for(engine, "do_connect")
        def provide_token(dialect, conn_rec, cargs, cparams):
            raw_token = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
            token_bytes = struct.pack(f"<I{len(raw_token)}s", len(raw_token), raw_token)
            cparams["attrs_before"] = {1256: token_bytes}
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
    """Ensure local databases exist; Azure SQL databases are provisioned outside the app."""
    if settings.DATABASE_BACKEND == "azure_sql":
        return

    if settings.DATABASE_BACKEND == "sqlserver":
        import pyodbc

        driver = _select_odbc_driver()
        database_literal = (settings.AZURE_SQL_DB or "ai_search_local").replace("'", "''")
        database_identifier = (settings.AZURE_SQL_DB or "ai_search_local").replace("]", "]]" )
        connection_string = (
            f"DRIVER={{{driver}}};SERVER=tcp:{settings.AZURE_SQL_HOST},{settings.AZURE_SQL_PORT};"
            f"DATABASE=master;UID={settings.AZURE_SQL_USER};PWD={settings.AZURE_SQL_PASSWORD};"
            "Encrypt=yes;TrustServerCertificate=yes;Login Timeout=30;"
        )
        connection = pyodbc.connect(connection_string, autocommit=True)
        try:
            cursor = connection.cursor()
            cursor.execute(
                f"IF DB_ID(N'{database_literal}') IS NULL CREATE DATABASE [{database_identifier}]"
            )
        finally:
            connection.close()
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


def ensure_local_unicode_columns(connection) -> None:
    """Upgrade existing local text columns before full-text index verification.

    Cloud schemas require a separate human migration. Names/types are fixed,
    never supplied by a request or a tenant configuration.
    """
    if settings.APP_ENV != "local" or settings.DATABASE_BACKEND != "sqlserver":
        return
    if settings.AZURE_SQL_HOST not in {"localhost", "127.0.0.1", "::1"} or settings.AZURE_SQL_DB != "ai_search_local":
        raise ValueError("Unicode startup migration is limited to loopback / ai_search_local.")
    for table, column, target in (
        ("documents", "title", "NVARCHAR(512)"),
        ("chunks", "content", "NVARCHAR(MAX)"),
        ("chat_threads", "title", "NVARCHAR(512)"),
        ("chat_messages", "content", "NVARCHAR(MAX)"),
    ):
        current = connection.scalar(text(
            "SELECT TYPE_NAME(system_type_id) FROM sys.columns "
            "WHERE object_id = OBJECT_ID(:table) AND name = :column"
        ), {"table": f"dbo.{table}", "column": column})
        if current is None or current == "nvarchar":
            continue
        if table == "chunks":
            connection.execute(text(
                "IF EXISTS (SELECT 1 FROM sys.fulltext_indexes WHERE object_id = OBJECT_ID('dbo.chunks')) "
                "DROP FULLTEXT INDEX ON dbo.chunks"
            ))
        connection.execute(text(f"ALTER TABLE dbo.[{table}] ALTER COLUMN [{column}] {target} NOT NULL"))
        logger.info("Local Unicode column verified: %s.%s", table, column)


def init_db() -> None:
    """Initialize database schemas, extensions, and tables."""
    from app.storage.models import Base

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
    elif settings.USE_AZURE_SQL:
        if settings.DATABASE_BACKEND == "sqlserver":
            ensure_database_exists()
        logger.info("Initializing Azure SQL Database tables...")
        for attempt in range(1, 4):
            try:
                with engine.begin() as conn:
                    if settings.DATABASE_BACKEND == "azure_sql":
                        tables = [table for table in Base.metadata.sorted_tables
                                  if table.name not in {"document_acl_grants", "chunk_acl_grants",
                                      "embedding_profiles", "search_indexes", "active_search_indexes", "model_access_policies", "tenant_model_registry", "model_descriptions", "model_runtime_settings"}]
                        Base.metadata.create_all(bind=conn, tables=tables)
                    else:
                        Base.metadata.create_all(bind=conn)
                        ensure_local_unicode_columns(conn)
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

    if settings.DATABASE_BACKEND != "azure_sql":
        from app.storage.acl import rebuild_acl_grants
        with SessionLocal.begin() as session:
            rebuild_acl_grants(session)

    # Public demo credentials are only appropriate for isolated local/test runs.
    if settings.APP_ENV not in {"local", "test"}:
        logger.info("Database initialization complete; cloud demo seeding disabled.")
        return

    # Seed default demo users if current TENANT_ID has no users yet
    try:
        from app.storage.models import DBUser
        from app.core.passwords import hash_password
        with SessionLocal() as db_session:
            user_count = db_session.query(DBUser).filter(DBUser.tenant_id == settings.TENANT_ID).count()
            if user_count == 0:
                logger.info(f"Seeding default demo users for tenant '{settings.TENANT_ID}'...")
                admin_hashed = hash_password("DolphinAdmin26")
                admin = DBUser(
                    tenant_id=settings.TENANT_ID,
                    email="admin@dolphin.cz",
                    username="Dolphin Admin",
                    password_hash=admin_hashed,
                    role="Admin",
                    groups=["Management", "HR", "IT", "User", "Admin"],
                )
                demo1 = DBUser(
                    tenant_id=settings.TENANT_ID,
                    email="user@dolphin.cz",
                    username="Dolphin Demo Uživatel",
                    password_hash=hash_password("password123"),
                    role="User",
                    groups=["User"],
                )
                demo2 = DBUser(
                    tenant_id=settings.TENANT_ID,
                    email="user@dolphinconsulting.cz",
                    username="Dolphin Demo Uživatel",
                    password_hash=hash_password("password123"),
                    role="User",
                    groups=["User"],
                )
                db_session.add_all([admin, demo1, demo2])
                db_session.commit()
                logger.info(f"Default demo users seeded for tenant '{settings.TENANT_ID}'.")
    except Exception as e:
        logger.warning(f"Could not seed default demo user: {e}")

    logger.info("Database initialization complete.")


def clear_db(preserve_users: bool = True) -> None:
    """Clear database tables. By default, preserves user accounts, credentials, and security roles."""
    from app.storage.models import DBChunk, DBDocument, DBChatMessage, DBChatThread, DBUser

    logger.info("Clearing document data from database...")
    for attempt in range(1, 4):
        try:
            with SessionLocal() as db_session:
                db_session.query(DBChunk).delete()
                db_session.query(DBDocument).delete()
                if not preserve_users:
                    logger.warning("EXPLICIT HARD RESET: Deleting chat messages, chat threads, and user accounts...")
                    db_session.query(DBChatMessage).delete()
                    db_session.query(DBChatThread).delete()
                    db_session.query(DBUser).delete()
                db_session.commit()
            logger.info("Database cleanup completed. User accounts preserved." if preserve_users else "Hard reset completed.")
            return
        except Exception as e:
            logger.warning(f"Database cleanup attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(5)
            else:
                raise e


def clear_document_data(tenant_id: Optional[str] = None) -> None:
    """Clear chunks and documents data without dropping tables or user accounts.
    If tenant_id is supplied, only document data belonging to that tenant scope is cleared.
    """
    from app.storage.models import DBChunk, DBDocument

    logger.info(f"Clearing document chunks and document metadata for tenant '{tenant_id or 'all'}'...")
    for attempt in range(1, 4):
        try:
            with SessionLocal() as db_session:
                if tenant_id:
                    from sqlalchemy import select
                    subq = select(DBDocument.document_id).where(exact_value(DBDocument.tenant_id, tenant_id, engine.dialect.name))
                    db_session.query(DBChunk).filter(DBChunk.document_id.in_(subq)).delete(synchronize_session=False)
                    db_session.query(DBDocument).filter(exact_value(DBDocument.tenant_id, tenant_id, engine.dialect.name)).delete(synchronize_session=False)
                else:
                    db_session.query(DBChunk).delete()
                    db_session.query(DBDocument).delete()
                db_session.commit()
            logger.info(f"Document chunks and document metadata cleared for '{tenant_id or 'all'}'. User accounts preserved.")
            return
        except Exception as e:
            logger.warning(f"Clear document data attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(5)
            else:
                raise e
