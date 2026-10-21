"""Read-only inventory classification, safe metadata and manager/tenant boundaries."""
import json
import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.core.model_config import ModelError
from app.providers.model_discovery import discover_models, public_model, _scan_slot
from test_model_catalog import models_db, models_client, account


@pytest.fixture
def anyio_backend():
    return "asyncio"


def tag(name="chat:latest", digest="a" * 64):
    return {"name": name, "digest": digest, "size": 1024}


def metadata(capabilities=None, family="llama"):
    return {"capabilities": capabilities or ["completion"], "details": {"family": family, "parameter_size": "8B"},
            "model_info": {f"{family}.embedding_length": 1024, f"{family}.context_length": 2048},
            "template": "private-template", "system": "private-system", "license": "private-license"}


@pytest.mark.parametrize("name,caps,family,kind,dimensions", [
    ("model:latest", ["completion"], "llama", "chat_candidate", None),
    ("qllama/bge-reranker-v2-m3:f16", ["completion"], "bert", "reranker", None),
    ("mxbai-embed-large:latest", ["embedding"], "bert", "embedding", 1024),
    ("bert-specialist:latest", ["completion"], "bert", "unsupported", None),
    ("unknown:latest", ["unknown-purpose"], "other", "unsupported", None),
])
def test_purpose_never_comes_from_hidden_llm_vector_dimension(name, caps, family, kind, dimensions):
    result = public_model(tag(name), metadata(caps, family))
    assert result["kind"] == kind and result["dimensions"] == dimensions
    assert "private" not in json.dumps(result)


@pytest.fixture
def discovery_http(monkeypatch):
    for key, value in {"JHU_LLM_ENDPOINT": "https://models.example.test", "JHU_LLM_USERNAME": "private-user",
                       "JHU_LLM_PASSWORD": "private-password"}.items():
        monkeypatch.setattr(settings, key, value)
    state = {"status": 200, "show_failure": False, "tags": [tag(), tag("nomic:latest", "b" * 64)],
             "running": 0, "peak": 0}
    calls = []
    async def respond(request):
        calls.append(request)
        assert request.headers["authorization"].startswith("Basic ")
        if request.url.path == "/api/tags":
            if state["status"] == "timeout": raise httpx.ReadTimeout("private-password", request=request)
            return httpx.Response(state["status"], json={"models": state["tags"], "private": "private-data"})
        assert request.method == "POST" and request.url.path == "/api/show"
        body = json.loads(request.content)
        assert set(body) == {"model"}
        state["running"] += 1
        state["peak"] = max(state["peak"], state["running"])
        await asyncio.sleep(0)
        state["running"] -= 1
        if state["show_failure"] and body["model"] == "nomic:latest":
            return httpx.Response(500, text="private-password private-data")
        return httpx.Response(200, json=metadata(["embedding"] if body["model"] == "nomic:latest" else ["completion"]))
    original = httpx.AsyncClient
    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return original(transport=httpx.MockTransport(respond), **kwargs)
    monkeypatch.setattr("app.providers.model_discovery.httpx.AsyncClient", client)
    return state, calls


@pytest.mark.anyio
async def test_inventory_is_metadata_only_and_partial_failure_is_explicit(discovery_http):
    state, calls = discovery_http
    result = await discover_models()
    assert [m["kind"] for m in result["models"]] == ["chat_candidate", "embedding"]
    assert len(calls) == 3 and "private" not in json.dumps(result)
    state["show_failure"] = True
    result = await discover_models()
    assert result["models"][1]["kind"] == "unverified"
    assert "private" not in json.dumps(result)


@pytest.mark.anyio
async def test_at_most_three_parallel_metadata_requests(discovery_http):
    state, calls = discovery_http
    state["tags"] = [tag(f"model-{i}:latest") for i in range(10)]
    result = await discover_models()
    assert len(result["models"]) == 10 and len(calls) == 11
    assert state["peak"] == 3


@pytest.mark.anyio
@pytest.mark.parametrize("status,code", [(401, "model_discovery_failed"), (500, "model_discovery_failed"),
                                       ("timeout", "model_discovery_timeout")])
async def test_discovery_failure_is_sanitized_without_retry(discovery_http, status, code):
    state, calls = discovery_http
    state["status"] = status
    with pytest.raises(ModelError) as error:
        await discover_models()
    assert error.value.code == code and "private" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("tags", [[tag("../unsafe")], [tag(digest="unknown")], [tag(), tag()], [tag()] * 201])
async def test_invalid_or_oversized_inventory_is_rejected(discovery_http, tags):
    state, calls = discovery_http
    state["tags"] = tags
    with pytest.raises(ModelError):
        await discover_models()
    assert len(calls) == 1


@pytest.mark.anyio
async def test_busy_discovery_does_not_start_http(discovery_http):
    _, calls = discovery_http
    assert _scan_slot.acquire(blocking=False)
    try:
        with pytest.raises(ModelError) as error:
            await discover_models()
        assert error.value.status == 429
    finally:
        _scan_slot.release()
    assert calls == []


def test_only_configured_tenant_manager_can_discover(models_db, models_client, monkeypatch):
    scan = AsyncMock(return_value={"scanned_at": "synthetic", "models": []})
    monkeypatch.setattr("app.providers.model_discovery.discover_models", scan)
    assert models_client.get("/api/models/discovery").status_code == 401
    _, headers = account(models_db)
    assert models_client.get("/api/models/discovery", headers=headers).status_code == 403
    _, headers = account(models_db, ["Management"])
    assert models_client.get("/api/models/discovery", headers=headers).status_code == 404
    scan.assert_not_called()


def test_jhu_manager_sees_catalog_links_but_scan_never_enables_a_model(models_db, models_client, monkeypatch):
    monkeypatch.setattr(settings, "TENANT_ID", "ju-prod")
    _, headers = account(models_db, ["Management"])
    from app.core.embedding_config import embedding_entry
    from app.core.model_config import load_model_catalog
    nomic = embedding_entry("ju-prod", "jhu-nomic").space()
    before = load_model_catalog("ju-prod").model_dump_json()
    scan = AsyncMock(return_value={"scanned_at": "synthetic", "models": [
        {"name": "qwen3.8:latest", "digest": "c" * 64},
        {"name": nomic.model_id, "digest": nomic.model_revision[7:]},
        {"name": "unapproved:latest", "digest": "d" * 64}]})
    monkeypatch.setattr("app.providers.model_discovery.discover_models", scan)
    response = models_client.get("/api/models/discovery", headers=headers)
    assert response.status_code == 200
    found = response.json()["models"]
    assert found[0]["configured_chat_ids"] == ["jhu-qwen"]
    assert found[1]["configured_embedding_ids"] == ["jhu-nomic"]
    assert found[2]["configured_chat_ids"] == found[2]["configured_embedding_ids"] == []
    assert load_model_catalog("ju-prod").model_dump_json() == before
    scan.return_value["models"][1]["digest"] = "e" * 64
    assert models_client.get("/api/models/discovery", headers=headers).json()["models"][1]["configured_embedding_ids"] == []
