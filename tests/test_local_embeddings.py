"""Ollama contract, active-profile routing and independent indexes over shared chunks."""
from dataclasses import replace
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.embedding_config import embedding_entry, load_embedding_catalog
from app.core.embedding_selection import active_embedding_provider
from app.core.model_config import ModelError
from app.providers.factory import catalog_embedding_provider, create_embedding_profile
from app.providers.ollama_embeddings import OllamaEmbeddingProvider
from app.storage.models import DBChunk, DBSearchIndex, DBChatThread
from app.storage.vector_store import (activate_index, coverage, exact_candidates, provision_index,
                                     write_chunks)
from app.ingestion.index_backfill import backfill_index
from test_search_access import access_engine, access_db, api_client, document, context, user
from app.api.routes.auth import create_token


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def nomic():
    return embedding_entry("ju-prod", "jhu-nomic")


def test_catalog_keeps_azure_identity_and_local_tenant_boundary(nomic, tmp_path, monkeypatch):
    import app.core.tenant_config as tc
    (tmp_path / "dolphin").mkdir()
    (tmp_path / "dolphin/embedding_config.json").write_text(json.dumps({"schema_version": 1,
        "default_profile": "azure-default", "profiles": [{"id": "azure-default", "provider": "azure_openai"}]}), encoding="utf-8")
    monkeypatch.setattr(tc, "LOCAL_TENANTS_DIR", str(tmp_path))
    assert embedding_entry("ju-prod", "azure-default").space() == create_embedding_profile()
    assert nomic.space().dimensions == 768
    assert nomic.space().prepare_query("Žádost") == "search_query: Žádost"
    assert nomic.space().prepare_document("Žádost") == "search_document: Žádost"
    with pytest.raises(ModelError) as error:
        embedding_entry("dolphin", "jhu-nomic")
    assert error.value.code == "embedding_profile_unavailable"
    with pytest.raises(ModelError):
        embedding_entry("ju-prod", space=replace(nomic.space(), model_revision="sha256:" + "a" * 64))


