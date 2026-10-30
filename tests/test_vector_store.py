"""Profile-isolated exact search, transactional lifecycle and native SQL gate."""
from dataclasses import asdict, replace
import json
import os
from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine, select, delete, inspect, text
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session

from test_search_access import access_db, access_engine, document, context
from app.core.config import Settings, settings
from app.providers.embeddings import EmbeddingProfile
from app.ingestion.index_backfill import backfill_index
from app.retrieval.vector import VectorRetriever
from app.storage.models import Base, DBChunk, DBDocument, DBSearchIndex, DBEmbeddingProfile, DBActiveSearchIndex
from app.storage.vector_store import (NativeVector, SearchIndexError, provision_index, vector_table,
    write_chunks, write_embeddings, revision, activate_index, active_index, coverage, exact_candidates, exact_statement)

PROFILE = EmbeddingProfile("test-model", "1", 2)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def vector_db(access_db, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "sqlserver" if access_db.bind.dialect.name == "mssql" else "postgresql")
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_MODEL", PROFILE.model_id)
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_MODEL_REVISION", PROFILE.model_revision)
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_DIMENSIONS", PROFILE.dimensions)
    return access_db


def add_vectors(db, doc, vectors, profile=PROFILE):
    rows = [{"document_id": doc.document_id, "chunk_index": i, "content": f"unique text {i} in {doc.title}",
             "embedding": vector, "security_acl": {"allowed_groups": ["User"]}} for i, vector in enumerate(vectors)]
    write_chunks(db, rows, profile)
    return db.scalars(select(DBChunk).where(DBChunk.document_id == doc.document_id).order_by(DBChunk.chunk_index)).all()


def profile_index(db, profile=PROFILE):
    return db.scalar(select(DBSearchIndex).where(DBSearchIndex.tenant_id == "alpha", DBSearchIndex.profile_id == profile.profile_id))


def exercise_exact_search(db, *, native=False):
    if native:
        provision_index(db, "alpha", PROFILE, native=True)
        provision_index(db, "beta", PROFILE, native=True)
    target_doc = document(db, title="Target", metadata={"tag": "wanted"})
    rows = add_vectors(db, target_doc, [[0.0, 1.0]] * 625 + [[1.0, 0.0]])
    best = rows[-1]
    hidden_doc = document(db, title="SECRET", acl={"allowed_groups": ["HR"]}, metadata={"tag": "wanted"})
    add_vectors(db, hidden_doc, [[1.0, 0.0]])
    chunk_restricted = document(db, title="Hidden chunk", metadata={"tag": "wanted"})
    restricted = add_vectors(db, chunk_restricted, [[1.0, 0.0]])[0]
    restricted.security_acl = {"allowed_groups": ["HR"]}
    wrong_meta = document(db, title="Wrong metadata", metadata={"tag": "wrong"})
    add_vectors(db, wrong_meta, [[1.0, 0.0]])
    foreign = document(db, tenant="beta", title="Foreign", metadata={"tag": "wanted"})
    add_vectors(db, foreign, [[1.0, 0.0]])
    db.commit()
    index = profile_index(db)
    assert coverage(db, index) == (629, 629)
    activate_index(db, index)
    db.commit()
    ctx = context(filters={"tag": "wanted"})
    matches = exact_candidates(db, ctx, [1.0, 0.0], PROFILE, 30)
    assert len(matches) == 30 and matches[0][0].chunk_id == best.chunk_id
    assert matches[0][3] == pytest.approx(1.0)
    assert all(row[1].title == "Target" for row in matches)
    assert exact_candidates(db, context(filters={"tag": "missing"}), [1.0, 0.0], PROFILE, 30) == []
    assert len(exact_candidates(db, context(filters={"title": "Target", "chunk_index": 625}), [1.0, 0.0], PROFILE, 30)) == 1
    with pytest.raises(SearchIndexError, match="profile"):
        exact_candidates(db, ctx, [1.0, 0.0], replace(PROFILE, model_revision="2"), 30)
    with pytest.raises(ValueError, match="dimensions"):
        exact_candidates(db, ctx, [1.0], PROFILE, 30)
    return index, best


