"""Local ANN SQL/dispatch/error contracts and opt-in native Azure ANN integration."""
from dataclasses import replace
from contextlib import nullcontext
import math
import json
import os
import re
from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import bindparam, select, text, Unicode
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql.selectable import TextualSelect

import app.storage.ann_search as ann
from app.core.config import settings
from app.core.search_config import SearchConfigSchema
from app.retrieval.vector import VectorRetriever
from app.storage.models import DBChunk, DBChatThread, DBSearchIndex
from app.storage.vector_store import SearchIndexError, activate_index, provision_index, write_chunks, write_embeddings
from test_search_access import access_engine, access_db, api_client, user, create_token, document, context
from test_vector_store import PROFILE, vector_db, add_vectors, profile_index, native_db


@pytest.fixture
def anyio_backend():
    return "asyncio"


def native_index():
    index = DBSearchIndex(index_id=uuid.uuid4(), tenant_id="alpha", profile_id=PROFILE.profile_id,
        storage_kind="native", corpus_id="tenant-chunks-v1")
    index.table_name = f"chunk_vectors_{index.index_id.hex}"
    return index


def ready_index():
    return ann.AnnIndex("diskann_test", 3, "cosine", "DiskANN", False)


@pytest.mark.parametrize("dimensions", [2, 1536])
def test_ann_sql_keeps_all_filters_before_top_k_and_uses_v3_aliases(dimensions):
    profile = replace(PROFILE, dimensions=dimensions)
    index = native_index()
    index.profile_id = profile.profile_id
    query = [1.0] + [0.0] * (dimensions - 1)
    ctx = context(groups=("HR",), filters={"tag": "secret'; DROP TABLE chunks;--", "freshness_filter": "latest"})
    statement = ann.ann_statement(index, profile, ctx, query, 30)
    compiled = statement.compile(dialect=mssql.dialect())
    sql = str(compiled)
    assert sql.count("TOP") == 1 and "TOP_N" not in sql
    assert "WITH APPROXIMATE" in sql and "WITH (FORCE_ANN_ONLY)" in sql
    assert "SIMILAR_TO = @query_vector" in sql and f"DECLARE @query_vector VECTOR({dimensions})" in sql
    assert f"CAST(CAST(@query_json AS NVARCHAR(MAX)) AS VECTOR({dimensions}))" in sql
    if dimensions == 1536:
        assert len(compiled.params["query_json"]) > 4000
    assert "eligible.chunk_id = v.chunk_id" in sql and "v.input_revision = eligible.input_revision" in sql
    assert "INSERT INTO @eligible" in sql and "chunks.content_hash" in sql
    assert sql.index("WHERE ") < sql.index("SELECT TOP")
    assert "EXEC sys.sp_executesql" in sql and "SET NOCOUNT ON" in sql
    assert "document_acl_grants" in sql and "chunk_acl_grants" in sql and "OPENJSON" in sql
    assert "FROM document_acl_grants, documents" not in sql
    assert "FROM chunk_acl_grants, chunks" not in sql
    assert "documents.tenant_id" in sql and "chunks.tenant_id" in sql and "DATALENGTH" not in sql.upper().split("WHERE")[0]
    assert "ORDER BY vs.distance ASC" in sql
    assert "DROP TABLE" not in sql and "HR" not in sql and "alpha" not in sql
    assert compiled.params["top_k"] == 30 and compiled.params["query_json"] == json.dumps(query)
    assert "HR" in compiled.params.values()
    assert any("DROP TABLE" in str(value) for value in compiled.params.values())
    index.table_name = "chunks]; DROP TABLE users;--"
    with pytest.raises(SearchIndexError, match="catalog"):
        ann.ann_statement(index, profile, ctx, query, 30)


@pytest.mark.parametrize("version", [None, 1, 2])
def test_old_or_unknown_ann_version_is_rejected(version):
    with pytest.raises(SearchIndexError, match=">=3"):
        replace(ready_index(), version=version).require_ready()


