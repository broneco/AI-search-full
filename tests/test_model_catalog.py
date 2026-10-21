"""Catalog, routing, access persistence, inference failures and summary regressions."""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.api.identity import Principal
from app.api.routes.auth import create_token, hash_password
from app.core.config import settings
from app.core.model_config import ModelError, load_model_catalog
from app.core.model_selection import model_provider, select_model
from app.providers.llm import ChatMessage
from app.providers.model_runtime import ProfileLLMProvider
from app.storage.models import Base, DBUser, DBModelAccess, DBChatMessage


@pytest.fixture
def models_db(monkeypatch, tmp_path):
    import app.core.tenant_config as tc
    jhu = json.loads((__import__("pathlib").Path(tc.TENANTS_DIR) / "jhu/model_config.json").read_text(encoding="utf-8"))
    root = tmp_path / "catalogs"
    (root / "jhu").mkdir(parents=True)
    (root / "jhu/model_config.json").write_text(json.dumps(jhu), encoding="utf-8")
    jhu["profiles"] = [p for p in jhu["profiles"] if p["location"] == "cloud"]
    (root / "default").mkdir()
    (root / "default/model_config.json").write_text(json.dumps(jhu), encoding="utf-8")
    # Standalone fixtures also declare the pipeline's embedding space.
    embedding = json.loads((__import__("pathlib").Path(tc.TENANTS_DIR) / "jhu/embedding_config.json").read_text(encoding="utf-8"))
    (root / "jhu/embedding_config.json").write_text(json.dumps(embedding), encoding="utf-8")
    embedding["profiles"] = [p for p in embedding["profiles"] if p["provider"] == "azure_openai"]
    (root / "default/embedding_config.json").write_text(json.dumps(embedding), encoding="utf-8")
    monkeypatch.setattr(tc, "TENANTS_DIR", str(root))
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr("app.storage.db.SessionLocal", factory)
    monkeypatch.setattr(settings, "TENANT_ID", "models-test")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.test")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(settings, "AZURE_OPENAI_FLASH_DEPLOYMENT", "mini-deployment")
    monkeypatch.setattr(settings, "AZURE_OPENAI_THINKING_DEPLOYMENT", "advanced-deployment")
    with factory() as db:
        yield db
    engine.dispose()


def account(db, groups=None, tenant=None):
    user = DBUser(tenant_id=tenant or settings.TENANT_ID, username="model-test",
                  email=uuid.uuid4().hex + "@example.test", groups=groups or ["User"],
                  password_hash=hash_password("test-only"), role="User")
    db.add(user); db.commit()
    return user, {"Authorization": "Bearer " + create_token(user)}


@pytest.fixture
def models_client(models_db):
    from app.main import app
    app.dependency_overrides[get_db_session] = lambda: models_db
    # Do not run application lifespan: model API tests do not initialize other databases or seed data.
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.pop(get_db_session, None)


def test_default_and_jhu_catalog_and_alias():
    import app.core.tenant_config as tc
    from pathlib import Path
    default = load_model_catalog("dolphin-dev") if (Path(tc.TENANTS_DIR) / "default/model_config.json").exists() else load_model_catalog("ju-prod")
    assert default.defaults == {p: "gpt-5.4-mini" for p in ("chat", "summary", "classification")}
    assert len([p for p in default.profiles if p.location == "cloud"]) == 2
    assert [p.id for p in load_model_catalog("ju-prod").profiles] == ["gpt-5.4-mini", "gpt-5.4", "jhu-qwen"]


def test_invalid_override_does_not_fall_back(tmp_path, monkeypatch):
    import app.core.tenant_config as tc
    (tmp_path / "models").mkdir()
    (tmp_path / "models/model_config.json").write_text('{"secret": "invalid"}', encoding="utf-8")
    monkeypatch.setattr(tc, "LOCAL_TENANTS_DIR", str(tmp_path))
    with pytest.raises(ModelError, match="Konfigurace"):
        load_model_catalog("models-test")


def test_catalog_requires_login_and_never_returns_connection(models_db, models_client):
    assert models_client.get("/api/models").status_code == 401
    _, headers = account(models_db)
    response = models_client.get("/api/models", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["models"]) == 2
    assert "example.test" not in response.text and "synthetic-test-key" not in response.text
    assert all("provider" not in p and "connection" not in p for p in body["models"])
    assert models_client.get("/api/models?purpose=embedding", headers=headers).status_code == 422


