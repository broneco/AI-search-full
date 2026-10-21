"""Search eligibility, authoritative identity and transactional ACL regression tests."""
import datetime
import os
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, insert, select, text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.api.identity import Principal
from app.api.routes.auth import create_token, hash_password
from app.core.config import Settings, settings
from app.main import app
from app.retrieval.access import ACCESS_POLICY, history_is_visible, visible_document
from app.retrieval.base import QueryContext
from app.retrieval.vector import VectorRetriever
from app.storage.acl import insert_chunks, rebuild_acl_grants
from app.storage.models import Base, DBChunk, DBChunkACL, DBChatMessage, DBDocument, DBDocumentACL, DBUser


@pytest.fixture(scope="module", params=["sqlite", "mssql"])
def access_engine(request):
    if request.param == "sqlite":
        engine = create_engine("sqlite://", poolclass=StaticPool,
                               connect_args={"check_same_thread": False})
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
        yield engine
        engine.dispose()
        return
    if os.getenv("RUN_LOCAL_SQL_TESTS") != "1":
        pytest.skip("Set RUN_LOCAL_SQL_TESTS=1 to verify against local SQL Server")
    import pyodbc
    from sqlalchemy.engine import URL
    local = Settings(_env_file=".env.local", APP_ENV="local", DATABASE_BACKEND="sqlserver")
    assert local.AZURE_SQL_HOST in {"127.0.0.1", "localhost"}
    drivers = pyodbc.drivers()
    driver = next(d for d in (local.AZURE_SQL_DRIVER, "ODBC Driver 18 for SQL Server",
                              "ODBC Driver 17 for SQL Server") if d in drivers)
    test_database = "ai_search_acl_test_" + uuid.uuid4().hex
    assert test_database.startswith("ai_search_acl_test_") and len(test_database) == 51
    connection = (f"DRIVER={{{driver}}};SERVER=tcp:{local.AZURE_SQL_HOST},{local.AZURE_SQL_PORT};"
                  f"UID={local.AZURE_SQL_USER};PWD={local.AZURE_SQL_PASSWORD};"
                  "Encrypt=yes;TrustServerCertificate=yes;Login Timeout=5;")
    master = pyodbc.connect(connection + "DATABASE=master;", autocommit=True)
    master.execute(f"CREATE DATABASE [{test_database}]")
    engine = create_engine(URL.create("mssql+pyodbc", query={
        "odbc_connect": connection + f"DATABASE={test_database};"
    }))
    try:
        yield engine
    finally:
        engine.dispose()
        # Only the uniquely named database created by this fixture is removed.
        master.execute(f"ALTER DATABASE [{test_database}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        master.execute(f"DROP DATABASE [{test_database}]")
        master.close()


@pytest.fixture
def access_db(access_engine, monkeypatch):
    monkeypatch.setattr(settings, "TENANT_ID", "alpha")
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "USE_AZURE_SQL", access_engine.dialect.name == "mssql")
    import re
    for name in inspect(access_engine).get_table_names():
        if re.fullmatch(r"chunk_vectors_[0-9a-f]{32}", name):
            with access_engine.begin() as connection:
                connection.execute(text(f"DROP TABLE [{name}]"))
    Base.metadata.drop_all(access_engine)
    Base.metadata.create_all(access_engine)
    with Session(access_engine) as session:
        yield session
        session.rollback()


def document(db, *, tenant="alpha", acl=None, metadata=None, title="Visible"):
    doc = DBDocument(tenant_id=tenant, title=title, source_type="local", source_uri=title,
                     document_type="test", language="cs", security_acl=acl, metadata_json=metadata)
    db.add(doc)
    db.flush()
    return doc


def chunk(db, doc, *, index=0, acl=None, metadata=None, content="needle content", embedding=None):
    item = DBChunk(document_id=doc.document_id, chunk_index=index, content=content,
                   security_acl=acl, metadata_json=metadata, embedding=embedding or [1.0, 0.0],
                   page_number=1, section_title="section")
    db.add(item)
    db.flush()
    return item


def context(*, groups=("User",), filters=None):
    return QueryContext(query="needle", tenant_id="alpha", acl_groups=list(groups), filters=filters or {})


