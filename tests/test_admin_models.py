"""Unified model overview, mutable descriptions and isolated document prompt updates."""
import asyncio
import copy
import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.local_model_registry import embedding_catalog
from app.core.model_metadata import description_rows
from app.core.model_config import ModelError
from app.storage.models import DBModelDescription, DBTenantModel
from app.storage.vector_store import tenant_key
from test_model_catalog import models_db, models_client, account
from test_search_access import access_engine, access_db
from test_admin_indexes import experiment, prepare
from test_search_access import api_client
from test_local_model_registry import inventory, add


def test_overview_is_manager_only_public_metadata_and_combines_embeddings(models_db, models_client):
    _, ordinary = account(models_db)
    _, manager = account(models_db, ["Management"])
    assert models_client.get("/api/models/management").status_code == 401
    assert models_client.get("/api/models/management", headers=ordinary).status_code == 403
    response = models_client.get("/api/models/management", headers=manager)
    assert response.status_code == 200
    rows = response.json()["models"]
    assert {row["kind"] for row in rows} == {"chat", "embedding"}
    assert all(row["access"]["allowed_groups"] is None for row in rows)
    assert next(row for row in rows if row["kind"] == "embedding")["parameters"]["dimensions"] > 0
    assert all("purposes" in row and "parameters" in row for row in rows)
    assert "synthetic-test-key" not in response.text and "example.test" not in response.text
    assert not any(key in row for row in rows for key in ("provider", "connection", "endpoint"))


def test_descriptions_persist_cas_and_are_exact_tenant_scoped(models_db, models_client, monkeypatch):
    _, ordinary = account(models_db)
    _, manager = account(models_db, ["Management"])
    endpoint = "/api/models/descriptions/gpt-5.4-mini"
    request = {"revision": 0, "description": {"cs": "Pro studijní agendu.", "en": "For study administration."}}
    assert models_client.put(endpoint, headers=ordinary, json=request).status_code == 403
    assert models_client.put("/api/models/descriptions/forged-model", headers=manager, json=request).status_code == 422
    assert models_client.put(endpoint, headers=manager, json={**request, "endpoint": "forged"}).status_code == 422
    assert models_client.put(endpoint, headers=manager, json={**request, "description": {"cs": "x"}}).status_code == 422
    response = models_client.put(endpoint, headers=manager, json=request)
    assert response.status_code == 200 and response.json()["revision"] == 1
    assert models_client.put(endpoint, headers=manager, json=request).status_code == 409
    models_db.expire_all()
    public = models_client.get("/api/models", headers=ordinary).json()["models"]
    mini = next(row for row in public if row["id"] == "gpt-5.4-mini")
    assert mini["description"] == request["description"]
    assert "max_output_tokens" in mini["parameters"]
    changed = {**request, "revision": 1, "description": {"cs": "", "en": ""}}
    assert models_client.put(endpoint, headers=manager, json=changed).json()["revision"] == 2
    assert models_client.put(endpoint, headers=manager, json=changed).status_code == 409
    original_tenant = settings.TENANT_ID
    other = original_tenant + "-other"
    assert description_rows(models_db, other) == {}
    monkeypatch.setattr(settings, "TENANT_ID", other)
    _, other_manager = account(models_db, ["Management"], tenant=other)
    assert models_client.put(endpoint, headers=other_manager, json=request).status_code == 200
    assert len(list(models_db.scalars(select(DBModelDescription)))) == 2
    assert description_rows(models_db, original_tenant)["gpt-5.4-mini"].description == {"cs":"", "en":""}


def test_embedding_description_never_mutates_vector_identity(models_db, models_client):
    _, manager = account(models_db, ["Management"])
    entry = embedding_catalog(models_db, settings.TENANT_ID).profiles[0]
    before = copy.deepcopy(entry.model_dump())
    fingerprint = entry.space().profile_id
    response = models_client.put(f"/api/models/descriptions/{entry.id}", headers=manager,
        json={"revision":0,"description":{"cs":"Vyhledávání českých předpisů.","en":"Czech regulations retrieval."}})
    assert response.status_code == 200
    current = embedding_catalog(models_db, settings.TENANT_ID).profiles[0]
    assert current.space().profile_id == fingerprint and current.model_dump() == before
    assert list(models_db.scalars(select(DBTenantModel))) == []
    row = next(row for row in models_client.get("/api/models/management", headers=manager).json()["models"] if row["id"] == entry.id)
    assert row["description"]["cs"] == "Vyhledávání českých předpisů."


