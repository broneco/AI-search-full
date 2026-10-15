"""Explicit native integration support; never used by the application runtime."""
from contextlib import contextmanager
import json
import re
import shutil
import struct
import subprocess

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session

from app.storage.models import Base


def validate_test_schema(schema: str) -> str:
    if not re.fullmatch(r"ann_test_[0-9a-f]{32}", schema):
        raise ValueError("Use a fresh ann_test_<32 lowercase hex> schema, never dbo.")
    return schema


def translate_native_sql(schema, statement, parameters):
    """Translate only production textual vector SQL; ORM/DDL uses schema_translate_map."""
    validate_test_schema(schema)
    if "CONTAINSTABLE(" in statement:
        statement = statement.replace("CONTAINSTABLE([dbo].[chunks],", f"CONTAINSTABLE([{schema}].[chunks],")
        statement = re.sub(r"\b(FROM|JOIN) (chunks|documents|document_acl_grants|chunk_acl_grants)\b",
            lambda match: f"{match[1]} [{schema}].[{match[2]}]", statement)
    statement = re.sub(r"\[dbo\]\.\[(chunk_vectors_[0-9a-f]{32})\]",
        lambda match: f"[{schema}].[{match[1]}]", statement)
    if "FROM VECTOR_SEARCH(" in statement:
        statement = re.sub(r"\b(FROM|JOIN) (chunks|documents)\b",
            lambda match: f"{match[1]} [{schema}].[{match[2]}]", statement)
        # Grant subqueries are textual too; retain the original table aliases.
        statement = re.sub(r"\bFROM (document_acl_grants|chunk_acl_grants)\b",
            lambda match: f"FROM [{schema}].[{match[1]}]", statement)
    if "FROM sys.vector_indexes vi" in statement:
        def translate(value):
            if isinstance(value, str) and re.fullmatch(r"dbo\.chunk_vectors_[0-9a-f]{32}", value):
                return schema + value[3:]
            return value
        if isinstance(parameters, dict):
            parameters = {key: translate(value) for key, value in parameters.items()}
        else:
            parameters = tuple(translate(value) for value in parameters)
    return statement, parameters


def azure_cli_engine(host: str, database: str, port: int = 1433):
    """Existing Entra identity only; tokens stay in memory, no Key Vault dependency."""
    import pyodbc
    if not re.fullmatch(r"[a-z0-9-]+\.database\.windows\.net", host):
        raise ValueError("Expected an Azure SQL host.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", database) or not 1 <= port <= 65535:
        raise ValueError("Invalid database/port.")
    driver = next((name for name in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server")
                   if name in pyodbc.drivers()), None)
    cli = shutil.which("az.cmd") or shutil.which("az")
    if driver is None or cli is None:
        raise RuntimeError("An installed SQL ODBC driver and authenticated Azure CLI are required.")

    def connect():
        result = subprocess.run([cli, "account", "get-access-token", "--resource",
            "https://database.windows.net/", "--query", "accessToken", "--output", "json",
            "--only-show-errors"], capture_output=True, text=True, timeout=45)
        if result.returncode:
            raise RuntimeError("Azure CLI could not acquire a SQL token; no token output was logged.")
        token = json.loads(result.stdout).encode("utf-16-le")
        packed = struct.pack("<I", len(token)) + token
        return pyodbc.connect(f"DRIVER={{{driver}}};SERVER=tcp:{host},{port};DATABASE={database};"
            "Encrypt=yes;TrustServerCertificate=no;APP=AI Search isolated native integration;",
            attrs_before={1256: packed}, timeout=30)

    return create_engine("mssql+pyodbc://", creator=connect, hide_parameters=True)


def dbo_counts(engine):
    """Only aggregate counts; never read existing document text or user data."""
    with engine.connect() as connection:
        names = inspect(connection).get_table_names(schema="dbo")
        return {name: connection.scalar(text(
            "SELECT COUNT_BIG(*) FROM [dbo].[" + name.replace("]", "]]") + "]"))
            for name in names}


@contextmanager
def isolated_schema_session(engine, schema: str):
    """Create and clean only a newly owned schema; existing dbo tables are untouched."""
    validate_test_schema(schema)
    scoped = engine.execution_options(schema_translate_map={None: schema, "dbo": schema})
    created = False

    def translate(connection, cursor, statement, parameters, context, executemany):
        return translate_native_sql(schema, statement, parameters)

    event.listen(scoped, "before_cursor_execute", translate, retval=True)
    try:
        with engine.begin() as connection:
            # CREATE fails if this name already exists; never adopt or clean an old schema.
            connection.execute(text(f"CREATE SCHEMA [{schema}]"))
        created = True
        Base.metadata.create_all(scoped)
        with Session(scoped) as session:
            yield session
    finally:
        try:
            if created:
                names = inspect(engine).get_table_names(schema=schema)
                known = {table.name for table in Base.metadata.tables.values()}
                vectors = [name for name in names if re.fullmatch(r"chunk_vectors_[0-9a-f]{32}", name)]
                if set(names) - known - set(vectors):
                    raise RuntimeError("Unexpected objects in owned test schema; manual cleanup required.")
                with engine.begin() as connection:
                    for name in vectors:
                        connection.execute(text(f"DROP TABLE [{schema}].[{name}]"))
                Base.metadata.drop_all(scoped)
                with engine.begin() as connection:
                    connection.execute(text(f"DROP SCHEMA [{schema}]"))
        finally:
            event.remove(scoped, "before_cursor_execute", translate)