def test_legacy_mapping_and_unknown_profiles(models_db):
    assert select_model(models_db, settings.TENANT_ID, "chat", mode="thinking").id == "gpt-5.4"
    assert select_model(models_db, settings.TENANT_ID, "chat").id == "gpt-5.4-mini"
    with pytest.raises(ModelError) as error:
        select_model(models_db, settings.TENANT_ID, "chat", "jhu-qwen")
    assert error.value.status == 422


def test_optional_unavailable_model_does_not_disable_mini(models_db, models_client, monkeypatch):
    _, headers = account(models_db)
    monkeypatch.setattr(settings, "AZURE_OPENAI_THINKING_DEPLOYMENT", "")
    response = models_client.get("/api/models", headers=headers).json()["models"]
    assert response[0]["available"] and not response[1]["available"]


def test_access_editor_authorization_cas_revocation_and_tenant_isolation(models_db, models_client):
    manager, admin = account(models_db, ["User", "Management"])
    normal, headers = account(models_db)
    assert models_client.get("/api/models/access", headers=headers).status_code == 403
    assert models_client.get("/api/models/access", headers=admin).status_code == 200
    url = "/api/models/access/gpt-5.4"
    assert models_client.put(url, json={"revision": 0, "allowed_groups": ["Management"]}, headers=admin).status_code == 200
    assert models_client.put(url, json={"revision": 0, "allowed_groups": None}, headers=admin).status_code == 409
    assert len(models_client.get("/api/models", headers=headers).json()["models"]) == 1
    principal = Principal(normal.user_id, normal.tenant_id, ("User", "Management"))
    with pytest.raises(ModelError) as error:
        select_model(models_db, normal.tenant_id, "chat", "gpt-5.4", principal)
    assert error.value.status == 403  # forged/stale groups ignored
    models_db.add(DBModelAccess(tenant_id="foreign", model_id="gpt-5.4-mini", allowed_groups=[], updated_by="test"))
    models_db.commit()
    assert select_model(models_db, normal.tenant_id, "chat", principal=principal).id == "gpt-5.4-mini"
    assert models_client.put(url, json={"revision": 1, "allowed_groups": []}, headers=admin).status_code == 200
    assert len(models_client.get("/api/models", headers=admin).json()["models"]) == 1


def test_recheck_before_generation_uses_fresh_server_groups(models_db):
    user, _ = account(models_db, ["User", "Management"])
    principal = Principal(user.user_id, user.tenant_id, ("User", "Management"))
    models_db.add(DBModelAccess(tenant_id=user.tenant_id, model_id="gpt-5.4", allowed_groups=["Management"], updated_by="test"))
    models_db.commit()
    provider = model_provider(models_db, user.tenant_id, "chat", "gpt-5.4", principal)
    user.groups = ["User"]; models_db.commit()
    with pytest.raises(ModelError) as error:
        asyncio.run(provider.generate([ChatMessage(role="user", content="Ahoj")]))
    assert error.value.status == 403


def jhu_settings(monkeypatch):
    for key, value in dict(JHU_LLM_ENDPOINT="https://jhu.example.test", JHU_LLM_USERNAME="synthetic-user",
                          JHU_LLM_PASSWORD="synthetic-password", JHU_LLM_VERIFIED_MODEL="qwen3.8:latest").items():
        monkeypatch.setattr(settings, key, value)


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr("app.providers.model_runtime.httpx.AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))


def test_jhu_contract_transcript_and_no_thinking_output(monkeypatch):
    jhu_settings(monkeypatch)
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        assert request.url.path == "/api/generate"
        assert request.headers["Authorization"].startswith("Basic ")
        return httpx.Response(200, json={"response": "Odpověď [1]", "thinking": "private", "done": True, "load_duration": 10})
    mock_http(monkeypatch, handler)
    profile = load_model_catalog("ju-prod").profiles[-1]
    provider = ProfileLLMProvider(profile)
    result = asyncio.run(provider.generate([ChatMessage(role="system", content="Cituj [1]"),
        ChatMessage(role="user", content="Starší dotaz"), ChatMessage(role="assistant", content="Dřívější odpověď"),
        ChatMessage(role="user", content="A co teď?")]))
    assert result == "Odpověď [1]" and "private" not in result
    assert set(calls[0]) == {"model", "prompt", "stream", "options"}
    assert calls[0]["options"] == {"num_predict": profile.max_output_tokens}
    assert calls[0]["stream"] is False and "Dřívější odpověď" in calls[0]["prompt"]
    assert provider.diagnostics["load_duration"] == 10


@pytest.mark.parametrize("status,body", [(401, {}), (404, {}), (200, {}), (200, {"response": ""}), (200, {"response": "partial", "done": False})])
def test_jhu_errors_do_not_leak_or_fallback(monkeypatch, status, body):
    jhu_settings(monkeypatch)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json=body)
    mock_http(monkeypatch, handler)
    with pytest.raises(ModelError) as error:
        asyncio.run(ProfileLLMProvider(load_model_catalog("ju-prod").profiles[-1]).generate([ChatMessage(role="user", content="synthetic")]))
    assert error.value.status == (503 if status == 404 else 502) and len(calls) == 1
    assert "synthetic-password" not in str(error.value) and "jhu.example" not in str(error.value)