def candidates(db, branch, ctx, limit=1):
    retriever = VectorRetriever(db)
    if branch == "vector":
        return retriever._get_vector_candidates([1.0, 0.0], limit, ctx)
    return retriever._get_fts_candidates("needle", limit, ctx)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_hybrid_score_addition_normalizes_database_rank(access_db):
    """Run actual SQL rank -> filters -> fusion; MSSQL rank is a Decimal."""
    from decimal import Decimal
    import json

    db = access_db
    strongest = chunk(db, document(db), content="needle " * 3)
    chunk(db, document(db), content="needle second", embedding=[0.0, 1.0])
    db.commit()
    retriever = VectorRetriever(db)
    raw = retriever._get_fts_candidates("needle", 10, context())
    if db.bind.dialect.name == "mssql":
        assert isinstance(raw[0][2], Decimal)
    filtered = retriever._apply_filters(raw, context(), [1.0, 0.0])
    assert all(isinstance(item.metadata["fts_rank"], float) for item in filtered)
    # Also cover a driver Decimal with no keyword match (zero) at the boundary.
    zero = retriever._apply_filters([(strongest, strongest.document, Decimal("0"))], context(), None)
    assert zero[0].metadata["fts_rank"] == 0.0
    results = await retriever.retrieve(context(), query_embedding=[1.0, 0.0], search_config={
        "search_strategy": "hybrid", "hybrid_strategy": "score_addition",
        "vector_weight": 0.6, "keyword_weight": 0.4,
        "score_threshold": 0, "context_expansion": "none",
    })
    assert results[0].chunk_id == str(strongest.chunk_id)
    assert results[0].score == pytest.approx(1.0)
    json.dumps([item.model_dump() for item in results])


@pytest.fixture
def local_demo_config(access_db, monkeypatch):
    """Keep the seeder's local guard; inject this fixture's isolated engine."""
    for name, value in {
        "APP_ENV": "local", "DATABASE_BACKEND": "sqlserver", "AZURE_SQL_HOST": "127.0.0.1",
        "AZURE_SQL_DB": "ai_search_local", "AZURE_OPENAI_EMBEDDING_DIMENSIONS": 2,
        "AZURE_OPENAI_ENDPOINT": None, "AZURE_OPENAI_API_KEY": None,
    }.items():
        monkeypatch.setattr(settings, name, value)
    return sessionmaker(bind=access_db.bind)


def demo_provider():
    from types import SimpleNamespace
    from app.providers.factory import create_embedding_profile
    return SimpleNamespace(profile=create_embedding_profile(), embed_documents=AsyncMock(
        return_value=[[1.0, 0.0], [0.0, 1.0]]
    ), embed_query=AsyncMock(side_effect=AssertionError("Documents must use document mode")))


@pytest.mark.anyio
async def test_local_demo_is_idempotent_public_and_restores_pdfs(access_db, local_demo_config, tmp_path):
    from pathlib import Path
    from app.ingestion.local_demo import seed_local_demo
    db = access_db
    user_doc = document(db, title="Existing user upload")
    chunk(db, user_doc)
    db.commit()
    provider = demo_provider()
    assert await seed_local_demo(local_demo_config, provider=provider, data_root=tmp_path) == 2
    db.expire_all()
    docs = db.scalars(select(DBDocument).where(DBDocument.document_type == "local_demo")).all()
    assert len(docs) == 2
    assert {doc.title for doc in docs} == {"Aurora: Organizace studia", "Aurora: Služby pro studenty"}
    assert all(doc.language == "cs" and len(doc.chunks) == 1 for doc in docs)
    assert any("studijní oddělení" in doc.chunks[0].content for doc in docs)
    assert db.get(DBDocument, user_doc.document_id) is not None
    original_ids = {doc.chunks[0].chunk_id for doc in docs}
    assert len(candidates(db, "keyword", context(filters={"document_type": "local_demo"}), 10)) == 0
    retriever = VectorRetriever(db)
    kw = retriever._get_fts_candidates("kreditů", 10, context(filters={"document_type": "local_demo"}))
    assert kw  # Czech text is preserved and public ACLs are projected.
    provider.embed_documents.assert_awaited_once()
    provider.embed_query.assert_not_awaited()
    Path(docs[0].source_uri).unlink()
    assert await seed_local_demo(local_demo_config, provider=provider, data_root=tmp_path) == 0
    assert Path(docs[0].source_uri).is_file()
    db.expire_all()
    assert {doc.chunks[0].chunk_id for doc in docs} == original_ids
    provider.embed_documents.assert_awaited_once()