def test_all_eligible_chunks_rank_before_top_k(vector_db):
    exercise_exact_search(vector_db)


def test_profiles_lifecycle_invalidation_cascade_and_rollback(vector_db):
    db = vector_db
    doc = document(db)
    item = add_vectors(db, doc, [[1.0, 0.0]])[0]
    first = profile_index(db)
    second_profile = replace(PROFILE, model_id="another-model")
    second = provision_index(db, "alpha", second_profile, native=False)
    write_embeddings(db, second, second_profile, [{"chunk_id": item.chunk_id,
        "input_revision": item.content_hash, "embedding": [0.0, 1.0]}])
    third_profile = replace(PROFILE, dimensions=3)
    third = provision_index(db, "alpha", third_profile, native=False)
    write_embeddings(db, third, third_profile, [{"chunk_id": item.chunk_id,
        "input_revision": item.content_hash, "embedding": [1.0, 0.0, 0.0]}])
    activate_index(db, first)
    db.commit()
    assert exact_candidates(db, context(), [1.0, 0.0], PROFILE, 30)[0][3] == pytest.approx(1)
    item.content = "Changed current input"
    db.flush()
    assert all(coverage(db, index) == (0, 1) for index in (first, second, third))
    assert exact_candidates(db, context(), [1.0, 0.0], PROFILE, 30) == []
    db.rollback()
    assert all(coverage(db, index) == (1, 1) for index in (first, second, third))
    old_ids = db.scalars(select(DBChunk.chunk_id)).all()
    with pytest.raises(ValueError):
        add_vectors(db, doc, [[1.0]], PROFILE)
    db.rollback()
    assert db.scalars(select(DBChunk.chunk_id)).all() == old_ids
    db.delete(item)
    db.commit()
    assert all(db.execute(select(vector_table(index, profile))).all() == []
        for index, profile in ((first, PROFILE), (second, second_profile), (third, third_profile)))


@pytest.mark.anyio
async def test_explicit_backfill_requires_provenance_and_preserves_json(vector_db):
    db = vector_db
    doc = document(db)
    legacy = DBChunk(document_id=doc.document_id, chunk_index=0, content="old input", embedding=[0.0, 1.0])
    db.add(legacy)
    db.commit()
    index = provision_index(db, "alpha", PROFILE, native=False)
    db.commit()
    with pytest.raises(SearchIndexError, match="Incomplete"):
        activate_index(db, index)
    with pytest.raises(SearchIndexError, match="unproven"):
        await backfill_index(db, index, proven_legacy=True)
    provider = SimpleNamespace(profile=PROFILE, embed_documents=AsyncMock(return_value=[[1.0, 0.0]]))
    assert await backfill_index(db, index, provider=provider) == 1
    assert await backfill_index(db, index, provider=provider) == 0
    assert legacy.embedding == [0.0, 1.0]  # Historical JSON was not overwritten.
    provider.embed_documents.assert_awaited_once_with(["old input"])
    activate_index(db, index)
    db.commit()
    assert exact_candidates(db, context(), [1.0, 0.0], PROFILE, 1)[0][3] == pytest.approx(1)


@pytest.mark.anyio
async def test_backfill_rechecks_as_one_batch_without_scalar_selects(vector_db):
    from sqlalchemy import event
    db = vector_db
    doc = document(db)
    for i in range(5):
        db.add(DBChunk(document_id=doc.document_id, chunk_index=i, content=f"batch input {i}", embedding=[0.0, 1.0]))
    db.commit()
    index = provision_index(db, "alpha", PROFILE, native=False)
    db.commit()
    statements = []
    def track(conn, cursor, statement, params, context, many):
        sql = statement.lower().replace("\n", " ")
        if sql.lstrip().startswith("select") and "from chunks" in sql:
            statements.append(sql)
    event.listen(db.bind, "before_cursor_execute", track)
    provider = SimpleNamespace(profile=PROFILE, embed_documents=AsyncMock(return_value=[[1.0, 0.0]] * 5))
    try:
        assert await backfill_index(db, index, provider=provider, batch_size=5) == 5
    finally:
        event.remove(db.bind, "before_cursor_execute", track)
    assert len(statements) <= 4  # initial batch, recheck, repository guard, end-of-input
    assert all("chunks.embedding" not in sql for sql in statements[:2])


