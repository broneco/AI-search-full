"""Two retained spaces, administrative preparation and exactly one selected index per chat."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid
import os
from dataclasses import replace

import pytest
from sqlalchemy import select

from app.api.routes import chat
from app.api.routes.auth import create_token
from app.core.config import settings
from app.core.model_config import ModelError
from app.ingestion import admin_indexes
from app.providers.factory import create_embedding_profile
from app.storage.models import DBActiveSearchIndex, DBChunk, DBChatThread, DBSearchIndex, DBChatMessage
from app.storage.vector_store import (activate_index, coverage, provision_index, tenant_key,
                                     write_chunks, write_embeddings)
from test_search_access import access_engine, access_db, api_client, document, user


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def experiment(access_db, tmp_path, monkeypatch):
    import app.core.tenant_config as tc
    root = tmp_path / "catalogs"
    (root / "alpha").mkdir(parents=True)
    for name in ("model_config.json", "embedding_config.json"):
        (root / "alpha" / name).write_bytes((Path(tc.TENANTS_DIR) / "jhu" / name).read_bytes())
    monkeypatch.setattr(tc, "LOCAL_TENANTS_DIR", str(root))
    from app.core.embedding_config import embedding_entry
    azure = create_embedding_profile()
    nomic = embedding_entry("alpha", "jhu-nomic").space()
    db = access_db
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.test")
    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "synthetic-key")
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "sqlserver")
    monkeypatch.setattr(admin_indexes, "can_prepare_locally", lambda session: True)
    manager = user(db, groups=["User", "Management"])
    for i, title in enumerate(("Studium", "Knihovna")):
        doc = document(db, title=title)
        write_chunks(db, [{"document_id": doc.document_id, "chunk_index": 0, "content": title,
                           "embedding": ([1.0, 0.0] if i == 0 else [0.0, 1.0]) + [0.0] * (azure.dimensions - 2),
                           "security_acl": {"allowed_groups": ["User"]}}], azure)
    old = db.scalar(select(DBSearchIndex).where(DBSearchIndex.profile_id == azure.profile_id))
    activate_index(db, old); db.commit()
    cloud_provider = SimpleNamespace(profile=azure, embed_query=AsyncMock(return_value=[1.0] + [0.0] * (azure.dimensions - 1)),
        embed_documents=AsyncMock(side_effect=AssertionError("Azure vectors are already prepared")))
    local_provider = SimpleNamespace(profile=nomic, embed_query=AsyncMock(return_value=[1.0] + [0.0] * 767),
        embed_documents=AsyncMock(side_effect=lambda texts: [[0.0, 1.0] + [0.0] * 766 if text == "Studium" else [1.0] + [0.0] * 767 for text in texts]))
    providers = {azure.profile_id: cloud_provider, nomic.profile_id: local_provider}
    monkeypatch.setattr(chat, "embedding_provider", cloud_provider)
    monkeypatch.setattr(admin_indexes, "catalog_embedding_provider", lambda tenant, name, **kwargs: local_provider if name == "jhu-nomic" else cloud_provider)
    monkeypatch.setattr("app.core.search_index_selection.catalog_embedding_provider", lambda tenant, *, space, **kwargs: providers[space.profile_id])
    monkeypatch.setattr(chat.SearchConfigManager, "load_config", AsyncMock(return_value={"context_expansion": "none", "final_limit": 1}))
    monkeypatch.setattr("app.providers.model_runtime.ProfileLLMProvider.generate", AsyncMock(return_value="Odpověď [1]"))
    return SimpleNamespace(db=db, manager=manager, headers={"Authorization": "Bearer " + create_token(manager)},
        azure=azure, nomic=nomic, old=old, cloud=cloud_provider, local=local_provider)


def prepare(client, e):
    response = client.post("/api/search-indexes/prepare", headers=e.headers, json={"embedding_profile": "jhu-nomic"})
    assert response.status_code == 200, response.text
    return response.json()["index"]["index_id"]


def test_admin_creates_second_space_preserves_corpus_and_selects_one_index(experiment, api_client):
    e = experiment
    original = {c.chunk_id: (c.content, c.embedding) for c in e.db.scalars(select(DBChunk))}
    new_id = prepare(api_client, e)
    assert prepare(api_client, e) == new_id  # idempotent resume, no duplicate index/model calls
    e.local.embed_documents.assert_awaited_once()
    index = e.db.get(DBSearchIndex, uuid.UUID(new_id))
    assert coverage(e.db, e.old) == coverage(e.db, index) == (2, 2)
    assert len(e.db.scalars(select(DBSearchIndex)).all()) == 2
    assert {c.chunk_id: (c.content, c.embedding) for c in e.db.scalars(select(DBChunk))} == original
    listing = api_client.get("/api/search-indexes", headers=e.headers).json()
    assert listing["documents"] == 2 and all(i["ready"] for i in listing["indexes"])
    assert {i["index_id"]: i["embedding_location"] for i in listing["indexes"]} == {
        str(e.old.index_id): "cloud", new_id: "local"}
    for ident, title, model in [(str(e.old.index_id), "Studium", e.azure.model_id), (new_id, "Knihovna", e.nomic.model_id)]:
        response = api_client.post("/api/chat", headers=e.headers,
            json={"query": "stejná otázka", "search_strategy": "vector", "search_index_id": ident})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["metadata"]["search_index_id"] == ident and body["metadata"]["embedding_model"] == model
        assert body["sources"][0]["title"] == title
    e.cloud.embed_query.assert_awaited_once()
    e.local.embed_query.assert_awaited_once()
    assert e.db.get(DBActiveSearchIndex, tenant_key("alpha")).index_id == e.old.index_id
    saved = e.db.scalars(select(DBChatMessage).where(DBChatMessage.role == "assistant")).all()
    assert {m.sources["generation"]["search_index_id"] for m in saved} == {str(e.old.index_id), new_id}


@pytest.mark.parametrize("problem,status", [("missing", 404), ("foreign", 404), ("incomplete", 409),
                                            ("keyword", 422), ("malformed", 422), ("unknown_profile", 503)])
def test_invalid_selection_never_falls_back_or_creates_thread(experiment, api_client, problem, status):
    e = experiment
    ident = uuid.uuid4()
    if problem in {"foreign", "incomplete"}:
        candidate = provision_index(e.db, "beta" if problem == "foreign" else "alpha", e.nomic, native=False)
        e.db.commit(); ident = candidate.index_id
    if problem == "unknown_profile":
        candidate = provision_index(e.db, "alpha", replace(e.nomic, model_revision="sha256:" + "f" * 64), native=False)
        e.db.commit(); ident = candidate.index_id
    payload = {"query": "Otázka", "search_index_id": str(ident)}
    if problem == "keyword": payload["search_strategy"] = "keyword"
    if problem == "malformed": payload["search_index_id"] = "not-a-uuid"
    before = len(e.db.scalars(select(DBChatThread)).all())
    response = api_client.post("/api/chat", headers=e.headers, json=payload)
    assert response.status_code == status, response.text
    assert len(e.db.scalars(select(DBChatThread)).all()) == before
    e.cloud.embed_query.assert_not_called(); e.local.embed_query.assert_not_called()


def test_selected_index_is_pinned_when_ingestion_default_changes(experiment, api_client):
    e = experiment
    new_id = prepare(api_client, e)
    async def query(text):
        activate_index(e.db, e.db.get(DBSearchIndex, uuid.UUID(new_id))); e.db.commit()
        return [1.0] + [0.0] * (e.azure.dimensions - 1)
    e.cloud.embed_query.side_effect = query
    response = api_client.post("/api/chat", headers=e.headers, json={"query": "Otázka", "search_strategy": "vector", "search_index_id": str(e.old.index_id)})
    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["title"] == "Studium"
    assert response.json()["metadata"]["search_index_id"] == str(e.old.index_id)
    e.local.embed_query.assert_not_called()


def test_two_indexes_of_same_profile_are_not_interchanged(experiment, api_client):
    e = experiment
    alternate = provision_index(e.db, "alpha", e.azure, native=False)
    chunks = e.db.scalars(select(DBChunk)).all()
    write_embeddings(e.db, alternate, e.azure, [{"chunk_id": c.chunk_id, "input_revision": c.content_hash,
        "embedding": ([0.0, 1.0] if c.content == "Studium" else [1.0, 0.0]) + [0.0] * (e.azure.dimensions - 2)} for c in chunks])
    e.db.commit()
    response = api_client.post("/api/chat", headers=e.headers, json={"query": "Otázka", "search_strategy": "vector", "search_index_id": str(alternate.index_id)})
    assert response.status_code == 200 and response.json()["sources"][0]["title"] == "Knihovna"
    assert e.db.get(DBActiveSearchIndex, tenant_key("alpha")).index_id == e.old.index_id


def test_permissions_and_cloud_guard(experiment, api_client, monkeypatch):
    e = experiment
    assert api_client.get("/api/search-indexes").status_code == 401
    normal = user(e.db, email="normal@example.test")
    headers = {"Authorization": "Bearer " + create_token(normal), "X-User-Groups": "Management"}
    assert api_client.get("/api/search-indexes", headers=headers).status_code == 403
    assert api_client.post("/api/search-indexes/prepare", headers=headers, json={"embedding_profile": "jhu-nomic"}).status_code == 403
    assert api_client.post("/api/chat", headers=headers, json={"query": "x", "search_index_id": str(e.old.index_id)}).status_code == 200  # Active default is available to authenticated users
    monkeypatch.setattr(admin_indexes, "can_prepare_locally", lambda session: False)
    assert api_client.post("/api/search-indexes/prepare", headers=e.headers, json={"embedding_profile": "jhu-nomic"}).status_code == 409
    e.local.embed_documents.assert_not_called()


def test_failed_model_call_is_resumable_and_revocation_prevents_writes(experiment, api_client):
    e = experiment
    e.local.embed_documents.side_effect = ModelError("embedding_timeout", "timeout", 504)
    response = api_client.post("/api/search-indexes/prepare", headers=e.headers, json={"embedding_profile": "jhu-nomic"})
    assert response.status_code == 504
    candidate = e.db.scalar(select(DBSearchIndex).where(DBSearchIndex.profile_id == e.nomic.profile_id))
    assert candidate and coverage(e.db, candidate) == (0, 2) and coverage(e.db, e.old) == (2, 2)
    async def revoked(texts):
        e.manager.groups = ["User"]; e.db.commit()
        return [[1.0] + [0.0] * 767 for _ in texts]
    e.local.embed_documents.side_effect = revoked
    response = api_client.post("/api/search-indexes/prepare", headers=e.headers, json={"embedding_profile": "jhu-nomic"})
    assert response.status_code == 403
    assert coverage(e.db, candidate) == (0, 2)


def test_actual_local_target_guard(access_db, monkeypatch):
    for key, value in {"APP_ENV": "local", "DATABASE_BACKEND": "sqlserver", "AZURE_SQL_HOST": "127.0.0.1", "AZURE_SQL_DB": "ai_search_local"}.items():
        monkeypatch.setattr(settings, key, value)
    assert admin_indexes.can_prepare_locally(access_db) == (access_db.bind.dialect.name == "mssql")
    monkeypatch.setattr(settings, "AZURE_SQL_HOST", "cloud.example.test")
    assert not admin_indexes.can_prepare_locally(access_db)


def test_live_local_admin_nomic_roundtrip(experiment, api_client, monkeypatch):
    e = experiment
    if os.getenv("RUN_JHU_EMBEDDING_TESTS") != "1" or e.db.bind.dialect.name != "mssql":
        pytest.skip("Opt-in real JHU embeddings over isolated local SQL through admin API")
    from dotenv import dotenv_values
    from app.core.embedding_config import embedding_entry
    from app.providers.ollama_embeddings import OllamaEmbeddingProvider
    from app.ingestion.extraction import DocumentExtractor
    from app.ingestion.local_demo import FIXTURE_ROOT, FIXTURES
    values = dotenv_values(".env.jhu-model")
    for key in ("JHU_LLM_ENDPOINT", "JHU_LLM_USERNAME", "JHU_LLM_PASSWORD"):
        monkeypatch.setattr(settings, key, os.getenv(key) or values.get(key))
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "JHU_LLM_ALLOW_HTTP", True)
    chunks = e.db.scalars(select(DBChunk).order_by(DBChunk.chunk_id)).all()
    for chunk, (filename, title) in zip(chunks, FIXTURES):
        chunk.content = "\n".join(page.text for page in DocumentExtractor().extract(str(FIXTURE_ROOT / filename)))
        chunk.document.title = title
    e.db.flush()
    # Azure reference vectors are synthetic; actual JHU vectors are the live part.
    write_embeddings(e.db, e.old, e.azure, [{"chunk_id": c.chunk_id, "input_revision": c.content_hash,
                                           "embedding": c.embedding} for c in chunks])
    e.db.commit()
    original = {c.chunk_id: c.content for c in chunks}
    provider = OllamaEmbeddingProvider(embedding_entry("alpha", "jhu-nomic"))
    monkeypatch.setattr(admin_indexes, "catalog_embedding_provider", lambda *args, **kwargs: provider)
    monkeypatch.setattr("app.core.search_index_selection.catalog_embedding_provider", lambda *args, **kwargs: provider)
    ident = prepare(api_client, e)
    assert coverage(e.db, e.old) == (2, 2)
    assert {c.chunk_id: c.content for c in e.db.scalars(select(DBChunk))} == original
    response = api_client.post("/api/chat", headers=e.headers,
        json={"query": "Kdy má studijní oddělení úřední hodiny?", "search_strategy": "vector", "search_index_id": ident})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"]["embedding_model"] == e.nomic.model_id and body["metadata"]["search_index_id"] == ident
    assert body["sources"]
    assert e.db.get(DBActiveSearchIndex, tenant_key("alpha")).index_id == e.old.index_id