@pytest.mark.anyio
async def test_local_demo_reembeds_only_missing_doc_and_changed_profile(access_db, local_demo_config, tmp_path, monkeypatch):
    from app.ingestion.local_demo import seed_local_demo
    provider = demo_provider()
    await seed_local_demo(local_demo_config, provider=provider, data_root=tmp_path)
    db = access_db
    doc = db.scalar(select(DBDocument).where(DBDocument.document_type == "local_demo"))
    db.delete(doc)
    db.commit()
    provider.embed_documents.return_value = [[1.0, 0.0]]
    assert await seed_local_demo(local_demo_config, provider=provider, data_root=tmp_path) == 1
    assert len(provider.embed_documents.call_args.args[0]) == 1
    # A model-space change with the same dimension must still re-embed both docs.
    original_ids = set(db.scalars(select(DBChunk.chunk_id)).all())
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_DOCUMENT_PREFIX", "passage: ")
    new_provider = demo_provider()
    assert await seed_local_demo(local_demo_config, provider=new_provider, data_root=tmp_path) == 2
    db.expire_all()
    docs = db.scalars(select(DBDocument).where(DBDocument.document_type == "local_demo")).all()
    assert len(docs) == 2
    assert set(db.scalars(select(DBChunk.chunk_id)).all()) == original_ids
    from app.storage.vector_store import coverage
    from app.storage.models import DBSearchIndex
    indexes = db.scalars(select(DBSearchIndex).where(DBSearchIndex.profile_id == new_provider.profile.profile_id)).all()
    assert indexes and all(coverage(db, index) == (2, 2) for index in indexes)
    # Legacy JSON provenance stays paired with its original vector, while the new
    # profile lives in a separate index over the same chunk IDs.
    assert all(c.metadata_json["embedding_profile_id"] == provider.profile.profile_id for doc in docs for c in doc.chunks)


@pytest.mark.anyio
async def test_local_demo_failure_rolls_back_both_documents(access_db, local_demo_config, tmp_path, monkeypatch):
    import app.ingestion.local_demo as demo
    await demo.seed_local_demo(local_demo_config, provider=demo_provider(), data_root=tmp_path)
    db = access_db
    originals = set(db.scalars(select(DBChunk.chunk_id)).all())
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_DOCUMENT_PREFIX", "passage: ")
    insert_original = demo.write_embeddings
    calls = 0
    def fail_second(session, index, profile, rows):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Simulated second insert failure")
        insert_original(session, index, profile, rows)
    monkeypatch.setattr(demo, "write_embeddings", fail_second)
    with pytest.raises(RuntimeError, match="second insert"):
        await demo.seed_local_demo(local_demo_config, provider=demo_provider(), data_root=tmp_path)
    db.expire_all()
    assert set(db.scalars(select(DBChunk.chunk_id)).all()) == originals
    assert len(db.scalars(select(DBDocument)).all()) == 2
    assert len(db.scalars(select(DBChunkACL)).all()) == 2


@pytest.mark.anyio
async def test_local_demo_missing_credentials_and_bad_vectors_do_not_create_rows(access_db, local_demo_config, tmp_path, caplog):
    from app.ingestion.local_demo import seed_local_demo
    assert await seed_local_demo(local_demo_config, data_root=tmp_path) == 0
    assert "AZURE_OPENAI_ENDPOINT" in caplog.text
    for vectors in ([[1.0, 0.0]], [[1.0], [0.0, 1.0]], [[float("nan"), 0.0], [0.0, 1.0]]):
        provider = demo_provider()
        provider.embed_documents.return_value = vectors
        with pytest.raises(ValueError):
            await seed_local_demo(local_demo_config, provider=provider, data_root=tmp_path)
    assert access_db.scalars(select(DBDocument)).all() == []
    assert access_db.scalars(select(DBChunk)).all() == []