def test_invalid_embedding_override_never_uses_default(tmp_path, monkeypatch):
    import app.core.tenant_config as tc
    (tmp_path / "jhu").mkdir()
    (tmp_path / "jhu/embedding_config.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(tc, "LOCAL_TENANTS_DIR", str(tmp_path))
    with pytest.raises(ModelError) as error:
        load_embedding_catalog("ju-prod")
    assert error.value.code == "embedding_config_invalid"
    with pytest.raises(ModelError):
        active_embedding_provider(SimpleNamespace(get=Mock(side_effect=AssertionError("Invalid config must fail first"))),
                                  "ju-prod", fallback=SimpleNamespace(profile=create_embedding_profile()))


def test_bootstrap_uses_catalog_default_not_cached_azure(nomic, tmp_path, monkeypatch, access_db):
    import app.core.tenant_config as tc
    catalog = load_embedding_catalog("ju-prod").model_dump(mode="json")
    catalog["default_profile"] = "jhu-nomic"
    (tmp_path / "jhu").mkdir()
    (tmp_path / "jhu/embedding_config.json").write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setattr(tc, "LOCAL_TENANTS_DIR", str(tmp_path))
    provider = active_embedding_provider(access_db, "ju-prod",
                                        fallback=SimpleNamespace(profile=create_embedding_profile()))
    assert provider.profile == nomic.space()


@pytest.fixture
def service(monkeypatch, nomic):
    import app.providers.ollama_embeddings as module
    for key, value in {"JHU_LLM_ENDPOINT": "https://model.example.test", "JHU_LLM_USERNAME": "private-user",
                       "JHU_LLM_PASSWORD": "private-password"}.items():
        monkeypatch.setattr(settings, key, value)
    requests = []
    state = dict(digest=nomic.space().model_revision[7:], fault=None, posts=0)

    def respond(request):
        requests.append(request)
        assert request.headers["authorization"].startswith("Basic ")
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": nomic.space().model_id, "digest": state["digest"]}]})
        state["posts"] += 1
        if isinstance(state["fault"], int):
            return httpx.Response(state["fault"], text="private-password private document")
        if state["fault"] == "timeout":
            raise httpx.ReadTimeout("private-password private document", request=request)
        body = json.loads(request.content)
        vectors = [([0.0, 1.0] + [0.0] * 766 if "knihovna" in text else [1.0] + [0.0] * 767)
                   for text in body["input"]]
        if state["fault"] == "incomplete": vectors = []
        if state["fault"] == "dimension": vectors[0] = [1.0, 0.0]
        if state["fault"] == "zero": vectors[0] = [0.0] * 768
        if state["fault"] == "bool": vectors[0][0] = True
        if state["fault"] == "string": vectors[0][0] = "1"
        if state["fault"] == "norm": vectors[0][0] = 2.0
        if state["fault"] == "digest_after": state["digest"] = "b" * 64
        if state["fault"] == "nan":
            return httpx.Response(200, content='{"model":"nomic-embed-text:latest","embeddings":[[NaN]]}')
        return httpx.Response(200, json={"model": "wrong" if state["fault"] == "model" else body["model"], "embeddings": vectors})

    original = httpx.AsyncClient
    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return original(transport=httpx.MockTransport(respond), **kwargs)
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    return requests, state


@pytest.mark.anyio
async def test_task_prefixes_batch_order_and_empty_input(nomic, service):
    requests, state = service
    provider = OllamaEmbeddingProvider(nomic.model_copy(update={"batch_size": 2}))
    assert await provider.embed_documents([]) == [] and requests == []
    vectors = await provider.embed_documents(["žádost", "knihovna", "zkouška"])
    assert [vector[:2] for vector in vectors] == [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
    await provider.embed_query("Kdy začíná semestr?")
    bodies = [json.loads(request.content) for request in requests if request.method == "POST"]
    assert [body["input"] for body in bodies] == [["search_document: žádost", "search_document: knihovna"],
        ["search_document: zkouška"], ["search_query: Kdy začíná semestr?"]]
    assert all(body["truncate"] is False and set(body) == {"model", "input", "truncate"} for body in bodies)


@pytest.mark.anyio
@pytest.mark.parametrize("fault,code,status", [
    (401, "embedding_credentials_invalid", 502), (403, "embedding_credentials_invalid", 502),
    (400, "embedding_input_rejected", 422), (404, "embedding_model_not_found", 503),
    (429, "model_busy", 429), (500, "embedding_request_failed", 502),
    ("timeout", "embedding_timeout", 504), ("digest_after", "embedding_model_changed", 503),
    *[(fault, "embedding_request_failed", 502) for fault in
      ("incomplete", "dimension", "zero", "bool", "string", "norm", "model", "nan")]])
async def test_invalid_service_results_fail_closed_without_retry(nomic, service, fault, code, status):
    _, state = service
    state["fault"] = fault
    with pytest.raises(ModelError) as error:
        await OllamaEmbeddingProvider(nomic).embed_query("private document")
    assert (error.value.code, error.value.status) == (code, status)
    assert "private" not in str(error.value)
    assert state["posts"] == 1


@pytest.mark.anyio
async def test_digest_limits_shared_budget_and_vpn_precede_embedding(nomic, service, monkeypatch):
    requests, state = service
    provider = OllamaEmbeddingProvider(nomic)
    with pytest.raises(ModelError, match="limit"):
        await provider.embed_query("x" * 12001)
    assert not requests
    state["digest"] = "f" * 64
    with pytest.raises(ModelError) as error:
        await provider.embed_query("Otázka")
    assert error.value.code == "embedding_model_changed" and state["posts"] == 0
    from app.providers.model_runtime import _jhu_slots
    assert _jhu_slots.acquire(blocking=False)
    try:
        with pytest.raises(ModelError) as error:
            await provider.embed_query("Otázka")
        assert error.value.status == 429
    finally:
        _jhu_slots.release()
    monkeypatch.setattr(settings, "JHU_LLM_ENDPOINT", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "JHU_LLM_ALLOW_HTTP", True)
    monkeypatch.setattr(settings, "APP_ENV", "local")
    guard = Mock(side_effect=ModelError("model_vpn_required", "VPN"))
    monkeypatch.setattr("app.providers.vpn.verify_windows_vpn", guard)
    monkeypatch.setattr("app.providers.jhu_connection.platform.system", lambda: "Windows")
    with pytest.raises(ModelError, match="VPN"):
        await provider.embed_query("Otázka")
    guard.assert_called_once()


@pytest.mark.anyio
async def test_two_spaces_backfill_switch_ingest_and_restore(access_db, nomic, monkeypatch):
    db = access_db
    azure = replace(create_embedding_profile(), dimensions=1536)
    vector = [1.0] + [0.0] * 1535
    doc = document(db)
    write_chunks(db, [{"document_id": doc.document_id, "chunk_index": 0, "content": "Studijní oddělení",
                       "embedding": vector, "security_acl": {"allowed_groups": ["User"]}}], azure)
    original = db.scalar(select(DBChunk))
    original_id = original.chunk_id
    cloud = db.scalar(select(DBSearchIndex).where(DBSearchIndex.profile_id == azure.profile_id))
    activate_index(db, cloud)
    local = provision_index(db, "alpha", nomic.space(), native=False)
    db.commit()
    provider = SimpleNamespace(profile=nomic.space(), embed_documents=AsyncMock(return_value=[[1.0] + [0.0] * 767]))
    assert await backfill_index(db, local, provider=provider) == 1
    assert await backfill_index(db, local, provider=provider) == 0
    provider.embed_documents.assert_awaited_once()
    assert db.get(DBChunk, original_id).embedding == vector
    assert coverage(db, cloud) == coverage(db, local) == (1, 1)
    monkeypatch.setattr("app.core.embedding_selection.catalog_embedding_provider", lambda tenant, **kwargs: provider)
    monkeypatch.setattr("app.core.local_model_registry.load_embedding_catalog", lambda tenant: load_embedding_catalog("ju-prod"))
    activate_index(db, local); db.commit()
    assert active_embedding_provider(db, "alpha").profile == nomic.space()
    assert exact_candidates(db, context(), [1.0] + [0.0] * 767, nomic.space(), 3)[0][0].chunk_id == original_id
    write_chunks(db, [{"document_id": doc.document_id, "chunk_index": 1, "content": "Nový text",
                       "embedding": [0.0, 1.0] + [0.0] * 766}], provider.profile)
    db.commit()
    assert coverage(db, local) == (2, 2) and coverage(db, cloud) == (1, 2)
    # An older experiment cannot be activated until the newly added chunk is embedded.
    with pytest.raises(ValueError, match="Incomplete"):
        activate_index(db, cloud)
    db.rollback()
    db.delete(db.get(DBChunk, original_id)); db.commit()
    assert coverage(db, local) == (1, 1) and coverage(db, cloud) == (0, 1)


def test_chat_and_raw_ingest_follow_active_space(access_db, api_client, monkeypatch, nomic, tmp_path):
    from app.api.routes import chat
    from app.core.model_config import load_model_catalog
    import app.core.tenant_config as tc
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha/model_config.json").write_text(
        load_model_catalog("ju-prod").model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(tc, "LOCAL_TENANTS_DIR", str(tmp_path))
    db = access_db
    account = user(db, groups=["User", "Management"])
    index = provision_index(db, "alpha", nomic.space(), native=False)
    activate_index(db, index); db.commit()
    provider = SimpleNamespace(profile=nomic.space(), embed_documents=AsyncMock(return_value=[[1.0] + [0.0] * 767]),
                               embed_query=AsyncMock(return_value=[1.0] + [0.0] * 767))
    monkeypatch.setattr("app.core.embedding_selection.catalog_embedding_provider", lambda tenant, **kwargs: provider)
    monkeypatch.setattr("app.core.local_model_registry.load_embedding_catalog", lambda tenant: load_embedding_catalog("ju-prod"))
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.test")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={"context_expansion": "none"}))
    monkeypatch.setattr("app.providers.model_runtime.ProfileLLMProvider.generate", AsyncMock(return_value="Odpověď [1]"))
    headers = {"Authorization": "Bearer " + create_token(account)}
    result = api_client.post("/api/documents/ingest", headers=headers, json={"source_type": "local",
        "source_uri": "synthetic", "title": "Studium", "document_type": "test", "content": "Studijní oddělení", "language": "cs",
        "security_acl": {"allowed_groups": ["User"]}})
    assert result.status_code == 200, result.text
    assert coverage(db, index) == (1, 1)
    response = api_client.post("/api/chat", headers=headers, json={"query": "Kam se obrátit?", "search_strategy": "vector"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"]["embedding_profile_id"] == nomic.space().profile_id
    assert body["sources"][0]["chunk_id"] == result.json()["chunk_id"]
    provider.embed_query.assert_awaited_once()
    assert provider.embed_documents.call_args.args == (["Studijní oddělení"],)
    # An unavailable active provider is an explicit failure before another thread is created.
    previous = len(db.scalars(select(DBChatThread)).all())
    def unavailable(*args, **kwargs):
        raise ModelError("embedding_profile_unavailable", "Profil chybí")
    monkeypatch.setattr("app.core.embedding_selection.catalog_embedding_provider", unavailable)
    response = api_client.post("/api/chat", headers=headers, json={"query": "Otázka"})
    assert response.status_code == 503
    assert len(db.scalars(select(DBChatThread)).all()) == previous


@pytest.mark.anyio
async def test_cli_backfills_inactive_profile_and_resumes_without_implicit_activation(access_db, nomic, monkeypatch):
    import migrate_search_vectors as cli
    from sqlalchemy.orm import sessionmaker
    from app.storage.vector_store import active_index
    db = access_db
    monkeypatch.setattr(settings, "TENANT_ID", "ju-prod")
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "sqlserver")
    doc = document(db, tenant="ju-prod")
    original_profile = create_embedding_profile()
    original_vector = [1.0] + [0.0] * (original_profile.dimensions - 1)
    write_chunks(db, [{"document_id": doc.document_id, "chunk_index": 0, "content": "Žádosti studentů",
                       "embedding": original_vector}], original_profile)
    original = db.scalar(select(DBChunk))
    old_index = db.scalar(select(DBSearchIndex))
    activate_index(db, old_index); db.commit()
    monkeypatch.setattr(cli, "engine", db.bind)
    monkeypatch.setattr(cli, "SessionLocal", sessionmaker(bind=db.bind))
    provider = SimpleNamespace(profile=nomic.space(), embed_documents=AsyncMock(return_value=[[1.0] + [0.0] * 767]))
    factory = Mock(return_value=provider)
    monkeypatch.setattr(cli, "catalog_embedding_provider", factory)
    args = SimpleNamespace(create=True, index=None, reembed=True, proven_legacy=False, activate=False,
        create_ann=False, ann_status=False, embedding_profile="jhu-nomic", expect_host=settings.AZURE_SQL_HOST,
        expect_db=settings.AZURE_SQL_DB, expect_tenant=settings.TENANT_ID)
    await cli.run(args)
    db.expire_all()
    candidate = db.scalar(select(DBSearchIndex).where(DBSearchIndex.profile_id == nomic.space().profile_id))
    assert coverage(db, candidate) == (1, 1)
    assert db.get(DBChunk, original.chunk_id).embedding == original_vector
    assert active_index(db, "ju-prod", original_profile).index_id == old_index.index_id
    args.create, args.index, args.embedding_profile = False, str(candidate.index_id), None
    await cli.run(args)
    provider.embed_documents.assert_awaited_once()
    assert factory.call_args.kwargs["space"] == nomic.space()
    args.reembed, args.activate = False, True
    await cli.run(args)
    db.expire_all()
    assert active_index(db, "ju-prod", nomic.space()).index_id == candidate.index_id


@pytest.mark.anyio
async def test_live_nomic_local_sql_roundtrip(access_db, nomic, monkeypatch):
    if os.getenv("RUN_JHU_EMBEDDING_TESTS") != "1" or access_db.bind.dialect.name != "mssql":
        pytest.skip("Opt-in real JHU API + isolated local SQL Server database")
    from dotenv import dotenv_values
    from app.providers.embeddings import EmbeddingProfile
    values = dotenv_values(".env.jhu-model")
    for key in ("JHU_LLM_ENDPOINT", "JHU_LLM_USERNAME", "JHU_LLM_PASSWORD"):
        monkeypatch.setattr(settings, key, os.getenv(key) or values.get(key))
    monkeypatch.setattr(settings, "JHU_LLM_ALLOW_HTTP", True)
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "sqlserver")
    db = access_db
    texts = ["Studijní oddělení přijímá žádosti o přerušení studia v pondělí a ve středu.",
             "Univerzitní knihovna půjčuje knihy na třicet dnů."]
    # Reference vectors are explicitly synthetic, never claimed to be Azure outputs.
    reference = EmbeddingProfile("synthetic-reference", "test", 1536)
    for i, content in enumerate(texts):
        doc = document(db, title=f"Synthetic university {i}")
        write_chunks(db, [{"document_id": doc.document_id, "chunk_index": 0, "content": content,
                           "embedding": [1.0] + [0.0] * 1535,
                           "security_acl": {"allowed_groups": ["User"]}}], reference)
    old = db.scalar(select(DBSearchIndex).where(DBSearchIndex.profile_id == reference.profile_id))
    ids = db.scalars(select(DBChunk.chunk_id)).all()
    activate_index(db, old)
    index = provision_index(db, "alpha", nomic.space(), native=False)
    db.commit()
    provider = OllamaEmbeddingProvider(nomic)
    assert await backfill_index(db, index, provider=provider) == 2
    assert await backfill_index(db, index, provider=provider) == 0
    assert coverage(db, old) == coverage(db, index) == (2, 2)
    assert db.scalars(select(DBChunk.chunk_id)).all() == ids
    query = await provider.embed_query("Kde mohu podat žádost o přerušení studia?")
    activate_index(db, index); db.commit()
    matches = exact_candidates(db, context(), query, provider.profile, 2)
    assert matches[0][0].content == texts[0]
    assert exact_candidates(db, context(filters={"title": "missing"}), query, provider.profile, 2) == []
    activate_index(db, old); db.commit()
    assert exact_candidates(db, context(), [1.0] + [0.0] * 1535, reference, 2)