@pytest.mark.anyio
async def test_backfill_bulk_recheck_rejects_changed_input(vector_db):
    from sqlalchemy import update, func
    db = vector_db
    doc = document(db)
    item = DBChunk(document_id=doc.document_id, chunk_index=0, content="before", embedding=[0.0, 1.0])
    db.add(item)
    db.commit()
    item_id = item.chunk_id
    index = provision_index(db, "alpha", PROFILE, native=False)
    db.commit()
    async def embed(texts):
        db.execute(update(DBChunk).where(DBChunk.chunk_id == item_id).values(content="changed"))
        db.commit()
        return [[1.0, 0.0]]
    provider = SimpleNamespace(profile=PROFILE, embed_documents=embed)
    with pytest.raises(SearchIndexError, match="changed during"):
        await backfill_index(db, index, provider=provider)
    assert db.scalar(select(func.count()).select_from(vector_table(index, PROFILE))) == 0


def test_catalog_rejects_identifier_injection_and_mutable_profiles(vector_db):
    db = vector_db
    index = provision_index(db, "alpha", PROFILE, native=False)
    db.commit()
    db.refresh(index)
    index.table_name = "x]; DROP TABLE chunks; --"
    with pytest.raises(SearchIndexError, match="catalog"):
        vector_table(index, PROFILE)
    db.rollback()
    stored = db.get(DBEmbeddingProfile, PROFILE.profile_id)
    stored.definition = {**stored.definition, "model_revision": "modified"}
    with pytest.raises(SearchIndexError, match="immutable"):
        db.flush()
    db.rollback()


@pytest.mark.anyio
async def test_pipeline_replacement_rolls_back_document_chunks_and_vectors(vector_db, tmp_path, monkeypatch):
    import app.ingestion.pipeline as pipeline_module
    import app.storage.vector_store as store
    db = vector_db
    file = tmp_path / "atomic-replacement.txt"
    file.write_text("New replacement text", encoding="utf-8")
    old = document(db, title="Old document")
    old.source_uri, old.checksum = "file://atomic-replacement.txt", "old-checksum"
    previous = add_vectors(db, old, [[1.0, 0.0]])[0]
    old_doc_id, old_chunk_id = old.document_id, previous.chunk_id
    db.commit()
    provider = SimpleNamespace(profile=PROFILE, embed_documents=AsyncMock(return_value=[[0.2, 0.8]]))
    monkeypatch.setattr(pipeline_module, "create_embedding_provider", lambda: provider)
    pipeline = pipeline_module.IngestionPipeline(db)
    pipeline.blob_provider = SimpleNamespace(is_configured=lambda: False)
    pipeline.splitter = SimpleNamespace(enrich_with_summary=False, chunk_size=1500, chunk_overlap=0, split_pages=lambda pages: [
        SimpleNamespace(content="New replacement text", index=0, page_number=1)])
    write_original = store.write_chunks
    def fail_after_write(session, rows, profile):
        write_original(session, rows, profile)
        raise RuntimeError("failed after all vector writes")
    monkeypatch.setattr(store, "write_chunks", fail_after_write)
    with pytest.raises(RuntimeError, match="after all vector"):
        await pipeline.ingest_file(str(file))
    db.expire_all()
    assert db.get(DBDocument, old_doc_id) is not None
    assert db.get(DBChunk, old_chunk_id) is not None
    assert coverage(db, profile_index(db)) == (1, 1)
    assert len(db.scalars(select(DBDocument)).all()) == 1