def test_ann_preserves_tenant_and_expanded_acl_parameter_types():
    statement = ann.ann_statement(native_index(), PROFILE,
        context(groups=("User", "HR"), filters={"tag": "wanted"}), [1.0, 0.0], 30)
    compiled = statement.compile(dialect=mssql.dialect())
    tenants = [name for name, value in compiled.params.items() if value == "alpha"]
    groups = [name for name in compiled.params if name.startswith("group_name_")]
    metadata = [name for name, value in compiled.params.items() if value == json.dumps({"tag": "wanted"})]
    assert tenants and groups and metadata
    assert all(not isinstance(compiled.binds[name].type, Unicode) for name in tenants)
    assert all(isinstance(compiled.binds[name].type, Unicode) for name in groups + metadata)
    assert all(f"CAST(@{name} AS VARCHAR(MAX))" in str(compiled) for name in tenants)
    assert all(f"CAST(@{name} AS NVARCHAR(MAX))" in str(compiled) for name in groups + metadata)


def test_ann_tenant_parameter_byte_length_matches_varchar(access_db):
    if access_db.bind.dialect.name != "mssql":
        pytest.skip("Byte length binding needs the local SQL Server")
    compiled = ann._ann_batch(native_index(), PROFILE, context(), [1.0, 0.0], 30).compile(
        dialect=mssql.dialect())
    name = next(name for name, value in compiled.params.items() if value == "alpha")
    actual_expression = re.search(r"CAST\(:" + re.escape(name) + r" AS VARCHAR\(MAX\)\)", str(compiled))[0]
    probe = text("SELECT DATALENGTH(CAST(N'alpha' AS VARCHAR(255))), DATALENGTH(" + actual_expression + ")").bindparams(
        bindparam(name, "alpha", type_=compiled.binds[name].type))
    assert tuple(access_db.execute(probe).one()) == (5, 5)


def test_ann_textual_predicates_enforce_correlated_acl_and_tenant(vector_db):
    db = vector_db
    if db.bind.dialect.name != "mssql":
        pytest.skip("The actual textual ANN predicate is T-SQL")
    visible = document(db, acl={"allowed_groups": ["User"]}, metadata={"tag": "wanted"})
    hidden = document(db, title="Hidden document", acl={"allowed_groups": ["HR"]}, metadata={"tag": "wanted"})
    foreign = document(db, tenant="beta", title="Foreign document", metadata={"tag": "wanted"})
    write_chunks(db, [{"document_id": owner.document_id, "chunk_index": i, "content": f"Synthetic input {i}",
        "embedding": [1.0, 0.0], "metadata_json": {"scope": "selected"}, "security_acl": acl}
        for i, (owner, acl) in enumerate([(visible, {"allowed_groups": ["User"]}),
            (visible, {"allowed_groups": ["HR"]}), (hidden, {"allowed_groups": ["User"]}),
            (foreign, {"allowed_groups": ["User"]})])], PROFILE)
    db.commit()
    index = profile_index(db)
    native = DBSearchIndex(index_id=index.index_id, tenant_id=index.tenant_id, profile_id=index.profile_id,
        storage_kind="native", table_name=index.table_name, corpus_id=index.corpus_id)
    for groups, scope, expected in [(('User',), 'selected', {0}), (('Management',), 'selected', {0, 1, 2}),
                                    (('User',), 'absent', set())]:
        ctx = context(groups=groups, filters={"tag": "wanted", "scope": scope})
        actual = ann._ann_batch(native, PROFILE, ctx, [1.0, 0.0], 30)
        predicates = actual.text.split("\n        WHERE ", 1)[1].split(";", 1)[0]
        names = set(re.findall(r":([A-Za-z_][A-Za-z0-9_]*)\b", predicates))
        compiled = actual.compile(dialect=mssql.dialect())
        probe = text(f"SELECT chunks.chunk_index FROM [dbo].[{index.table_name}] AS v "
            "INNER JOIN chunks ON chunks.chunk_id=v.chunk_id "
            "INNER JOIN documents ON documents.document_id=chunks.document_id WHERE " + predicates)
        probe = probe.bindparams(*(compiled.binds[name] for name in names))
        assert set(db.scalars(probe).all()) == expected


