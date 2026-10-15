"""Native full-text SQL contract plus opt-in real Azure word/ACL regressions."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import time
import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.retrieval.base import QueryContext
from app.retrieval.keyword import fulltext_condition, fulltext_statement
from app.retrieval.vector import VectorRetriever
from app.storage.ann_search import SearchExecutionError
from test_search_access import document, chunk
from test_vector_store import native_db


@pytest.mark.parametrize("query,expected", [
    ('Žádost o stipendium?', '"Žádost" OR "o" OR "stipendium"'),
    ('"NEAR((a,b),3)"; DROP TABLE chunks;--', '"NEAR" OR "a" OR "b" OR "3" OR "DROP" OR "TABLE" OR "chunks"'),
    ('needle needle %_[] !', '"needle"'),
    ('… %_\" *', None),
    ('studijní řád 2026', '"studijní" OR "řád" OR "2026"'),
])
def test_user_input_is_literal_unicode_words(query, expected):
    assert fulltext_condition(query) == expected


def test_fulltext_condition_rejects_oversize_instead_of_truncating():
    with pytest.raises(ValueError, match="4000"):
        fulltext_condition("a" * 4000)
    with pytest.raises(ValueError, match="4000"):
        fulltext_condition("𐐀" * 2000)


def test_fulltext_sql_filters_before_only_top_and_omits_legacy_vectors():
    ctx = QueryContext(query="stipendium", tenant_id="alpha", acl_groups=["HR"],
                       filters={"tag": "private'; DROP TABLE chunks;--", "freshness_filter": "latest"})
    statement = fulltext_statement(ctx, fulltext_condition(ctx.query), 30)
    compiled = statement.compile(dialect=mssql.dialect())
    sql = str(compiled)
    assert sql.count("TOP") == 1
    assert "CONTAINSTABLE([dbo].[chunks], [content], @fts_query)" in sql
    assert "DECLARE @fts_query NVARCHAR(4000) = CAST(:fts_condition AS NVARCHAR(4000))" in sql
    assert "JOIN" in sql and "ft.[KEY] = chunks.chunk_id" in sql
    assert "document_acl_grants" in sql and "chunk_acl_grants" in sql and "OPENJSON" in sql
    assert "FROM document_acl_grants, documents" not in sql
    assert "FROM chunk_acl_grants, chunks" not in sql
    assert "documents.tenant_id" in sql and "chunks.tenant_id" in sql
    assert "chunks.embedding" not in sql and "LIKE" not in sql
    assert "DROP TABLE" not in sql and "alpha" not in sql and '"stipendium"' not in sql
    assert compiled.params["fts_condition"] == '"stipendium"'
    assert "ORDER BY ft.[RANK] DESC, chunks.chunk_id" in sql


@pytest.mark.parametrize("sqlstate,code,status", [("HYT00", "keyword_timeout", 504), ("42000", "keyword_unavailable", 503)])
def test_cloud_keyword_error_never_falls_back_or_discloses_sql(monkeypatch, sqlstate, code, status):
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "azure_sql")
    monkeypatch.setattr("app.retrieval.vector.sql_query_timeout", lambda *a: nullcontext())
    db = Mock(bind=SimpleNamespace(dialect=mssql.dialect()))
    db.execute.side_effect = OperationalError("secret SQL", {}, Exception(sqlstate, "private details"))
    retriever = VectorRetriever(db)
    with pytest.raises(SearchExecutionError) as caught:
        retriever._get_fts_candidates("stipendium", 10, QueryContext(tenant_id="alpha", query="stipendium"))
    assert caught.value.code == code and caught.value.status_code == status
    assert "secret" not in str(caught.value) and "private" not in str(caught.value)
    assert db.execute.call_count == 1
    db.execute.reset_mock()
    assert retriever._get_fts_candidates("!?", 10, QueryContext(query="!?")) == []
    db.execute.assert_not_called()


def test_native_fulltext_czech_words_filters_and_no_global_cap(native_db):
    """Explicit native fixture only; all objects belong to the owned test scope."""
    db = native_db
    engine = db.get_bind()
    schema = engine.get_execution_options().get("schema_translate_map", {}).get(None, "dbo")
    assert schema == "dbo" or (schema.startswith("ann_test_") and len(schema) == 41)
    table = f"[{schema}].[chunks]"
    catalog = "keyword_test_" + uuid.uuid4().hex
    with engine.connect() as conn:
        key = conn.scalar(text("SELECT name FROM sys.indexes WHERE object_id=OBJECT_ID(:table) AND is_primary_key=1"), {"table": schema + ".chunks"})
    assert key and "]" not in key
    allowed = {"allowed_groups": ["User"]}
    denied = {"allowed_groups": ["HR"]}
    # Stronger ineligible matches must not consume a global lexical top K.
    for _ in range(12):
        chunk(db, document(db, acl=denied), acl=allowed, content="stipendium " * 20)
    chunk(db, document(db, acl=allowed), acl=denied, content="stipendium " * 20)
    chunk(db, document(db, tenant="beta", acl=allowed), acl=allowed, content="stipendium " * 20)
    chunk(db, document(db, acl=allowed, metadata={"faculty": "other"}), acl=allowed, content="stipendium " * 20)
    chunk(db, document(db, acl=allowed), acl=allowed, content="Other administrative agenda without the search term.")
    visible = chunk(db, document(db, acl=allowed, metadata={"faculty": "science"}), acl=allowed,
                    content="Žádost o stipendium a studijní řád vysoké školy. Scholarship rules.")
    expected = visible.chunk_id
    db.commit()
    db.expunge_all()
    created_catalog = False
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"CREATE FULLTEXT CATALOG [{catalog}]"))
            created_catalog = True
            conn.execute(text(f"CREATE FULLTEXT INDEX ON {table}(content LANGUAGE 1029) KEY INDEX [{key}] ON [{catalog}] WITH (CHANGE_TRACKING=AUTO, STOPLIST=SYSTEM)"))
        # Fresh FULL population is asynchronous. Wait boundedly for known text.
        ctx = QueryContext(query="stipendium", tenant_id="alpha", acl_groups=["User"], filters={"faculty": "science"})
        for attempt in range(60):
            rows = VectorRetriever(db)._get_fts_candidates(ctx.query, 1, ctx)
            if rows: break
            db.rollback()
            time.sleep(1)
        assert [row[0].chunk_id for row in rows] == [expected]
        # A corpus-wide common word can have rank 0; RANK is 0..1000.
        assert 0 <= rows[0][2] <= 1000
        assert "embedding" in inspect(rows[0][0]).unloaded
        # Do not assume the installed SYSTEM stoplist includes Czech 'a'.
        noise = db.scalar(text("SELECT COUNT(*) FROM sys.fulltext_system_stopwords WHERE language_id=1029 AND stopword=N'a'"))
        for query, matches in [("žádost", True), ("vysoké", True), ("scholarship", True), ("pendi", False), ("nenalezitelnyslovotest", False), ("a", not bool(noise))]:
            ctx.query = query
            found = VectorRetriever(db)._get_fts_candidates(query, 30, ctx)
            assert bool(found) == matches, query
            assert all(row[0].chunk_id == expected for row in found)
        ctx.filters = {"faculty": "unknown"}
        assert VectorRetriever(db)._get_fts_candidates("stipendium", 1, ctx) == []
    finally:
        db.rollback()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"IF EXISTS(SELECT 1 FROM sys.fulltext_indexes WHERE object_id=OBJECT_ID(N'{schema}.chunks')) DROP FULLTEXT INDEX ON {table}"))
            if created_catalog:
                conn.execute(text(f"DROP FULLTEXT CATALOG [{catalog}]"))