def test_missing_description_schema_preserves_catalog_but_writes_require_migration(models_db, models_client):
    _, manager = account(models_db, ["Management"])
    DBModelDescription.__table__.drop(models_db.bind)
    assert models_client.get("/api/models", headers=manager).status_code == 200
    response = models_client.put("/api/models/descriptions/gpt-5.4-mini", headers=manager,
        json={"revision":0,"description":{"cs":"x","en":"x"}})
    assert response.status_code == 503
    assert response.json()["code"] == "model_metadata_migration_required"


def test_document_prompt_patch_preserves_categories_acl_and_chunking(models_db, models_client, monkeypatch):
    from app.core.search_config import SearchConfigManager
    from app.ingestion.tagger import MetadataTagger
    from app.core.tenant_config import save_tenant_json, load_tenant_json
    monkeypatch.setattr("app.providers.blob_storage.BlobStorageProvider.is_configured", lambda _: False)
    _, ordinary = account(models_db)
    _, manager = account(models_db, ["Management"])
    search = SearchConfigManager().get_defaults()
    search.update(chunk_size=777, enrich_with_summary=True, summary_custom_prompt="Before")
    categories = {"categories":[{"key":"synthetic", "label":"Studium", "allowed_groups":["HR"]}], "analysis_rules":"Before"}
    save_tenant_json(settings.TENANT_ID, "search_config.json", search)
    save_tenant_json(settings.TENANT_ID, "classification_config.json", categories)
    for purpose in ("summary", "classification"):
        endpoint = f"/api/prompts/tasks/{purpose}"
        assert models_client.put(endpoint, headers=ordinary, json={"prompt_text":"forged"}).status_code == 403
        response = models_client.put(endpoint, headers=manager, json={"prompt_text":" Česká instrukce. "})
        assert response.status_code == 200
    saved_search = asyncio.run(SearchConfigManager().load_config())
    saved_categories = asyncio.run(MetadataTagger(llm_provider=object()).load_config())
    assert saved_search == {**search, "summary_custom_prompt":"Česká instrukce."}
    assert saved_categories == {**categories, "analysis_rules":"Česká instrukce."}
    assert models_client.put("/api/prompts/tasks/summary", headers=manager, json={"prompt_text":""}).status_code == 200
    assert models_client.put("/api/prompts/tasks/summary", headers=manager, json={"prompt_text":"x"*16001}).status_code == 422
    assert models_client.put("/api/prompts/tasks/unknown", headers=manager, json={"prompt_text":"x"}).status_code == 422


def test_description_migration_is_read_only_until_exact_target_confirmed(models_db, monkeypatch, capsys):
    import migrate_model_metadata as migration
    monkeypatch.setattr("app.storage.db.engine", models_db.bind)
    DBModelDescription.__table__.drop(models_db.bind)
    monkeypatch.setattr("sys.argv", ["migrate_model_metadata.py"])
    migration.main()
    assert json.loads(capsys.readouterr().out)["apply"] is False
    monkeypatch.setattr("sys.argv", ["migrate_model_metadata.py", "--apply", "--expect-host", "wrong"])
    with pytest.raises(ValueError):
        migration.main()
    host = settings.AZURE_SQL_HOST if settings.USE_AZURE_SQL else settings.POSTGRES_HOST
    database = settings.AZURE_SQL_DB if settings.USE_AZURE_SQL else settings.POSTGRES_DB
    monkeypatch.setattr("sys.argv", ["migrate_model_metadata.py", "--apply", "--expect-host", host,
                                    "--expect-db", database, "--expect-tenant", settings.TENANT_ID])
    migration.main()
    assert description_rows(models_db, settings.TENANT_ID, required=True) == {}


