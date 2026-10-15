"""Real local T-SQL Unicode/FTS/tenant migration, never Azure."""
import pytest
from sqlalchemy import text

from test_search_access import access_engine, access_db, document, chunk
from migrate_search_schema import apply, capture


def prepare(db):
    doc = document(db, tenant="ju", title="Original")
    item = chunk(db, doc, content="Original text")
    item.tenant_id = "ju"
    foreign = document(db, tenant="ju ", title="Trailing space tenant")
    db.commit()
    return doc.document_id, item.chunk_id, foreign.document_id


def test_rollout_refuses_without_writer_guard(access_db):
    with pytest.raises(ValueError, match="Writers"):
        apply(access_db.bind, source="ju", target="ju-prod", expected_documents=0, expected_chunks=0)


def test_actual_tsql_migration_preserves_fts_and_exact_tenant(access_db):
    if access_db.bind.dialect.name != "mssql":
        pytest.skip("Actual Unicode/fulltext DDL requires MSSQL")
    doc_id, chunk_id, foreign_id = prepare(access_db)
    access_db.close()
    engine = access_db.bind
    # Create the same legacy VARCHAR schema and full-text settings as audited JHU.
    with engine.begin() as conn:
        for table, col, typ in (("documents", "title", "VARCHAR(512)"), ("chunks", "content", "VARCHAR(MAX)"),
                                ("chat_threads", "title", "VARCHAR(512)"), ("chat_messages", "content", "VARCHAR(MAX)")):
            conn.execute(text(f"ALTER TABLE dbo.[{table}] ALTER COLUMN [{col}] {typ} NOT NULL"))
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        has_fts = conn.scalar(text("SELECT FULLTEXTSERVICEPROPERTY('IsFullTextInstalled')"))
        if has_fts:
            conn.execute(text("IF NOT EXISTS(SELECT 1 FROM sys.fulltext_catalogs WHERE name='rollout_test') CREATE FULLTEXT CATALOG rollout_test"))
            pk = conn.scalar(text("SELECT name FROM sys.indexes WHERE object_id=OBJECT_ID('dbo.chunks') AND is_primary_key=1"))
            conn.execute(text(f"CREATE FULLTEXT INDEX ON dbo.chunks(content LANGUAGE 1033) KEY INDEX [{pk}] ON rollout_test WITH (CHANGE_TRACKING=AUTO,STOPLIST=SYSTEM)"))
    before = capture(engine)
    with pytest.raises(ValueError, match="counts"):
        apply(engine, source="ju", target="ju-prod", expected_documents=999, expected_chunks=1, writers_stopped=True)
    assert capture(engine) == before  # Restored FTS even when the guarded transaction fails.
    result = apply(engine, source="ju", target="ju-prod", expected_documents=1, expected_chunks=1, writers_stopped=True)
    assert result["documents_moved"] == result["chunks_moved"] == 1
    after = capture(engine)
    assert after["fulltext"] == before["fulltext"]
    assert after["language"] == (1033 if has_fts else None)
    assert all(c["type"] == "nvarchar" for c in after["columns"])
    with engine.begin() as conn:
        assert conn.scalar(text("SELECT tenant_id FROM dbo.documents WHERE document_id=:id"), {"id": doc_id}) == "ju-prod"
        assert conn.scalar(text("SELECT tenant_id FROM dbo.documents WHERE document_id=:id"), {"id": foreign_id}) == "ju "
        conn.execute(text("UPDATE dbo.chunks SET content=:value WHERE chunk_id=:id"), {"value": "Příliš žluťoučký kůň", "id": chunk_id})
        assert conn.scalar(text("SELECT content FROM dbo.chunks WHERE chunk_id=:id"), {"id": chunk_id}) == "Příliš žluťoučký kůň"