def test_jhu_timeout_no_retry_and_input_limit(monkeypatch):
    jhu_settings(monkeypatch)
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret upstream details")
    mock_http(monkeypatch, handler)
    provider = ProfileLLMProvider(load_model_catalog("ju-prod").profiles[-1])
    with pytest.raises(ModelError) as error:
        asyncio.run(provider.generate([ChatMessage(role="user", content="synthetic")]))
    assert error.value.status == 504 and len(calls) == 1
    with pytest.raises(ModelError) as error:
        asyncio.run(provider.generate([ChatMessage(role="user", content="x" * 25000)]))
    assert error.value.status == 422 and len(calls) == 1


def test_azure_exact_deployment_and_supported_parameters(models_db, monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs): self.chat = SimpleNamespace(completions=self)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="answer"), finish_reason="stop")])
    monkeypatch.setattr("app.providers.model_runtime.AsyncAzureOpenAI", Client)
    async def run():
        return await asyncio.gather(*[model_provider(models_db, settings.TENANT_ID, "chat", ident).generate(
            [ChatMessage(role="user", content="question")]) for ident in ("gpt-5.4-mini", "gpt-5.4")])
    assert asyncio.run(run()) == ["answer", "answer"]
    assert [call["model"] for call in calls] == ["mini-deployment", "advanced-deployment"]
    assert all("temperature" not in call and "max_tokens" not in call and "max_completion_tokens" in call for call in calls)