@pytest.mark.parametrize("dimensions", [2, 1536])
def test_native_exact_sql_has_filters_and_only_final_top_k(dimensions):
    profile = replace(PROFILE, dimensions=dimensions)
    query = [1.0] + [0.0] * (dimensions - 1)
    index = DBSearchIndex(index_id=uuid.uuid4(), tenant_id="alpha", profile_id=profile.profile_id,
        storage_kind="native", corpus_id="tenant-chunks-v1")
    index.table_name = f"chunk_vectors_{index.index_id.hex}"
    compiled = exact_statement(index, profile, context(filters={"tag": "wanted"}), query, 30).compile(
        dialect=mssql.dialect(), compile_kwargs={"render_postcompile": True})
    sql = str(compiled)
    assert sql.count("TOP") == 1 and "VECTOR_DISTANCE" in sql and f"VECTOR({dimensions})" in sql
    assert "CAST(CAST(" in sql and " AS NVARCHAR(max))" in sql
    assert json.loads(compiled.params["query_json"]) == query
    if dimensions == 1536:
        assert len(compiled.params["query_json"]) > 4000
    assert "document_acl_grants" in sql and "chunk_acl_grants" in sql
    assert "FROM document_acl_grants, documents" not in sql
    assert "FROM chunk_acl_grants, chunks" not in sql
    assert "OPENJSON" in sql and "input_revision = chunks.content_hash" in sql
    assert sql.count("INNER HASH JOIN") == 2
    assert "OPTION (HASH JOIN)" not in sql  # Nested JSON/ACL joins keep their own plans.
    assert "WITH APPROXIMATE" not in sql and "VECTOR_SEARCH" not in sql
    assert 600 not in compiled.params.values() and "wanted" not in sql  # UUIDs may contain the digits 600.
    with pytest.raises(SearchIndexError, match="1998"):
        NativeVector(1999)


def test_native_write_preserves_long_json_through_max_text_cast():
    profile = replace(PROFILE, dimensions=1536)
    index = DBSearchIndex(index_id=uuid.uuid4(), tenant_id="alpha", profile_id=profile.profile_id,
        storage_kind="native", corpus_id="tenant-chunks-v1")
    index.table_name = f"chunk_vectors_{index.index_id.hex}"
    chunk = DBChunk(chunk_id=uuid.uuid4(), tenant_id="alpha", content_hash="current-input")
    session = SimpleNamespace(
        get=Mock(return_value=DBEmbeddingProfile(profile_id=profile.profile_id, definition=asdict(profile))),
        execute=Mock(side_effect=[SimpleNamespace(all=lambda: [(chunk.chunk_id, chunk)]), None, None]))
    query = [1.0] + [0.0] * 1535
    write_embeddings(session, index, profile, [{"chunk_id": chunk.chunk_id,
        "input_revision": chunk.content_hash, "embedding": query}])
    statement, rows = session.execute.call_args.args
    sql = str(statement.compile(dialect=mssql.dialect()))
    assert "CAST(CAST(" in sql and " AS NVARCHAR(max)) AS VECTOR(1536))" in sql
    assert rows[0]["input_revision"] == chunk.content_hash
    assert len(rows[0]["vector_json"]) > 4000
    assert json.loads(rows[0]["vector_json"]) == query


