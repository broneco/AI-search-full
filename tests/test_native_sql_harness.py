"""Schema isolation guards, plus a real local SQL Server cleanup regression."""
import uuid

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateTable

from app.storage.models import Base, DBDocument
from native_sql_harness import isolated_schema_session, translate_native_sql
from test_search_access import access_engine


@pytest.mark.parametrize("schema", ["dbo", "ann_test_", "ann_test_" + "a" * 31,
    "ann_test_" + "A" * 32, "ann_test_x]; DROP SCHEMA dbo;--"])
def test_invalid_schema_rejected_before_connection(schema):
    with pytest.raises(ValueError):
        with isolated_schema_session(None, schema):
            pytest.fail("Must reject before opening any connection")


def test_textual_translation_preserves_values_and_scopes_only_vector_sql():
    schema = "ann_test_" + "a" * 32
    table = "chunk_vectors_" + "b" * 32
    sql = f"FROM VECTOR_SEARCH(TABLE = [dbo].[{table}] AS v) AS vs INNER JOIN chunks ON x INNER JOIN documents ON y WHERE EXISTS (SELECT 1 FROM document_acl_grants) AND EXISTS (SELECT 1 FROM chunk_acl_grants)"
    params = ("dbo." + table, "User", "secret'; DROP TABLE chunks;--")
    rewritten, unchanged = translate_native_sql(schema, sql, params)
    assert unchanged == params
    for name in (table, "chunks", "documents", "document_acl_grants", "chunk_acl_grants"):
        assert f"[{schema}].[{name}]" in rewritten
    catalog, bound = translate_native_sql(schema,
        "SELECT name FROM sys.vector_indexes vi WHERE object_id=OBJECT_ID(?)", ("dbo." + table,))
    assert catalog.startswith("SELECT name FROM sys.vector_indexes")
    assert bound == (schema + "." + table,)
    assert translate_native_sql(schema, "SELECT ?", params) == ("SELECT ?", params)


def test_orm_ddl_schema_translation_includes_foreign_keys():
    schema = "ann_test_" + "a" * 32
    statement = CreateTable(Base.metadata.tables["chunks"]).compile(
        dialect=mssql.dialect(), schema_translate_map={None: schema, "dbo": schema},
        render_schema_translate=True)
    assert f"{schema}.chunks" in str(statement)
    assert f"REFERENCES {schema}.documents" in str(statement)


def test_local_owned_schema_cleanup_preserves_dbo_even_on_failure(access_engine):
    if access_engine.dialect.name != "mssql":
        pytest.skip("Schema DDL isolation needs the local SQL Server")
    schema = "ann_test_" + uuid.uuid4().hex
    with access_engine.begin() as connection:
        connection.execute(text("CREATE TABLE dbo.isolation_sentinel (id int PRIMARY KEY)"))
        connection.execute(text("INSERT INTO dbo.isolation_sentinel VALUES (42)"))
    before = set(inspect(access_engine).get_table_names(schema="dbo"))
    with pytest.raises(RuntimeError, match="exercise cleanup"):
        with isolated_schema_session(access_engine, schema) as session:
            session.add(DBDocument(title="Test only", tenant_id="alpha", source_type="test",
                source_uri="test", document_type="test"))
            session.commit()
            assert session.scalar(select(DBDocument.title)) == "Test only"
            raise RuntimeError("exercise cleanup")
    assert schema not in inspect(access_engine).get_schema_names()
    assert set(inspect(access_engine).get_table_names(schema="dbo")) == before
    with access_engine.connect() as connection:
        assert connection.scalar(text("SELECT id FROM dbo.isolation_sentinel")) == 42


def test_existing_schema_is_never_adopted_or_cleaned(access_engine):
    if access_engine.dialect.name != "mssql":
        pytest.skip("Schema DDL isolation needs the local SQL Server")
    from sqlalchemy.exc import DBAPIError
    schema = "ann_test_" + uuid.uuid4().hex
    with access_engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA [{schema}]"))
        connection.execute(text(f"CREATE TABLE [{schema}].sentinel (id int)"))
    try:
        with pytest.raises(DBAPIError):
            with isolated_schema_session(access_engine, schema):
                pytest.fail("Must not adopt an existing schema")
        assert inspect(access_engine).get_table_names(schema=schema) == ["sentinel"]
    finally:
        with access_engine.begin() as connection:
            connection.execute(text(f"DROP TABLE [{schema}].sentinel"))
            connection.execute(text(f"DROP SCHEMA [{schema}]"))