@pytest.mark.anyio
async def test_local_demo_rejects_wrong_profile_and_cloud_targets(local_demo_config, tmp_path, monkeypatch):
    from app.ingestion.local_demo import seed_local_demo
    provider = demo_provider()
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_MODEL_REVISION", "changed")
    with pytest.raises(ValueError, match="profile"):
        await seed_local_demo(local_demo_config, provider=provider, data_root=tmp_path)
    monkeypatch.setattr(settings, "AZURE_SQL_HOST", "cloud.database.windows.net")
    with pytest.raises(ValueError, match="loopback"):
        await seed_local_demo(local_demo_config, provider=provider, data_root=tmp_path)
    for env in ("test", "dev", "prod"):
        monkeypatch.setattr(settings, "APP_ENV", env)
        assert await seed_local_demo(lambda: pytest.fail("must not access DB"), provider=provider) == 0
    provider.embed_documents.assert_not_awaited()


def test_local_unicode_upgrade_preserves_existing_rows(access_db, local_demo_config):
    from app.storage.db import ensure_local_unicode_columns
    db = access_db
    if db.bind.dialect.name != "mssql":
        pytest.skip("Local Unicode migration uses SQL Server DDL")
    doc = document(db)
    item = chunk(db, doc, content="existing text")
    db.commit()
    with db.bind.begin() as connection:
        connection.execute(text("ALTER TABLE dbo.chunks ALTER COLUMN content VARCHAR(MAX) NOT NULL"))
        connection.execute(text("ALTER TABLE dbo.documents ALTER COLUMN title VARCHAR(512) NOT NULL"))
        ensure_local_unicode_columns(connection)
        ensure_local_unicode_columns(connection)  # A second start does no DDL.
    db.expire_all()
    assert item.content == "existing text"
    doc.title = "Žluťoučký kůň a příliš žluťoučký úředník"
    item.content = "Studijní oddělení: řádné žádosti, čtenáři, příště."
    db.commit()
    db.expire_all()
    assert doc.title == "Žluťoučký kůň a příliš žluťoučký úředník"
    assert item.content == "Studijní oddělení: řádné žádosti, čtenáři, příště."


@pytest.mark.parametrize("branch", ["vector", "keyword"])
def test_both_acl_levels_and_exact_tenant_precede_top_k(access_db, branch):
    db = access_db
    chunk(db, document(db, acl={"allowed_groups": ["HR"]}), content="needle " * 20)
    chunk(db, document(db), acl={"allowed_groups": ["HR"]}, content="needle " * 19)
    chunk(db, document(db, tenant="alpha-dev"), content="needle " * 18)
    chunk(db, document(db, tenant="beta"), content="needle " * 17)
    chunk(db, document(db, tenant="Alpha"), content="needle " * 16)
    chunk(db, document(db, tenant="alpha "), content="needle " * 15)
    allowed = chunk(db, document(db), embedding=[0.8, 0.2])
    db.commit()
    assert [row[0].chunk_id for row in candidates(db, branch, context())] == [allowed.chunk_id]
    assert len(candidates(db, branch, context(groups=("Management",)), limit=10)) == 3


@pytest.mark.parametrize("branch", ["vector", "keyword"])
@pytest.mark.parametrize("value", ["Finance", ["Žluťoučký", "B"], 3, True, []])
def test_metadata_filters_precede_top_k_and_preserve_value_types(access_db, branch, value):
    db = access_db
    chunk(db, document(db, metadata={"tag": "wrong"}), content="needle " * 10)
    allowed = chunk(db, document(db), metadata={"tag": value}, embedding=[0.8, 0.2])
    db.commit()
    assert [row[0].chunk_id for row in candidates(db, branch, context(filters={"tag": value}))] == [allowed.chunk_id]
    assert candidates(db, branch, context(filters={"tag": "missing"})) == []


@pytest.mark.parametrize("branch", ["vector", "keyword"])
def test_scalar_metadata_does_not_treat_literal_injection_as_sql(access_db, branch):
    db = access_db
    key, value = 'tag"; DROP TABLE chunks; --', "x' OR 1=1 --"
    allowed = chunk(db, document(db, metadata={key: value}))
    chunk(db, document(db, metadata={key: "wrong"}))
    db.commit()
    assert [row[0].chunk_id for row in candidates(db, branch, context(filters={key: value}))] == [allowed.chunk_id]


def test_acl_prefilter_does_not_spend_candidate_cap_on_forbidden_chunks(access_db):
    db = access_db
    hidden = document(db, acl={"allowed_groups": ["HR"]})
    insert_chunks(db, [{"document_id": hidden.document_id, "chunk_index": i,
                        "content": "needle", "embedding": [1.0, 0.0]} for i in range(310)])
    allowed = chunk(db, document(db), embedding=[0.5, 0.5])
    db.commit()
    assert [row[0].chunk_id for row in candidates(db, "vector", context())] == [allowed.chunk_id]