def test_materialized_batch_preserves_nocount_and_bound_values(access_db):
    if access_db.bind.dialect.name != "mssql":
        pytest.skip("Scoped T-SQL SET options require SQL Server")
    db = access_db
    value = "Příliš žluťoučký '; DROP TABLE chunks;--"
    batch = text("SET NOCOUNT ON; DECLARE @allowed TABLE(value NVARCHAR(255)); "
                 "INSERT INTO @allowed VALUES(:value); SELECT value FROM @allowed;").bindparams(
                     bindparam("value", value, type_=Unicode(255)))
    try:
        for option in ("ON", "OFF"):
            db.execute(text("SET NOCOUNT " + option))
            before = db.scalar(text("SELECT @@OPTIONS & 512"))
            assert db.scalar(ann._scoped_batch(batch)) == value
            assert db.scalar(text("SELECT @@OPTIONS & 512")) == before
        with pytest.raises(OperationalError):
            with ann.sql_query_timeout(db, 1):
                db.execute(ann._scoped_batch(text("SET NOCOUNT ON; WAITFOR DELAY '00:00:03'; SELECT 1"))).all()
        db.rollback()
        assert db.scalar(text("SELECT @@OPTIONS & 512")) == 0
        assert db.scalar(text("SELECT 1")) == 1
    finally:
        db.rollback()
        db.execute(text("SET NOCOUNT OFF"))


@pytest.mark.parametrize("changes", [{"disabled": True}, {"metric": "dot"}, {"index_type": "unknown"}])
def test_disabled_or_incompatible_index_is_rejected(changes):
    with pytest.raises(SearchIndexError, match="enabled cosine"):
        replace(ready_index(), **changes).require_ready()


def test_catalog_reads_actual_column_version_and_rejects_ambiguous_metadata(monkeypatch):
    index = native_index()
    monkeypatch.setattr(ann, "index_profile", lambda session, selected: PROFILE)
    session = SimpleNamespace(bind=SimpleNamespace(dialect=mssql.dialect()), execute=Mock())
    session.execute.return_value.all.return_value = [("vec", "3", "COSINE", "DISKANN", False)]
    assert ann.ann_index_status(session, index).version == 3
    sql, params = session.execute.call_args.args
    assert "sys.index_columns" in str(sql) and "c.name = N'embedding'" in str(sql)
    assert params == {"table_name": "dbo." + index.table_name}
    session.execute.return_value.all.return_value = [("vec", "unrecognized", "COSINE", "DISKANN", False)]
    with pytest.raises(SearchIndexError, match=">=3"):
        ann.ann_index_status(session, index).require_ready()
    session.execute.return_value.all.return_value *= 2
    with pytest.raises(SearchIndexError, match="Ambiguous"):
        ann.ann_index_status(session, index)


def test_explicit_exact_does_not_need_ann_metadata_and_missing_ann_does_not_fallback(vector_db, monkeypatch):
    db = vector_db
    add_vectors(db, document(db), [[1.0, 0.0]])
    index = profile_index(db)
    activate_index(db, index)
    db.commit()
    diagnostics = {}
    metadata = Mock(side_effect=AssertionError("exact must not query ANN metadata"))
    monkeypatch.setattr(ann, "ann_index_status", metadata)
    assert len(ann.vector_candidates(db, context(), [1.0, 0.0], PROFILE, 30, diagnostics=diagnostics)) == 1
    assert diagnostics["storage"] == "local_json" and diagnostics["vector_mode"] == "exact"
    lookup = Mock(wraps=ann.active_index)
    monkeypatch.setattr(ann, "active_index", lookup)
    plan = ann.prepare_vector_search(db, "alpha", PROFILE, "exact")
    assert len(ann.vector_candidates(db, context(), [1.0, 0.0], PROFILE, 30, plan=plan)) == 1
    assert lookup.call_count == 1  # No second/third catalog pass after preflight.
    with pytest.raises(SearchIndexError, match="mismatch"):
        ann.vector_candidates(db, context(), [1.0, 0.0], PROFILE, 30, "ann", plan=plan)
    with pytest.raises(SearchIndexError, match="mismatch"):
        plan.validate("beta", PROFILE, "exact")
    metadata.side_effect = None
    metadata.return_value = None
    exact = Mock(side_effect=AssertionError("no fallback scan"))
    monkeypatch.setattr(ann, "exact_candidates", exact)
    with pytest.raises(SearchIndexError, match="missing"):
        ann.vector_candidates(db, context(), [1.0, 0.0], PROFILE, 30, "ann")
    exact.assert_not_called()
    with pytest.raises(SearchIndexError, match="profile"):
        ann.vector_candidates(db, context(), [1.0, 0.0], replace(PROFILE, model_revision="other"), 30, "ann")