@pytest.fixture
def native_db(monkeypatch):
    """Human-provisioned EMPTY Azure test DB, explicitly expected host/name."""
    if os.getenv("RUN_NATIVE_SQL_TESTS") != "1":
        pytest.skip("Native VECTOR requires an explicitly provisioned Azure test database")
    isolated = os.getenv("NATIVE_SQL_ISOLATED_SCHEMA")
    if isolated:
        from native_sql_harness import azure_cli_engine, dbo_counts, isolated_schema_session, validate_test_schema
        validate_test_schema(isolated)
        if os.getenv("NATIVE_SQL_ALLOW_EXISTING") != "1":
            raise ValueError("Isolated schema writes require NATIVE_SQL_ALLOW_EXISTING=1 approval.")
        # Explicit non-secret target; do not inherit tenant env or use Key Vault.
        host = os.environ["NATIVE_SQL_EXPECT_HOST"]
        database = os.environ["NATIVE_SQL_EXPECT_DB"]
        engine = azure_cli_engine(host, database)
        monkeypatch.setattr(settings, "DATABASE_BACKEND", "azure_sql")
        monkeypatch.setattr(settings, "TENANT_ID", "alpha")
        try:
            before = dbo_counts(engine)
            try:
                with isolated_schema_session(engine, isolated) as session:
                    yield session
            finally:
                after = dbo_counts(engine)
                assert before == after, "Existing dbo table inventory/counts changed during the test"
                assert isolated not in inspect(engine).get_schema_names(), "Test schema cleanup incomplete"
                print(json.dumps({"isolated_schema_cleaned": isolated, "dbo_counts_unchanged": True,
                                  "dbo_counts": after}))
        finally:
            engine.dispose()
        return
    from sqlalchemy.engine import URL
    local = Settings(_env_file=".env.native-test", APP_ENV="test", DATABASE_BACKEND="azure_sql")
    assert local.AZURE_SQL_HOST == os.environ["NATIVE_SQL_EXPECT_HOST"]
    assert local.AZURE_SQL_DB == os.environ["NATIVE_SQL_EXPECT_DB"]
    assert "test" in local.AZURE_SQL_DB.lower()
    engine = create_engine(URL.create("mssql+pyodbc", query={"odbc_connect":
        f"DRIVER={{{local.AZURE_SQL_DRIVER}}};SERVER=tcp:{local.AZURE_SQL_HOST},{local.AZURE_SQL_PORT};"
        f"DATABASE={local.AZURE_SQL_DB};UID={local.AZURE_SQL_USER};PWD={local.AZURE_SQL_PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=no;Login Timeout=30;"}))
    assert inspect(engine).get_table_names() == [], "Use a dedicated empty test database"
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "azure_sql")
    monkeypatch.setattr(settings, "TENANT_ID", "alpha")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        # Only tables in this initially empty test DB, created by this fixture.
        with Session(engine) as session:
            for index in session.scalars(select(DBSearchIndex)).all():
                from app.storage.vector_store import index_profile
                vector_table(index, index_profile(session, index)).drop(session.connection())
            session.commit()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_native_vector_end_to_end(native_db):
    index, best = exercise_exact_search(native_db, native=True)
    large_profile = replace(PROFILE, dimensions=1536)
    large_index = provision_index(native_db, "alpha", large_profile, native=True)
    vector = [1.0] + [0.0] * 1535
    write_embeddings(native_db, large_index, large_profile, [{"chunk_id": best.chunk_id,
        "input_revision": best.content_hash, "embedding": vector}])
    high_dimensional = native_db.execute(exact_statement(large_index, large_profile,
        context(filters={"tag": "wanted"}), vector, 30)).all()
    assert len(high_dimensional) == 1 and float(high_dimensional[0][2]) == pytest.approx(1.0)
    with pytest.raises(SearchIndexError, match="Incomplete"):
        activate_index(native_db, large_index)
    native_db.commit()
    best.content = "Updated native input"
    native_db.flush()
    assert coverage(native_db, index) == (628, 629)
    write_embeddings(native_db, index, PROFILE, [{"chunk_id": best.chunk_id,
        "input_revision": best.content_hash, "embedding": [0.2, 0.8]}])
    assert coverage(native_db, index) == (629, 629)
    native_db.rollback()
    assert exact_candidates(native_db, context(filters={"tag": "wanted"}), [1.0, 0.0], PROFILE, 1)[0][0].chunk_id == best.chunk_id
    native_db.delete(best)
    native_db.commit()
    assert coverage(native_db, index) == (628, 628)