def test_chat_model_provenance_and_switching(models_db, models_client, monkeypatch):
    from app.api.routes import chat
    user, headers = account(models_db)
    monkeypatch.setattr(chat.embedding_provider, "embed_query", AsyncMock(return_value=[1., 0.]))
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={}))
    monkeypatch.setattr(chat.VectorRetriever, "retrieve", AsyncMock(return_value=[]))
    monkeypatch.setattr(ProfileLLMProvider, "generate", AsyncMock(return_value="Odpověď"))
    thread = None
    for model_id in ("gpt-5.4-mini", "gpt-5.4"):
        response = models_client.post("/api/chat", json={"query": "Test", "model_id": model_id,
            "search_strategy": "keyword", "thread_id": thread}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["metadata"]["model_id"] == model_id
        thread = response.json()["thread_id"]
    messages = models_client.get("/api/threads/" + thread, headers=headers).json()["messages"]
    assert [m["generation"]["model_id"] for m in messages if m["role"] == "assistant"] == ["gpt-5.4-mini", "gpt-5.4"]


def test_unknown_chat_model_fails_before_embedding_or_thread_write(models_db, models_client, monkeypatch):
    from app.api.routes import chat
    _, headers = account(models_db)
    embed = AsyncMock()
    monkeypatch.setattr(chat.embedding_provider, "embed_query", embed)
    response = models_client.post("/api/chat", json={"query": "Test", "model_id": "jhu-qwen"}, headers=headers)
    assert response.status_code == 422
    embed.assert_not_called()
    assert not list(models_db.scalars(select(DBChatMessage)))


def test_summary_uses_separate_provider_and_failure_never_becomes_placeholder():
    from app.ingestion.chunking import RecursiveCharacterTextSplitter
    from app.ingestion.extraction import ExtractedPage
    summary = SimpleNamespace(generate=AsyncMock(return_value="Skutečné shrnutí"))
    boundary = SimpleNamespace(generate=AsyncMock(side_effect=AssertionError("wrong model")))
    splitter = RecursiveCharacterTextSplitter(enrich_with_summary=True, strict_summary=True,
        llm_provider=boundary, summary_provider=summary)
    page = ExtractedPage(page_number=1, text="Dokument o studiu na univerzitě.")
    chunks = splitter.split_pages([page])
    assert chunks[0].content.startswith("[AI Shrnutí: Skutečné shrnutí]")
    boundary.generate.assert_not_called()
    summary.generate = AsyncMock(side_effect=ModelError("model_timeout", "timeout", 504))
    with pytest.raises(ModelError):
        splitter.split_pages([page])


def test_missing_permission_table_fails_closed(models_db, models_client):
    _, headers = account(models_db)
    DBModelAccess.__table__.drop(models_db.bind)
    response = models_client.get("/api/models", headers=headers)
    assert response.status_code == 503 and response.json()["code"] == "model_policy_unavailable"


def test_jhu_busy_does_not_start_second_request(monkeypatch):
    from app.providers.model_runtime import _jhu_slots
    jhu_settings(monkeypatch)
    _jhu_slots.acquire()
    try:
        with pytest.raises(ModelError) as error:
            asyncio.run(ProfileLLMProvider(load_model_catalog("ju-prod").profiles[-1]).generate([ChatMessage(role="user", content="test")]))
        assert error.value.status == 429
    finally:
        _jhu_slots.release()


def test_jhu_classification_steps_do_not_compete_for_single_slot(tmp_path, monkeypatch):
    from app.ingestion.tagger import MetadataTagger
    from app.ingestion.extraction import ExtractedPage
    file = tmp_path / "university.txt"
    file.write_text("Text", encoding="utf-8")
    tagger = MetadataTagger(llm_provider=SimpleNamespace(profile=load_model_catalog("ju-prod").profiles[-1]))
    tagger.extractor = SimpleNamespace(extract=lambda name: [ExtractedPage(1, "Text")])
    tagger.load_config = AsyncMock(return_value={"categories": []})
    running = 0
    def step(value):
        async def execute(*args):
            nonlocal running
            running += 1
            assert running == 1
            await asyncio.sleep(0)
            running -= 1
            return value
        return execute
    for method, value in [("determine_release_date", "2026-10-16"), ("classify_category", "User"),
                          ("detect_relationships", {"relationship_type": "none"}), ("detect_language", "cs")]:
        monkeypatch.setattr(tagger, method, step(value))
    assert asyncio.run(tagger.analyze_file(str(file)))["suggested_category"] == "User"


def test_summary_failure_preserves_document_before_embedding(models_db, tmp_path, monkeypatch):
    from app.ingestion.pipeline import IngestionPipeline
    from app.storage.models import DBDocument, DBChunk
    monkeypatch.setattr("app.core.search_config.SearchConfigManager.load_config_sync", lambda self: {"enrich_with_summary": True})
    file = tmp_path / "summary-test.txt"
    file.write_text("New document content", encoding="utf-8")
    old = DBDocument(tenant_id=settings.TENANT_ID, title="Old", source_type="local", source_uri="file://summary-test.txt", document_type="test", checksum="old")
    models_db.add(old); models_db.flush()
    chunk = DBChunk(tenant_id=settings.TENANT_ID, document_id=old.document_id, chunk_index=0, content="Original text", embedding=[1., 0.])
    models_db.add(chunk); models_db.commit()
    old_id, chunk_id = old.document_id, chunk.chunk_id
    summary = SimpleNamespace(generate=AsyncMock(side_effect=ModelError("model_timeout", "timeout", 504)))
    pipeline = IngestionPipeline(models_db, summary_provider=summary)
    embed = AsyncMock()
    monkeypatch.setattr(pipeline.embedding_provider, "embed_documents", embed)
    with pytest.raises(ModelError):
        asyncio.run(pipeline.ingest_file(str(file), force_reindex=True))
    embed.assert_not_awaited()
    assert models_db.get(DBDocument, old_id).title == "Old"
    assert models_db.get(DBChunk, chunk_id).content == "Original text"


def test_document_models_are_independent_and_provenance_is_server_owned(models_db, models_client, monkeypatch):
    import app.ingestion.tagger as tagger_module
    import app.ingestion.pipeline as pipeline_module
    from app.storage.models import DBDocument
    from pathlib import Path
    _, headers = account(models_db, ["User", "Management"])
    selected = {}
    class Tagger:
        def __init__(self, db_session=None, llm_provider=None):
            if llm_provider:
                selected["classification"] = llm_provider.profile.id
        async def analyze_file(self, file):
            return {"suggested_category": "User", "suggested_date": "2026-10-16", "relationship": {"relationship_type": "none"}}
        async def load_config(self):
            return {"categories": [{"key": "User", "allowed_groups": ["User"]}]}
    class Pipeline:
        def __init__(self, db_session, summary_provider=None, principal=None):
            selected["summary"] = summary_provider.profile.id
            self.db = db_session
        async def ingest_file(self, **kwargs):
            doc = DBDocument(tenant_id=settings.TENANT_ID, title="Doc", source_type="local", source_uri="synthetic://doc", document_type="test", metadata_json=kwargs["metadata_json"])
            self.db.add(doc); self.db.flush()
            return doc
    monkeypatch.setattr(tagger_module, "MetadataTagger", Tagger)
    monkeypatch.setattr(pipeline_module, "IngestionPipeline", Pipeline)
    draft = models_client.post("/api/documents/analyze-draft", files={"file": ("doc.txt", b"Synthetic university text", "text/plain")},
        data={"classification_model_id": "gpt-5.4"}, headers=headers)
    assert draft.status_code == 200, draft.text
    body = draft.json()
    temp = Path(body["temp_file_path"])
    receipt = Path(str(temp) + ".model.json")
    try:
        payload = dict(title="Document", date="2026-10-16", category="User", language="cs",
            temp_file_path=str(temp), original_filename="doc.txt", classification_model_id="gpt-5.4",
            summary_model_id="gpt-5.4-mini")
        forged = models_client.post("/api/documents/ingest-confirmed", json={**payload, "classification_model_id": "gpt-5.4-mini"}, headers=headers)
        assert forged.status_code == 422
        confirmed = models_client.post("/api/documents/ingest-confirmed", json=payload, headers=headers)
        assert confirmed.status_code == 200, confirmed.text
        doc = models_db.get(DBDocument, uuid.UUID(confirmed.json()["document_id"]))
        assert selected == {"classification": "gpt-5.4", "summary": "gpt-5.4-mini"}
        assert doc.metadata_json["classification_model_id"] == "gpt-5.4"
    finally:
        temp.unlink(missing_ok=True)
        receipt.unlink(missing_ok=True)


def test_model_policy_migration_requires_exact_reviewed_target(models_db, monkeypatch):
    import sys
    import migrate_model_access
    monkeypatch.setattr("app.storage.db.engine", models_db.bind)
    DBModelAccess.__table__.drop(models_db.bind)
    monkeypatch.setattr(sys, "argv", ["migrate_model_access.py", "--apply", "--expect-host", "wrong"])
    with pytest.raises(ValueError, match="exact expected"):
        migrate_model_access.main()
    from sqlalchemy import inspect
    assert not inspect(models_db.bind).has_table("model_access_policies")
    host = settings.AZURE_SQL_HOST if settings.USE_AZURE_SQL else settings.POSTGRES_HOST
    database = settings.AZURE_SQL_DB if settings.USE_AZURE_SQL else settings.POSTGRES_DB
    monkeypatch.setattr(sys, "argv", ["migrate_model_access.py", "--apply", "--expect-host", host,
        "--expect-db", database, "--expect-tenant", settings.TENANT_ID])
    migrate_model_access.main()
    assert inspect(models_db.bind).has_table("model_access_policies")


def test_jhu_keyvault_refs_and_explicit_secret_precedence(monkeypatch):
    from app.core.config import Settings
    calls = []
    def secret(name):
        calls.append(name)
        return SimpleNamespace(value="synthetic-" + name)
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: object())
    monkeypatch.setattr("azure.keyvault.secrets.SecretClient", lambda **kwargs: SimpleNamespace(get_secret=secret))
    values = dict(_env_file=(), APP_ENV="prod", DATABASE_BACKEND="postgresql", AZURE_KEY_VAULT_NAME="synthetic",
        AZURE_KEY_VAULT_SECRET_JHU_LLM_USERNAME="jhu-user", AZURE_KEY_VAULT_SECRET_JHU_LLM_PASSWORD="jhu-pass")
    resolved = Settings(**values)
    assert resolved.JHU_LLM_USERNAME == "synthetic-jhu-user" and resolved.JHU_LLM_PASSWORD == "synthetic-jhu-pass"
    assert calls == ["jhu-user", "jhu-pass"]
    calls.clear()
    explicit = Settings(**values, JHU_LLM_USERNAME="explicit-user", JHU_LLM_PASSWORD="explicit-pass")
    assert explicit.JHU_LLM_PASSWORD == "explicit-pass" and calls == []
    assert "explicit-pass" not in repr(explicit) and "JHU_LLM_PASSWORD" not in explicit.model_dump()