@pytest.mark.parametrize("state,status,code", [("HYT00", 504, "search_timeout"), ("42000", 503, "search_unavailable")])
def test_sql_failure_is_controlled_and_never_retries_exact(monkeypatch, state, status, code):
    index = native_index()
    monkeypatch.setattr(ann, "active_index", lambda *args: index)
    monkeypatch.setattr(ann, "prepare_vector_search", lambda *args: ann.VectorSearchPlan(index, "ann", ready_index()))
    exact = Mock(side_effect=AssertionError("no retry"))
    monkeypatch.setattr(ann, "exact_candidates", exact)
    error = OperationalError("private SQL", {"password": "private"}, Exception(state, "private provider error"))
    session = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
                              execute=Mock(side_effect=error))
    with pytest.raises(ann.SearchExecutionError) as caught:
        ann.vector_candidates(session, context(), [1.0, 0.0], PROFILE, 30, "ann")
    assert caught.value.status_code == status and caught.value.code == code
    assert "private" not in str(caught.value)
    exact.assert_not_called()
    assert session.execute.call_count == 1


def test_create_ann_requires_coverage_minimum_and_validates_created_version(monkeypatch):
    index = native_index()
    connection = Mock()
    connection.execution_options.return_value = connection
    engine = SimpleNamespace(dialect=mssql.dialect(), connect=Mock(side_effect=lambda: nullcontext(connection)))
    session = SimpleNamespace(bind=engine, get_bind=lambda: engine, execute=Mock(),
                              in_transaction=lambda: False, rollback=Mock())
    monkeypatch.setattr(ann, "Session", lambda bind: nullcontext(session))
    monkeypatch.setattr(ann, "index_profile", lambda *args: PROFILE)
    metadata = Mock(return_value=None)
    monkeypatch.setattr(ann, "ann_index_status", metadata)
    for coverage in [(99, 99), (100, 101)]:
        monkeypatch.setattr(ann, "coverage", lambda *args: coverage)
        with pytest.raises(SearchIndexError, match="100"):
            ann.create_ann_index(session, index)
        session.execute.assert_not_called()
    monkeypatch.setattr(ann, "coverage", lambda *args: (100, 100))
    metadata.side_effect = [None, ready_index()]
    assert ann.create_ann_index(session, index).version == 3
    assert "MAXDOP = 1" in str(connection.execute.call_args.args[0])
    connection.execution_options.assert_called_with(isolation_level="AUTOCOMMIT")
    session.execute.assert_not_called()  # DDL never uses a Session transaction.
    metadata.side_effect = [None, replace(ready_index(), version=2)]
    with pytest.raises(SearchIndexError, match=">=3"):
        ann.create_ann_index(session, index)


def test_create_ann_refuses_flushed_caller_writes_without_committing(vector_db):
    db = vector_db
    doc = document(db)  # Already flushed, so session.new is empty but the write is uncommitted.
    document_id = doc.document_id
    with pytest.raises(SearchIndexError, match="caller transaction"):
        ann.create_ann_index(db, native_index())
    assert db.in_transaction()
    db.rollback()
    from app.storage.models import DBDocument
    assert db.get(DBDocument, document_id) is None