def test_description_repository_unicode_isolation_and_real_missing_table(access_db):
    from types import SimpleNamespace
    from sqlalchemy import text
    from app.core.model_metadata import save_description
    principal = SimpleNamespace(tenant_id="Alpha-prod", user_id="synthetic")
    saved = save_description(access_db, principal, "model", 0, {"cs":"Studijní oddělení — český popis", "en":"Study office"})
    assert saved["revision"] == 1
    assert description_rows(access_db, "Alpha-prod")["model"].description["cs"] == "Studijní oddělení — český popis"
    assert description_rows(access_db, "alpha-prod") == {}
    DBModelDescription.__table__.drop(access_db.bind)
    assert description_rows(access_db, "Alpha-prod") == {}
    assert access_db.scalar(text("SELECT 1")) == 1


def test_hidden_description_metadata_fails_closed_on_sql_permission_denial(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from sqlalchemy.exc import ProgrammingError
    import app.core.model_metadata as metadata
    monkeypatch.setattr(metadata,"inspect",lambda _:SimpleNamespace(has_table=lambda _:False))
    db=SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="mssql")),connection=lambda:None,
        execute=Mock(side_effect=ProgrammingError("SELECT",{},Exception("42000","SELECT permission denied"))))
    with pytest.raises(ModelError) as caught:
        metadata.description_rows(db,"tenant")
    assert caught.value.code == "model_metadata_unavailable"


def test_comparison_keeps_model_index_and_history_per_variant(experiment, api_client, monkeypatch):
    e = experiment
    second_index = prepare(api_client, e)
    monkeypatch.setattr(settings, "AZURE_OPENAI_THINKING_DEPLOYMENT", "advanced-synthetic")
    calls = []

    async def generate(provider, messages, **kwargs):
        calls.append((provider.profile.id, [(message.role, message.content) for message in messages]))
        return f"Odpověď modelu {provider.profile.id} [1]"

    monkeypatch.setattr("app.providers.model_runtime.ProfileLLMProvider.generate", generate)
    variants = [("gpt-5.4-mini", str(e.old.index_id)), ("gpt-5.4", second_index)]
    threads = {}
    for question in ("Kde najdu informace?", "A jak to funguje dál?"):
        for model, index in variants:
            response = api_client.post("/api/chat", headers=e.headers,
                json={"query":question, "model_id":model, "search_index_id":index,
                      "search_strategy":"vector", "thread_id":threads.get(model)})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["metadata"]["model_id"] == model
            assert body["metadata"]["search_index_id"] == index
            threads[model] = body["thread_id"]
    assert len(set(threads.values())) == 2
    assert [ident for ident, _ in calls] == ["gpt-5.4-mini", "gpt-5.4"] * 2
    for model, transcript in calls[2:]:
        assistants = [text for role, text in transcript if role == "assistant"]
        assert assistants == [f"Odpověď modelu {model} [1]"]
    e.cloud.embed_query.assert_awaited()
    e.local.embed_query.assert_awaited()