@pytest.mark.parametrize("alias,allowed", [("OpenVPN TAP-Windows6", True), ("Wi-Fi", False)])
def test_vpn_route_is_required_before_plain_http(monkeypatch, alias, allowed):
    from app.providers.vpn import verify_windows_vpn
    monkeypatch.setattr("app.providers.vpn.subprocess.run", lambda *args, **kwargs:
        SimpleNamespace(returncode=0, stdout=json.dumps([alias])))
    if allowed:
        verify_windows_vpn("160.217.182.41", "OpenVPN")
    else:
        with pytest.raises(ModelError) as error:
            verify_windows_vpn("160.217.182.41", "OpenVPN")
        assert error.value.code == "model_vpn_required"


@pytest.mark.skipif(os.getenv("RUN_JHU_MODEL_TESTS") != "1", reason="Explicit VPN/live model opt-in")
def test_live_jhu_synthetic_rag(models_db, models_client, monkeypatch):
    from dotenv import dotenv_values
    from app.api.routes import chat
    from app.storage.models import DBDocument, DBChunk
    from app.retrieval.base import RetrievalResult
    monkeypatch.setattr(settings, "TENANT_ID", "ju-prod")
    for key, value in dotenv_values(".env.jhu-model").items():
        if key.startswith("JHU_LLM_"):
            monkeypatch.setattr(settings, key, value == "true" if key == "JHU_LLM_ALLOW_HTTP" else value)
    user, headers = account(models_db)
    doc = DBDocument(tenant_id="ju-prod", title="Syntetický projekt", source_type="local", source_uri="synthetic://model-test", document_type="test", language="cs", security_acl={"allowed_groups": ["User"]})
    models_db.add(doc); models_db.flush()
    chunk = DBChunk(tenant_id="ju-prod", document_id=doc.document_id, chunk_index=0,
        content="Kód studentského projektu je JHU-MODEL-TEST-42.", embedding=[1., 0.], security_acl={"allowed_groups": ["User"]})
    models_db.add(chunk); models_db.commit()
    monkeypatch.setattr(chat.embedding_provider, "embed_query", AsyncMock(return_value=[1., 0.]))
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={}))
    monkeypatch.setattr(chat.VectorRetriever, "retrieve", AsyncMock(return_value=[RetrievalResult(
        chunk_id=str(chunk.chunk_id), document_id=str(doc.document_id), content=chunk.content,
        score=1., freshness_status="current", title=doc.title)]))
    response = models_client.post("/api/chat", json={"query": "Jaký je kód studentského projektu? Uveď citaci [1].", "model_id": "jhu-qwen", "search_strategy": "keyword"}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "JHU-MODEL-TEST-42" in body["answer"] and "[1]" in body["answer"]
    assert body["metadata"]["model_id"] == "jhu-qwen"
    assert body["sources"][0]["chunk_id"] == str(chunk.chunk_id)
    history = models_client.get("/api/threads/" + body["thread_id"], headers=headers).json()
    assert history["messages"][-1]["generation"]["model_id"] == "jhu-qwen"
    from app.ingestion.tagger import MetadataTagger
    from app.ingestion.chunking import RecursiveCharacterTextSplitter
    from app.ingestion.extraction import ExtractedPage
    principal = Principal(user.user_id, user.tenant_id, ("User",))
    classifier = model_provider(models_db, user.tenant_id, "classification", "jhu-qwen", principal)
    tagger = MetadataTagger(db_session=models_db, llm_provider=classifier)
    category = asyncio.run(tagger.classify_category("Studijní oddělení přijímá žádosti studentů o stipendium.", {
        "categories": [
            {"key": "study", "role_name": "Studium", "label": "Studium", "description": "Studijní záležitosti, stipendia a zápis studentů.", "allowed_groups": ["User"]},
            {"key": "finance", "role_name": "Finance", "label": "Finance", "description": "Faktury dodavatelů, účetnictví a platby za vybavení.", "allowed_groups": ["Finance"]},
        ], "analysis_rules": "Vyber nejvhodnější kategorii podle obsahu."}))
    assert category == "study"
    summary = model_provider(models_db, user.tenant_id, "summary", "jhu-qwen", principal)
    splitter = RecursiveCharacterTextSplitter(enrich_with_summary=True, strict_summary=True, summary_provider=summary)
    enriched = splitter.split_pages([ExtractedPage(1, "Studijní oddělení přijímá žádosti o stipendium do 15. listopadu.")])
    assert enriched[0].content.startswith("[AI Shrnutí:")
    assert "Klikněte" not in enriched[0].content