@pytest.mark.anyio
async def test_retriever_dispatch_diagnostics_and_empty_ann(vector_db, monkeypatch):
    db = vector_db
    visible = add_vectors(db, document(db), [[1.0, 0.0]])[0]
    hidden = add_vectors(db, document(db, acl={"allowed_groups": ["HR"]}, title="SECRET"), [[1.0, 0.0]])[0]
    index = profile_index(db)
    activate_index(db, index)
    db.commit()
    native = DBSearchIndex(index_id=index.index_id, tenant_id=index.tenant_id, profile_id=index.profile_id,
                          table_name=index.table_name, storage_kind="native", corpus_id=index.corpus_id)
    monkeypatch.setattr(ann, "active_index", lambda *args: native)
    monkeypatch.setattr(ann, "prepare_vector_search", lambda *args: ann.VectorSearchPlan(native, "ann", ready_index()))
    if db.bind.dialect.name == "sqlite":
        original_table = ann.vector_table
        monkeypatch.setattr(ann, "vector_table", lambda selected, profile: original_table(index, profile))
    original = db.execute
    winners = [(visible.chunk_id, 0.2, visible.content_hash), (hidden.chunk_id, 0.0, hidden.content_hash)]
    def dispatch(statement, *args, **kwargs):
        if isinstance(statement, TextualSelect):
            return SimpleNamespace(all=lambda: winners)
        return original(statement, *args, **kwargs)
    monkeypatch.setattr(db, "execute", dispatch)
    retriever = VectorRetriever(db)
    config = {"search_strategy": "vector", "vector_search_mode": "ann", "vector_limit": 30}
    results = await retriever.retrieve(context(), query_embedding=[1.0, 0.0], query_profile=PROFILE, search_config=config)
    assert [result.chunk_id for result in results] == [str(visible.chunk_id)]
    assert results[0].score == pytest.approx(0.8)
    assert retriever.diagnostics["ann_index_version"] == 3
    assert retriever.diagnostics["vector_candidates"] == 1
    # A fresh embedding created between ANN and hydration cannot validate an old distance.
    visible.content = "New input after ANN selection"
    db.flush()
    write_embeddings(db, index, PROFILE, [{"chunk_id": visible.chunk_id, "input_revision": visible.content_hash,
                                         "embedding": [0.0, 1.0]}])
    db.commit()
    assert await retriever.retrieve(context(), query_embedding=[1.0, 0.0], query_profile=PROFILE, search_config=config) == []
    winners.clear()
    assert await retriever.retrieve(context(), query_embedding=[1.0, 0.0], query_profile=PROFILE, search_config=config) == []
    assert retriever.diagnostics["vector_candidates"] == 0


def test_api_ann_preflight_fails_before_models_and_thread_creation(access_db, api_client, monkeypatch):
    from app.api.routes import chat
    from test_search_access import prepare_chat_index
    normal = user(access_db)
    prepare_chat_index(access_db, chat, monkeypatch)
    embed, llm = AsyncMock(), AsyncMock()
    monkeypatch.setattr(chat.embedding_provider, "embed_query", embed)
    monkeypatch.setattr(chat.llm_provider, "generate", llm)
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={"vector_search_mode": "ann"}))
    before = len(access_db.scalars(select(DBChatThread)).all())
    response = api_client.post("/api/chat", json={"query": "needle"}, headers={"Authorization": "Bearer " + create_token(normal)})
    assert response.status_code == 503 and "exact" in response.text
    assert len(access_db.scalars(select(DBChatThread)).all()) == before
    embed.assert_not_awaited()
    llm.assert_not_awaited()


def test_search_mode_schema_defaults_to_exact_and_rejects_auto_fallback():
    assert SearchConfigSchema().vector_search_mode == "exact"
    assert SearchConfigSchema(vector_search_mode="ann").vector_search_mode == "ann"
    with pytest.raises(ValueError):
        SearchConfigSchema(vector_search_mode="auto")
    with pytest.raises(ValueError):
        SearchConfigSchema(vector_query_timeout_seconds=0)


def test_query_timeout_is_restored_after_error():
    driver = SimpleNamespace(timeout=0)
    session = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="mssql")),
        connection=lambda: SimpleNamespace(connection=SimpleNamespace(driver_connection=driver)))
    with pytest.raises(RuntimeError):
        with ann.sql_query_timeout(session, 2):
            assert driver.timeout == 2
            raise RuntimeError("operation failed")
    assert driver.timeout == 0
    with pytest.raises(SearchIndexError):
        with ann.sql_query_timeout(session, True):
            pass


@pytest.mark.anyio
async def test_ann_cli_mutation_checks_target_before_access():
    import migrate_search_vectors as migration
    arguments = SimpleNamespace(create=False, reembed=False, proven_legacy=False, activate=False,
        create_ann=True, ann_status=False, index=str(uuid.uuid4()), expect_host="wrong-test-host",
        expect_db="wrong-test-db", expect_tenant="wrong-test-tenant")
    with pytest.raises(SearchIndexError, match="must match"):
        await migration.run(arguments)