def test_output_limit_authorization_persistence_cas_reset_and_tenant_scope(models_db, models_client, monkeypatch):
    from app.core.model_selection import select_model
    from app.storage.models import DBModelRuntimeSettings
    _, ordinary = account(models_db)
    _, manager = account(models_db, ["Management"])
    endpoint = "/api/models/runtime/gpt-5.4-mini"
    request = {"revision":0,"max_output_tokens":1024}
    assert models_client.put(endpoint, json=request).status_code == 401
    assert models_client.put(endpoint, headers=ordinary, json=request).status_code == 403
    initial = next(row for row in models_client.get("/api/models/management",headers=manager).json()["models"] if row["id"] == "gpt-5.4-mini")
    assert initial["runtime"]["max_output_tokens"] is None
    response = models_client.put(endpoint, headers=manager, json=request)
    assert response.status_code == 200 and response.json()["runtime"]["revision"] == 1
    models_db.expire_all()
    for purpose in ("chat","summary","classification"):
        assert select_model(models_db, settings.TENANT_ID, purpose, "gpt-5.4-mini").max_output_tokens == 1024
    for purpose in ("chat","summary","classification"):
        catalog = models_client.get(f"/api/models?purpose={purpose}",headers=ordinary).json()["models"]
        assert next(p for p in catalog if p["id"] == "gpt-5.4-mini")["parameters"]["max_output_tokens"] == 1024
    assert models_client.put(endpoint, headers=manager, json=request).status_code == 409
    reset = models_client.put(endpoint, headers=manager, json={"revision":1,"max_output_tokens":None})
    assert reset.status_code == 200
    assert reset.json()["runtime"]["revision"] == 2 and reset.json()["runtime"]["effective_max_output_tokens"] == 4096
    assert models_client.put(endpoint, headers=manager, json=request).status_code == 409
    # Configuration fallback/alias never shares runtime settings across exact tenants.
    original = settings.TENANT_ID
    monkeypatch.setattr(settings,"TENANT_ID",original+"-other")
    _, other_manager = account(models_db,["Management"])
    assert models_client.put(endpoint,headers=other_manager,json=request).status_code == 200
    assert select_model(models_db, original, "chat", "gpt-5.4-mini").max_output_tokens == 4096
    assert len(list(models_db.scalars(select(DBModelRuntimeSettings)))) == 2


@pytest.mark.parametrize("value", [127,32769,-1,2048.5,"2048",True])
def test_output_limit_rejects_invalid_input_without_writes(models_db,models_client,value):
    from app.storage.models import DBModelRuntimeSettings
    _,manager=account(models_db,["Management"])
    response=models_client.put("/api/models/runtime/gpt-5.4-mini",headers=manager,
        json={"revision":0,"max_output_tokens":value})
    assert response.status_code == 422
    assert not list(models_db.scalars(select(DBModelRuntimeSettings)))


def test_registered_local_limit_keeps_identity_and_validates_context_before_generation(models_db,models_client,inventory,monkeypatch):
    import httpx
    from app.core.model_selection import select_model
    from app.providers.llm import ChatMessage
    from app.providers.model_runtime import ProfileLLMProvider
    _,manager=account(models_db,["Management"])
    registered=add(models_client,manager,inventory[0][:1]).json()["models"][0]
    ident=registered["id"]
    row=models_db.get(DBTenantModel,(tenant_key(settings.TENANT_ID),ident))
    snapshot=copy.deepcopy(row.profile_json)
    assert models_client.put(f"/api/models/runtime/{ident}",headers=manager,
        json={"revision":0,"max_output_tokens":8192}).status_code == 422
    result=models_client.put(f"/api/models/runtime/{ident}",headers=manager,
        json={"revision":0,"max_output_tokens":4096})
    assert result.status_code == 200
    assert result.json()["runtime"]["maximum"] == 6912
    assert result.json()["parameters"]["max_input_chars"] == 3840
    assert row.profile_json == snapshot and row.revision == 1
    profile=select_model(models_db,settings.TENANT_ID,"chat",ident)
    calls=[]
    def handler(request):
        calls.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200,json={"models":[{"name":profile.model,"digest":profile.model_digest}]})
        assert json.loads(request.content)["options"] == {"num_ctx":8192,"num_predict":4096}
        return httpx.Response(200,json={"model":profile.model,"response":"Odpověď [1]","done":True})
    original=httpx.AsyncClient
    monkeypatch.setattr("app.providers.model_runtime.httpx.AsyncClient",lambda **kw:original(**kw,transport=httpx.MockTransport(handler)))
    provider=ProfileLLMProvider(profile)
    assert asyncio.run(provider.generate([ChatMessage(role="user",content="Ahoj")])) == "Odpověď [1]"
    calls.clear()
    with pytest.raises(ModelError) as caught:
        asyncio.run(provider.generate([ChatMessage(role="user",content="a"*4000)]))
    assert caught.value.code == "model_input_too_large" and calls == []
    # Input-bound reductions are reversible and do not alter the registry snapshot.
    assert models_client.put(f"/api/models/runtime/{ident}",headers=manager,
        json={"revision":1,"max_output_tokens":None}).json()["parameters"]["max_input_chars"] == snapshot["max_input_chars"]
    embedding_id=embedding_catalog(models_db,settings.TENANT_ID).profiles[0].id
    assert models_client.put(f"/api/models/runtime/{embedding_id}",headers=manager,
        json={"revision":0,"max_output_tokens":1024}).status_code == 422


