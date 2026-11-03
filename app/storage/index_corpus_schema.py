"""Explicit additive schema upgrade shared by the CLI and local initialization."""
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

SETTINGS_COLUMNS = {"settings_origin": "VARCHAR(16)", "current_index_id": "UNIQUEIDENTIFIER",
                    "owner_index_id": "UNIQUEIDENTIFIER", "base_revision": "INTEGER"}


def migrate(connection: Connection) -> None:
    from app.storage.models import DBIndexSettings, DBIndexDocument
    if "corpus_id" not in {col["name"] for col in inspect(connection).get_columns("chunks")}:
        connection.exec_driver_sql("ALTER TABLE chunks ADD corpus_id VARCHAR(64) NULL")
    DBIndexSettings.__table__.create(connection, checkfirst=True)
    DBIndexDocument.__table__.create(connection, checkfirst=True)
    columns = {c["name"] for c in inspect(connection).get_columns("index_settings")}
    for name, sql_type in SETTINGS_COLUMNS.items():
        if name not in columns:
            # UUID values use SQLAlchemy's portable CHAR storage on SQLite.
            if connection.dialect.name == "sqlite" and sql_type == "UNIQUEIDENTIFIER":
                sql_type = "CHAR(32)"
            connection.exec_driver_sql(f"ALTER TABLE index_settings ADD {name} {sql_type} NULL")