def test_local_odbc_timeout_and_restore(vector_db):
    db = vector_db
    if db.bind.dialect.name != "mssql":
        pytest.skip("ODBC statement timeout requires local SQL Server")
    connection = db.connection()
    driver = connection.connection.driver_connection
    previous = driver.timeout
    with pytest.raises(OperationalError) as caught:
        with ann.sql_query_timeout(db, 1):
            db.execute(text("WAITFOR DELAY '00:00:03'"))
    assert ann.execution_error(caught.value, "test").status_code == 504
    if not connection.invalidated:
        assert driver.timeout == previous
    db.rollback()
    assert db.scalar(text("SELECT 1")) == 1
    assert db.connection().connection.driver_connection.timeout == previous


@pytest.mark.parametrize("mode", ["exact", "ann"])
def test_api_reports_selected_mode_and_safe_diagnostics(access_db, api_client, monkeypatch, mode):
    from app.api.routes import chat
    from test_search_access import prepare_chat_index
    normal = user(access_db)
    prepare_chat_index(access_db, chat, monkeypatch)
    monkeypatch.setattr(chat, "prepare_vector_search", Mock(return_value=ready_index() if mode == "ann" else None))
    monkeypatch.setattr(chat.embedding_provider, "embed_query", AsyncMock(return_value=[1.0, 0.0]))
    monkeypatch.setattr(chat.llm_provider, "generate", AsyncMock(return_value="No evidence"))
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={"vector_search_mode": mode}))
    diagnostic = {"vector_mode": mode, "ann_index_version": 3 if mode == "ann" else None,
                  "vector_candidates": 0, "retrieval_latency_ms": 3}
    monkeypatch.setattr(chat, "VectorRetriever", lambda db: SimpleNamespace(
        retrieve=AsyncMock(return_value=[]), diagnostics=diagnostic))
    response = api_client.post("/api/chat", json={"query": "needle"}, headers={"Authorization": "Bearer " + create_token(normal)})
    assert response.status_code == 200
    assert response.json()["metadata"]["retrieval_strategy"] == "hybrid_" + mode
    assert response.json()["metadata"]["search_diagnostics"] == diagnostic


def test_api_timeout_is_504_and_does_not_call_llm(access_db, api_client, monkeypatch):
    from app.api.routes import chat
    from test_search_access import prepare_chat_index
    normal = user(access_db)
    prepare_chat_index(access_db, chat, monkeypatch)
    monkeypatch.setattr(chat.embedding_provider, "embed_query", AsyncMock(return_value=[1.0, 0.0]))
    llm = AsyncMock()
    monkeypatch.setattr(chat.llm_provider, "generate", llm)
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={"vector_search_mode": "exact"}))
    monkeypatch.setattr(chat, "VectorRetriever", lambda db: SimpleNamespace(
        retrieve=AsyncMock(side_effect=ann.SearchExecutionError("search_timeout", "Vector search timed out.", 504))))
    response = api_client.post("/api/chat", json={"query": "needle"}, headers={"Authorization": "Bearer " + create_token(normal)})
    assert response.status_code == 504 and response.headers["X-Search-Error-Code"] == "search_timeout"
    assert isinstance(response.json()["detail"], str)  # Existing frontend renders a string.
    llm.assert_not_awaited()


@pytest.fixture
def native_ann_db(request):
    if os.getenv("RUN_NATIVE_ANN_TESTS") != "1":
        pytest.skip("Native ANN is deferred to the explicit Azure slice 5 gate")
    return request.getfixturevalue("native_db")