@pytest.mark.parametrize("branch", ["vector", "keyword"])
def test_freshness_and_standard_columns_precede_top_k(access_db, branch):
    db = access_db
    year = datetime.datetime.now(datetime.timezone.utc).year
    old = document(db)
    old.created_at = datetime.datetime(year - 1, 1, 1)
    old.freshness_status = "archived"
    chunk(db, old, content="needle " * 15)
    new = document(db)
    allowed = chunk(db, new, embedding=[0.8, 0.2])
    db.commit()
    for freshness in ("this_year", "latest"):
        assert [row[0].chunk_id for row in candidates(db, branch, context(filters={
            "freshness_filter": freshness, "language": "cs",
        }))] == [allowed.chunk_id]
    assert candidates(db, branch, context(filters={"language": "absent"})) == []


@pytest.mark.parametrize("expansion", ["siblings", "page", "section"])
def test_context_expansion_excludes_forbidden_neighbors(access_db, expansion):
    db = access_db
    doc = document(db)
    anchor = chunk(db, doc, index=1, content="needle anchor")
    chunk(db, doc, index=0, acl={"allowed_groups": ["HR"]}, content="SECRET neighbor")
    visible = chunk(db, doc, index=2, content="allowed neighbor")
    db.commit()
    retriever = VectorRetriever(db)
    result = retriever._apply_filters([(anchor, doc)], context(), [1.0, 0.0])
    expanded = retriever._expand_context(result, expansion, 2, context=context())
    assert "SECRET" not in expanded[0].content
    assert "allowed neighbor" in expanded[0].content
    assert set(expanded[0].metadata["context_chunk_ids"]) == {str(anchor.chunk_id), str(visible.chunk_id)}
    principal = Principal(uuid.uuid4(), "alpha", ("User",))
    assert visible_document(db, doc.document_id, principal, full_document=True) is None


def test_orm_bulk_update_rollback_and_backfill_preserve_acl_projection(access_db):
    db = access_db
    doc = document(db, acl={"allowed_groups": ["HR"]})
    insert_chunks(db, [{"document_id": doc.document_id, "chunk_index": 0, "content": "needle",
                        "security_acl": {"allowed_groups": ["HR"]}, "embedding": [1.0, 0.0]}])
    db.commit()
    item = db.scalar(select(DBChunk))
    assert item.tenant_id == "alpha"
    assert candidates(db, "vector", context()) == []
    doc.security_acl = item.security_acl = {"allowed_groups": ["User"]}
    db.flush()
    assert len(candidates(db, "vector", context())) == 1
    db.rollback()
    assert candidates(db, "vector", context()) == []
    db.execute(delete(DBChunkACL))
    db.execute(delete(DBDocumentACL))
    rebuild_acl_grants(db, batch_size=1)
    db.commit()
    assert candidates(db, "vector", context()) == []
    assert len(candidates(db, "vector", context(groups=("HR",)))) == 1
    db.execute(delete(DBChunk))
    db.execute(delete(DBDocument))
    db.commit()
    assert db.scalars(select(DBChunkACL)).all() == []
    assert db.scalars(select(DBDocumentACL)).all() == []


def test_malformed_acl_and_foreign_chunk_tenant_fail_closed(access_db):
    db = access_db
    chunk(db, document(db, acl={"allowed_groups": "User"}))
    doc = document(db)
    chunk(db, doc, acl={"allowed_groups": [None]})
    db.execute(insert(DBChunk), [{"document_id": doc.document_id, "tenant_id": "beta",
                                 "chunk_index": 3, "content": "needle", "embedding": [1.0, 0.0]}])
    db.commit()
    assert candidates(db, "vector", context()) == []
    assert len(candidates(db, "vector", context(groups=("Management",)), limit=10)) == 2