def test_runtime_azure_provider_caps_per_call_and_db_tagger_uses_override(models_db,models_client,monkeypatch):
    from types import SimpleNamespace
    from app.core.model_selection import model_provider
    from app.providers.llm import ChatMessage
    from app.ingestion.tagger import MetadataTagger
    _,manager=account(models_db,["Management"])
    assert models_client.put("/api/models/runtime/gpt-5.4-mini",headers=manager,
        json={"revision":0,"max_output_tokens":512}).status_code == 200
    calls=[]
    class Client:
        def __init__(self,**kwargs):self.chat=SimpleNamespace(completions=self)
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def create(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="answer"),finish_reason="stop")])
    monkeypatch.setattr("app.providers.model_runtime.AsyncAzureOpenAI",Client)
    for purpose in ("chat","summary","classification"):
        provider=model_provider(models_db,settings.TENANT_ID,purpose)
        asyncio.run(provider.generate([ChatMessage(role="user",content="Ahoj")],max_tokens=99999))
    assert [call["max_completion_tokens"] for call in calls] == [512]*3
    tagger=MetadataTagger(db_session=models_db)
    assert tagger.llm.profile.max_output_tokens == 512


def test_missing_runtime_schema_keeps_catalog_and_requires_explicit_migration(models_db,models_client):
    from app.storage.models import DBModelRuntimeSettings
    _,manager=account(models_db,["Management"])
    DBModelRuntimeSettings.__table__.drop(models_db.bind)
    assert models_client.get("/api/models",headers=manager).status_code == 200
    response=models_client.put("/api/models/runtime/gpt-5.4-mini",headers=manager,
        json={"revision":0,"max_output_tokens":1024})
    assert response.status_code == 503 and response.json()["code"] == "model_limits_migration_required"


def test_runtime_repository_and_migration_guards(access_db,monkeypatch,capsys):
    from sqlalchemy import text
    from app.core.model_config import load_model_catalog
    from app.core.model_limits import save_limit,limit_rows
    from app.storage.models import DBModelRuntimeSettings
    import migrate_model_limits as migration
    monkeypatch.setattr("app.storage.db.engine",access_db.bind)
    profile=load_model_catalog("ju-prod").profiles[0]
    assert save_limit(access_db,"Alpha-prod","synthetic",profile,0,1024)["runtime"]["revision"] == 1
    assert limit_rows(access_db,"alpha-prod") == {}
    DBModelRuntimeSettings.__table__.drop(access_db.bind)
    assert limit_rows(access_db,"Alpha-prod") == {} and access_db.scalar(text("SELECT 1")) == 1
    monkeypatch.setattr("sys.argv",["migrate_model_limits.py"])
    migration.main()
    assert json.loads(capsys.readouterr().out)["apply"] is False
    monkeypatch.setattr("sys.argv",["migrate_model_limits.py","--apply","--expect-host","wrong"])
    with pytest.raises(ValueError):migration.main()
    host=settings.AZURE_SQL_HOST if settings.USE_AZURE_SQL else settings.POSTGRES_HOST
    database=settings.AZURE_SQL_DB if settings.USE_AZURE_SQL else settings.POSTGRES_DB
    monkeypatch.setattr("sys.argv",["migrate_model_limits.py","--apply","--expect-host",host,"--expect-db",database,"--expect-tenant",settings.TENANT_ID])
    migration.main()
    assert limit_rows(access_db,"Alpha-prod",required=True) == {}