def test_native_ann_filters_and_transactional_lifecycle(native_ann_db):
    """Real v3+ SQL execution, not a recall/performance benchmark."""
    db = native_ann_db
    profile = replace(PROFILE, dimensions=1536)
    query = [1.0] + [0.0] * 1535
    index = provision_index(db, "alpha", profile, native=True)
    doc = document(db, metadata={"tag": "wanted"})
    rows = [{"document_id": doc.document_id, "chunk_index": i, "content": f"Diverse input {i}",
        "embedding": [math.cos(i / 100), math.sin(i / 100)] + [0.0] * 1534,
        "metadata_json": {"scope": "selected" if i == 140 else "other"},
        "security_acl": {"allowed_groups": ["User"]}} for i in range(141)]
    write_chunks(db, rows, profile)
    hidden = document(db, title="SECRET", acl={"allowed_groups": ["HR"]}, metadata={"tag": "wanted"})
    write_chunks(db, [{"document_id": hidden.document_id, "chunk_index": 0, "content": "SECRET",
        "embedding": query, "metadata_json": {"scope": "selected"}, "security_acl": {"allowed_groups": ["User"]}},
        {"document_id": doc.document_id, "chunk_index": 142, "content": "PRIVATE CHUNK",
        "embedding": query, "metadata_json": {"scope": "selected"}, "security_acl": {"allowed_groups": ["HR"]}}], profile)
    provision_index(db, "beta", profile, native=True)
    foreign = document(db, tenant="beta", title="FOREIGN", metadata={"tag": "wanted"})
    write_chunks(db, [{"document_id": foreign.document_id, "chunk_index": 0, "content": "FOREIGN",
        "embedding": query, "metadata_json": {"scope": "selected"}}], profile)
    activate_index(db, index)
    db.commit()
    status = ann.create_ann_index(db, index)
    assert status.version >= 3
    print(json.dumps({"native_ann_index_version": status.version, "metric": status.metric,
                      "enabled": not status.disabled, "dimensions": profile.dimensions}))
    db.commit()
    selected = context(filters={"tag": "wanted", "scope": "selected"})
    reference = ann.vector_candidates(db, selected, query, profile, 30, "exact")
    assert len(reference) == 1 and reference[0][0].chunk_index == 140
    winners = ann.vector_candidates(db, selected, query, profile, 30, "ann")
    print(json.dumps({"native_exact_selected": len(reference), "native_ann_selected": len(winners)}))
    if not winners:
        raw = db.execute(ann.ann_statement(index, profile, selected, query, 30)).all()
        print(json.dumps({"native_ann_raw_selected": len(raw),
            "raw_id_type": type(raw[0][0]).__name__ if raw else None,
            "orm_id_type": type(reference[0][0].chunk_id).__name__,
            "raw_id_matches_exact": raw[0][0] == reference[0][0].chunk_id if raw else None,
            "raw_revision_matches_exact": raw[0][2] == reference[0][0].content_hash if raw else None}))
        broad = db.execute(ann.ann_statement(index, profile, context(), query, 30)).all()
        print(json.dumps({"native_ann_raw_broad": len(broad)}))
        standalone = text(f"""DECLARE @q VECTOR(1536)=CAST(CAST(:q AS NVARCHAR(MAX)) AS VECTOR(1536));
            SELECT TOP (30) WITH APPROXIMATE v.chunk_id, vs.distance
            FROM VECTOR_SEARCH(TABLE=[dbo].[{index.table_name}] AS v, COLUMN=embedding,
                SIMILAR_TO=@q, METRIC='cosine') AS vs WITH (FORCE_ANN_ONLY)
            ORDER BY vs.distance""").bindparams(bindparam("q", json.dumps(query), type_=Unicode()))
        print(json.dumps({"native_ann_raw_without_joins": len(db.execute(standalone).all())}))
    assert len(winners) == 1 and winners[0][0].chunk_index == 140
    assert ann.vector_candidates(db, context(filters={"scope": "absent"}), query, profile, 30, "ann") == []
    assert len(ann.vector_candidates(db, context(), query, profile, 30, "ann")) == 30
    best = winners[0][0]
    best.content = "Updated input"
    db.flush()
    write_embeddings(db, index, profile, [{"chunk_id": best.chunk_id, "input_revision": best.content_hash, "embedding": query}])
    db.rollback()
    assert ann.vector_candidates(db, selected, query, profile, 30, "ann")[0][0].content != "Updated input"
    best.content = "Committed update"
    db.flush()
    assert ann.vector_candidates(db, selected, query, profile, 30, "ann") == []
    write_embeddings(db, index, profile, [{"chunk_id": best.chunk_id, "input_revision": best.content_hash, "embedding": query}])
    db.commit()
    assert ann.vector_candidates(db, selected, query, profile, 30, "ann")[0][3] == pytest.approx(1)
    db.delete(best)
    db.commit()
    assert ann.vector_candidates(db, selected, query, profile, 30, "ann") == []