def test_history_revocation_checks_all_expanded_chunks(access_db):
    db = access_db
    doc = document(db)
    anchor = chunk(db, doc)
    neighbor = chunk(db, doc, index=1, acl={"allowed_groups": ["HR"]})
    db.commit()
    evidence = {"access_policy": ACCESS_POLICY, "citations": [], "access_refs": [
        {"chunk_id": str(cid), "document_id": str(doc.document_id)}
        for cid in (anchor.chunk_id, neighbor.chunk_id)
    ]}
    msg = DBChatMessage(role="assistant", content="HR evidence", sources=evidence)
    assert history_is_visible(db, msg, Principal(uuid.uuid4(), "alpha", ("HR", "User")))
    assert not history_is_visible(db, msg, Principal(uuid.uuid4(), "alpha", ("User",)))


@pytest.fixture
def api_client(access_db):
    def get_session():
        yield access_db
    app.dependency_overrides[get_db_session] = get_session
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


def user(db, *, tenant="alpha", groups=None, email="user@example.test"):
    item = DBUser(tenant_id=tenant, username="tester", email=email,
                  groups=groups or ["User"], role="User", password_hash=hash_password("test-only"))
    db.add(item)
    db.commit()
    return item


def test_identity_rejects_headers_and_foreign_tenant_tokens(access_db, api_client):
    normal = user(access_db)
    headers = {"X-User-Id": str(normal.user_id), "X-User-Groups": "Management"}
    assert api_client.post("/api/chat", json={"query": "needle"}, headers=headers).status_code == 401
    foreign = user(access_db, tenant="beta", email="foreign@example.test")
    headers["Authorization"] = "Bearer " + create_token(foreign)
    assert api_client.get("/api/documents/list", headers=headers).status_code == 401
    assert api_client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    token = create_token(normal)
    normal.tenant_id = "Alpha"
    access_db.commit()
    assert api_client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_missing_expiration_and_invalid_filters_fail_before_model_calls(access_db, api_client, monkeypatch):
    import base64
    import hashlib
    import hmac
    import json
    normal = user(access_db)
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": str(normal.user_id), "tenant_id": "alpha",
    }).encode()).decode().rstrip("=")
    signature = hmac.new(settings.JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert api_client.get("/api/auth/me", headers={"Authorization": f"Bearer {payload}.{signature}"}).status_code == 401
    headers = {"Authorization": "Bearer " + create_token(normal)}
    assert api_client.post("/api/chat", json={"query": "needle", "filters": {"tag": {"nested": 1}}}, headers=headers).status_code == 422
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "JWT_SECRET", "dolphin-ai-search-secret-key-2026")
    assert api_client.get("/api/auth/me", headers=headers).status_code == 503
    assert api_client.post("/api/auth/register", json={
        "email": "outsider@example.test", "username": "outsider", "password": "test-only",
    }).status_code == 403


def test_self_registration_cannot_assign_management_and_login_is_tenant_scoped(access_db, api_client):
    foreign = user(access_db, tenant="beta", email="same@example.test")
    assert api_client.post("/api/auth/login", json={"email": foreign.email, "password": "test-only"}).status_code == 401
    response = api_client.post("/api/auth/register", json={
        "email": foreign.email, "username": "new", "password": "test-only",
        "role": "Admin", "groups": ["Management", "HR"],
    })
    assert response.status_code == 200
    assert response.json()["user"]["groups"] == ["User"]
    assert response.json()["user"]["role"] == "User"


def prepare_chat_index(db, chat, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.test")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "synthetic-test-key")
    from app.storage.vector_store import provision_index, write_embeddings, activate_index
    profile = replace(chat.embedding_provider.profile, dimensions=2)
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_DIMENSIONS", 2)
    monkeypatch.setattr(chat.embedding_provider, "_profile", profile)
    index = provision_index(db, "alpha", profile, native=False)
    rows = [{"chunk_id": chunk.chunk_id, "input_revision": chunk.content_hash, "embedding": chunk.embedding}
            for chunk in db.scalars(select(DBChunk)).all() if chunk.tenant_id == "alpha"]
    write_embeddings(db, index, profile, rows)
    activate_index(db, index)
    db.commit()


def test_chat_uses_current_server_groups_not_headers_or_stale_token(access_db, api_client, monkeypatch):
    from app.api.routes import chat
    normal = user(access_db, groups=["User", "HR"])
    token = create_token(normal)
    normal.groups = ["User"]
    access_db.commit()
    secret = document(access_db, acl={"allowed_groups": ["HR"]}, title="SECRET")
    chunk(access_db, secret, content="SECRET EVIDENCE")
    public = chunk(access_db, document(access_db, title="Public"))
    access_db.commit()
    prepare_chat_index(access_db, chat, monkeypatch)
    monkeypatch.setattr(chat.embedding_provider, "embed_query", AsyncMock(return_value=[1.0, 0.0]))
    generate = AsyncMock(return_value="test answer")
    monkeypatch.setattr("app.providers.model_runtime.ProfileLLMProvider.generate", generate)
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={"context_expansion": "none"}))
    headers = {"Authorization": "Bearer " + token, "X-User-Groups": "Management"}
    result = api_client.post("/api/chat", json={"query": "needle", "search_strategy": "vector"}, headers=headers)
    assert result.status_code == 200, result.text
    assert [source["chunk_id"] for source in result.json()["sources"]] == [str(public.chunk_id)]
    assert all("SECRET" not in message.content for message in generate.call_args.kwargs["messages"])
    assert api_client.post("/api/documents/reindex-all", headers=headers).status_code == 403
    assert api_client.get(f"/api/documents/{secret.document_id}/chunks", headers=headers).status_code == 404
    assert api_client.get(f"/api/documents/view/{secret.document_id}", headers=headers).status_code == 404
    assert api_client.post("/api/documents/preview-chunks", json={"document_id": str(secret.document_id)}, headers=headers).status_code == 404


def test_followup_answer_inherits_history_permissions(access_db, api_client, monkeypatch):
    from app.api.routes import chat
    from app.storage.models import DBChatMessage
    normal = user(access_db, groups=["User", "HR"])
    hidden = document(access_db, acl={"allowed_groups": ["HR"]})
    secret = chunk(access_db, hidden, content="SECRET evidence")
    access_db.commit()
    prepare_chat_index(access_db, chat, monkeypatch)
    monkeypatch.setattr(chat.embedding_provider, "embed_query", AsyncMock(return_value=[1.0, 0.0]))
    generate = AsyncMock(side_effect=["SECRET first", "SECRET carried", "insufficient evidence"])
    monkeypatch.setattr("app.providers.model_runtime.ProfileLLMProvider.generate", generate)
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={"context_expansion": "none"}))
    headers = {"Authorization": "Bearer " + create_token(normal)}
    first = api_client.post("/api/chat", json={"query": "needle", "search_strategy": "vector"}, headers=headers)
    assert first.status_code == 200
    thread = first.json()["thread_id"]
    followup = {"query": "followup", "thread_id": thread, "search_strategy": "vector", "filters": {"tag": "missing"}}
    second = api_client.post("/api/chat", json=followup, headers=headers)
    assert second.status_code == 200 and second.json()["sources"] == []
    saved = access_db.scalars(select(DBChatMessage).where(DBChatMessage.role == "assistant")).all()
    assert all({"chunk_id": str(secret.chunk_id), "document_id": str(hidden.document_id)}
               in message.sources["access_refs"] for message in saved)
    normal.groups = ["User"]
    access_db.commit()
    third = api_client.post("/api/chat", json=followup, headers=headers)
    assert third.status_code == 200
    assert all("SECRET" not in msg.content for msg in generate.call_args.kwargs["messages"])
    history = api_client.get(f"/api/threads/{thread}", headers=headers)
    assert history.status_code == 200
    assert all("SECRET" not in message["content"] for message in history.json()["messages"])


def test_document_reads_cannot_escape_data_or_tenant_blob_container(access_db, api_client, tmp_path):
    normal = user(access_db)
    private_file = tmp_path / "private.txt"
    private_file.write_text("PRIVATE outside data", encoding="utf-8")
    doc = document(access_db)
    doc.source_uri = str(private_file)
    chunk(access_db, doc)
    access_db.commit()
    headers = {"Authorization": "Bearer " + create_token(normal)}
    result = api_client.get(f"/api/documents/view/{doc.document_id}", headers=headers)
    assert result.status_code == 404
    assert "PRIVATE outside data" not in result.text
    assert api_client.post("/api/documents/preview-chunks", json={"document_id": str(doc.document_id)}, headers=headers).status_code == 404
    doc.source_type = "azure_blob"
    doc.source_uri = "azure://not-current-container/missing.pdf"
    access_db.commit()
    assert api_client.get(f"/api/documents/view/{doc.document_id}", headers=headers).status_code == 404
