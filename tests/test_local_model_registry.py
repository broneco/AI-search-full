"""Tenant approvals, pinned inference, publication/ACL and selected-index isolation."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.api.identity import Principal
from app.api.routes.auth import create_token
from app.core.config import settings
from app.core.model_config import ModelError
from app.core import local_model_registry as registry
from app.core.model_selection import select_model
from app.providers.llm import ChatMessage
from app.providers.model_runtime import ProfileLLMProvider
from app.storage.models import DBTenantModel, DBModelAccess, DBSearchIndex, DBActiveSearchIndex, DBChatThread, DBChunk
from app.storage.vector_store import tenant_key
from test_model_catalog import models_db, models_client, account
from test_admin_indexes import experiment, prepare
from test_search_access import access_engine, access_db, api_client, user


@pytest.fixture
def anyio_backend(): return "asyncio"


@pytest.fixture
def inventory(monkeypatch):
    # Versioned recipes, including the JHU-only clean source projection.
    root = Path(__file__).resolve().parents[1] / "tenants"
    recipe_path = next(p for p in (root / "default/local_model_recipes.json", root / "jhu/local_model_recipes.json") if p.exists())
    recipes = json.loads(recipe_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(registry, "load_tenant_json", lambda *args: recipes)
    from app.core.embedding_config import embedding_entry
    nomic = embedding_entry("ju-prod", "jhu-nomic").space()
    rows = [dict(name="chat-a:latest", digest="a"*64, kind="chat_candidate", context_length=32768, capabilities=["completion"]),
            dict(name="chat-b:latest", digest="b"*64, kind="chat_candidate", context_length=4096, capabilities=["completion", "thinking"]),
            dict(name="mxbai-embed-large:latest", digest="c"*64, kind="embedding", dimensions=1024, context_length=512, capabilities=["embedding"]),
            dict(name=nomic.model_id, digest=nomic.model_revision.removeprefix("sha256:"), kind="embedding", dimensions=768, context_length=2048, capabilities=["embedding"]),
            dict(name="bge-reranker:latest", digest="d"*64, kind="reranker", context_length=512, capabilities=["completion"])]
    scan = AsyncMock(return_value={"scanned_at":"synthetic", "models":rows})
    monkeypatch.setattr("app.providers.model_discovery.discover_models", scan)
    for key,value in {"JHU_LLM_ENDPOINT":"https://models.example.test", "JHU_LLM_USERNAME":"private-user",
                      "JHU_LLM_PASSWORD":"private-password", "TENANT_ID":"ju-prod"}.items():
        monkeypatch.setattr(settings,key,value)
    return rows,scan


def add(client, headers, rows):
    return client.post("/api/models/registry",headers=headers,json={"models":[{k:m[k] for k in ("name","digest")} for m in rows]})


def test_register_all_compatible_models_is_explicit_idempotent_and_tenant_scoped(models_db,models_client,inventory):
    rows,scan=inventory
    manager,headers=account(models_db,["Management"])
    assert models_client.get("/api/models/discovery",headers=headers).status_code==200
    assert list(models_db.scalars(select(DBTenantModel)))==[]  # scan is read-only
    scan.reset_mock()
    response=add(models_client,headers,rows[:4])
    assert response.status_code==200,response.text
    records=response.json()["models"]
    assert len(records)==4 and all(not r["user_visible"] for r in records)
    scan.assert_awaited_once()  # bulk approval scans metadata once, never generates
    assert add(models_client,headers,rows[:4]).status_code==200
    assert len(list(models_db.scalars(select(DBTenantModel))))==4
    assert len(registry.model_catalog(models_db,"jhu").profiles)==3  # config alias does not share registrations
    assert len(registry.model_catalog(models_db,"ju-prod").profiles)==5
    catalog=models_client.get("/api/models",headers=headers).json()
    assert catalog["default_model_id"]=="gpt-5.4-mini"
    assert {r["id"] for r in records if r["kind"]=="chat"}<={r["id"] for r in catalog["models"]}
    assert "private" not in response.text
    profiles=registry.embedding_catalog(models_db,"ju-prod").profiles
    assert len(profiles)==3  # existing Nomic is reused, never duplicated or re-fingerprinted
    mx=next(p for p in profiles if p.space().dimensions==1024)
    assert mx.space().query_prefix=="Represent this sentence for searching relevant passages: "
    assert mx.space().document_prefix==""


def test_publication_group_rules_and_revision_cannot_be_bypassed(models_db,models_client,inventory):
    rows,_=inventory
    manager,headers=account(models_db,["Management"])
    normal,normal_headers=account(models_db)
    row=add(models_client,headers,rows[:1]).json()["models"][0]
    principal=Principal(normal.user_id,normal.tenant_id,("Management",))  # server DB still says User
    assert row["id"] not in {p["id"] for p in models_client.get("/api/models",headers=normal_headers).json()["models"]}
    with pytest.raises(ModelError) as error: select_model(models_db,normal.tenant_id,"chat",row["id"],principal)
    assert error.value.status==403
    update={"revision":1,"user_visible":True}
    assert models_client.put("/api/models/registry/"+row["id"],headers=normal_headers,json=update).status_code==403
    assert models_client.put("/api/models/registry/"+row["id"],headers=headers,json=update).status_code==200
    assert models_client.put("/api/models/registry/"+row["id"],headers=headers,json=update).status_code==409
    assert select_model(models_db,normal.tenant_id,"chat",row["id"],principal).model==rows[0]["name"]
    rule=models_client.put("/api/models/access/"+row["id"],headers=headers,json={"revision":0,"allowed_groups":["Management"]})
    assert rule.status_code==200,rule.text
    with pytest.raises(ModelError) as error: select_model(models_db,normal.tenant_id,"chat",row["id"],principal)
    assert error.value.status==403  # publishing does not override group ACL


def test_untrusted_inventory_identity_and_unsupported_models_never_write(models_db,models_client,inventory):
    rows,_=inventory
    _,headers=account(models_db,["Management"])
    _,normal_headers=account(models_db)
    assert add(models_client,{},rows[:1]).status_code==401
    assert add(models_client,{**normal_headers,"X-User-Groups":"Management"},rows[:1]).status_code==403
    forged={**rows[0],"digest":"f"*64}
    assert add(models_client,headers,[forged]).status_code==409
    assert add(models_client,headers,[rows[0],rows[-1]]).status_code==422  # all-or-nothing approval
    payload={"models":[{"name":rows[0]["name"],"digest":rows[0]["digest"],"endpoint":"https://attacker.test"}]}
    assert models_client.post("/api/models/registry",headers=headers,json=payload).status_code==422
    assert not list(models_db.scalars(select(DBTenantModel)))


def test_existing_local_choice_is_not_duplicated_and_new_digest_gets_new_profile(models_db,models_client,inventory):
    rows,_=inventory
    _,headers=account(models_db,["Management"])
    _,normal_headers=account(models_db)
    from app.core.model_config import load_model_catalog
    legacy=next(p for p in load_model_catalog("ju-prod").profiles if p.connection=="jhu")
    metadata={**rows[0],"name":legacy.model}
    rows.append(metadata)
    first=add(models_client,headers,[metadata])
    assert first.status_code==200,first.text
    first=first.json()["models"][0]
    assert first["id"]==legacy.id and first["user_visible"] is True
    assert len(registry.model_catalog(models_db,"ju-prod").profiles)==3
    assert models_client.put("/api/models/registry/"+legacy.id,headers=headers,
        json={"revision":1,"user_visible":False}).status_code==200
    assert legacy.id not in {m["id"] for m in models_client.get("/api/models",headers=normal_headers).json()["models"]}
    metadata["digest"]="f"*64
    changed=add(models_client,headers,[metadata])
    assert changed.status_code==200,changed.text
    records=changed.json()["models"]
    assert len(records)==2 and len({r["id"] for r in records})==2
    old=next(p for p in registry.model_catalog(models_db,"ju-prod").profiles if p.id==legacy.id)
    assert old.model_digest=="a"*64  # A changed tag never silently rewrites an approved profile.


def test_changed_embedding_preprocessing_keeps_old_approved_space(models_db,models_client,inventory,monkeypatch):
    rows,_=inventory
    _,headers=account(models_db,["Management"])
    original=add(models_client,headers,[rows[2]]).json()["models"][0]
    old=next(p for p in registry.embedding_catalog(models_db,"ju-prod").profiles if p.id==original["id"])
    recipes={"schema_version":1,"recipes":[{"models":["mxbai-embed-large"],"version":"explicit-new-transform-v2",
        "query_prefix":"New retrieval instruction: ","document_prefix":""}]}
    monkeypatch.setattr(registry,"load_tenant_json",lambda *args:recipes)
    discovered=models_client.get("/api/models/discovery",headers=headers).json()["models"]
    assert next(m for m in discovered if m["name"]==rows[2]["name"])["registration"] is None
    changed=add(models_client,headers,[rows[2]])
    assert changed.status_code==200,changed.text
    profiles=[p for p in registry.embedding_catalog(models_db,"ju-prod").profiles if p.space().model_id==rows[2]["name"]]
    assert len(profiles)==2 and len({p.space().profile_id for p in profiles})==2
    assert next(p for p in profiles if p.id==old.id).space()==old.space()


def test_missing_schema_keeps_file_catalog_and_migration_requires_exact_target(models_db,models_client,inventory,monkeypatch):
    from sqlalchemy import inspect
    import migrate_model_registry as migration
    _,headers=account(models_db,["Management"])
    DBTenantModel.__table__.drop(models_db.bind)
    assert models_client.get("/api/models",headers=headers).status_code==200
    assert add(models_client,headers,inventory[0][:1]).status_code==503
    inventory[1].assert_not_awaited()
    monkeypatch.setattr(settings,"USE_AZURE_SQL",True)
    monkeypatch.setattr(settings,"AZURE_SQL_HOST","127.0.0.1")
    monkeypatch.setattr(settings,"AZURE_SQL_DB","isolated-registry-test")
    monkeypatch.setattr("app.storage.db.engine",models_db.bind)
    monkeypatch.setattr("sys.argv",["migrate_model_registry.py"])
    migration.main()
    assert not inspect(models_db.bind).has_table(DBTenantModel.__tablename__)
    monkeypatch.setattr("sys.argv",["migrate_model_registry.py","--apply","--expect-host","wrong"])
    with pytest.raises(ValueError):migration.main()
    assert not inspect(models_db.bind).has_table(DBTenantModel.__tablename__)
    monkeypatch.setattr("sys.argv",["migrate_model_registry.py","--apply","--expect-host","127.0.0.1",
        "--expect-db","isolated-registry-test","--expect-tenant","ju-prod"])
    migration.main()
    assert inspect(models_db.bind).has_table(DBTenantModel.__tablename__)


def test_hidden_sql_metadata_never_hides_permission_errors(monkeypatch):
    from sqlalchemy.exc import ProgrammingError
    error=ProgrammingError("SELECT",{},Exception("42000","SELECT permission denied (229)"))
    monkeypatch.setattr(registry,"inspect",lambda conn:SimpleNamespace(has_table=lambda name:False))
    db=SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="mssql")),connection=lambda:None,
        execute=Mock(side_effect=error),scalars=Mock(side_effect=AssertionError("Permission error ignored")))
    with pytest.raises(ModelError) as caught:registry.registry_rows(db,"alpha")
    assert caught.value.code=="model_registry_unavailable"


def test_permission_change_from_another_session_invalidates_cached_policy(models_db,models_client,inventory):
    from sqlalchemy.orm import Session
    from sqlalchemy import update
    _,headers=account(models_db,["Management"])
    normal,_=account(models_db)
    row=add(models_client,headers,inventory[0][:1]).json()["models"][0]
    assert models_client.put("/api/models/registry/"+row["id"],headers=headers,
        json={"revision":1,"user_visible":True}).status_code==200
    cached=DBModelAccess(tenant_id="ju-prod",model_id=row["id"],allowed_groups=None,revision=1,updated_by="fixture")
    models_db.add(cached);models_db.commit();models_db.refresh(cached)
    with Session(models_db.bind) as other:
        other.execute(update(DBModelAccess).where(DBModelAccess.model_id==row["id"]).values(allowed_groups=[]))
        other.commit()
    assert cached.allowed_groups is None  # Deliberately retain a stale identity-map object.
    with pytest.raises(ModelError) as caught:
        select_model(models_db,"ju-prod","chat",row["id"],Principal(normal.user_id,"ju-prod",("User",)))
    assert caught.value.status==403


def test_real_absent_registry_allows_legacy_without_poisoning_transaction(access_db):
    from sqlalchemy import text
    DBTenantModel.__table__.drop(access_db.bind)
    assert registry.registry_rows(access_db,"alpha")==[]
    assert access_db.scalar(text("SELECT 1"))==1
    with pytest.raises(ModelError) as caught:registry.registry_rows(access_db,"alpha",required=True)
    assert caught.value.code=="model_registry_migration_required"


@pytest.mark.parametrize("case",["before","after","timeout","empty","mismatch","length","thinking_only"])
@pytest.mark.anyio
async def test_pinned_local_model_errors_never_fall_back(inventory,monkeypatch,case):
    rows,_=inventory
    _,profile=registry.make_profile("ju-prod",rows[0])
    calls=[]
    async def respond(request):
        calls.append(request.url.path)
        if request.url.path=="/api/tags":
            digest="f"*64 if case=="before" or (case=="after" and len(calls)>1) else rows[0]["digest"]
            return httpx.Response(200,json={"models":[{"name":profile.model,"digest":digest}]})
        assert request.url.path=="/api/generate"
        data=json.loads(request.content)
        assert data["model"]==profile.model and data["stream"] is False
        assert data["options"]=={"num_ctx":8192,"num_predict":2048}
        if case=="timeout": raise httpx.ReadTimeout("private-password",request=request)
        return httpx.Response(200,json={"model":"other" if case=="mismatch" else profile.model,"done":True,
            "done_reason":"length" if case=="length" else "stop","thinking":"private-thought",
            "response":"" if case=="empty" else "<think>private-thought</think>" if case=="thinking_only" else "Odpověď [1]"})
    original=httpx.AsyncClient
    monkeypatch.setattr("app.providers.model_runtime.httpx.AsyncClient",lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    with pytest.raises(ModelError) as error:
        await ProfileLLMProvider(profile).generate([ChatMessage(role="user",content="Česká otázka?")])
    assert "private" not in str(error.value)
    assert calls.count("/api/generate")==(0 if case=="before" else 1)


@pytest.mark.anyio
async def test_multiple_local_models_use_their_own_ids_and_bounded_context(inventory,monkeypatch):
    rows,_=inventory
    calls=[]
    async def respond(request):
        calls.append(request)
        if request.url.path=="/api/tags":return httpx.Response(200,json={"models":rows[:2]})
        body=json.loads(request.content)
        return httpx.Response(200,json={"model":body["model"],"done":True,"response":"Odpověď [1]","thinking":"not exposed"})
    original=httpx.AsyncClient
    monkeypatch.setattr("app.providers.model_runtime.httpx.AsyncClient",lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    for metadata in rows[:2]:
        _,profile=registry.make_profile("ju-prod",metadata)
        assert await ProfileLLMProvider(profile).generate([ChatMessage(role="user",content="Otázka v češtině")])=="Odpověď [1]"
        before=len(calls)
        with pytest.raises(ModelError) as error:
            await ProfileLLMProvider(profile).generate([ChatMessage(role="user",content="ř"*profile.max_input_chars)])
        assert error.value.status==422 and len(calls)==before
    assert [json.loads(c.content)["model"] for c in calls if c.url.path=="/api/generate"]==[r["name"] for r in rows[:2]]


def test_published_embedding_index_preserves_default_and_document_acl(experiment,api_client,inventory,monkeypatch):
    e=experiment
    monkeypatch.setattr(settings,"TENANT_ID","alpha")
    rows,_=inventory
    # The fixture supplies the JHU file catalogs for exact tenant alpha.
    index_id=prepare(api_client,e)
    record=add(api_client,e.headers,[rows[3]]).json()["models"][0]
    normal=user(e.db,email="registry-user@example.test")
    headers={"Authorization":"Bearer "+create_token(normal)}
    available=api_client.get("/api/search-indexes/available",headers=headers).json()["indexes"]
    assert {i["index_id"] for i in available}=={str(e.old.index_id)}
    assert api_client.post("/api/chat",headers=headers,json={"query":"x","search_index_id":index_id}).status_code==403
    response=api_client.put("/api/models/registry/"+record["id"],headers=e.headers,json={"revision":1,"user_visible":True})
    assert response.status_code==200,response.text
    assert len(api_client.get("/api/search-indexes/available",headers=headers).json()["indexes"])==2
    denied=e.db.scalar(select(DBChunk).where(DBChunk.content=="Knihovna"))
    denied.security_acl={"allowed_groups":["Management"]};e.db.commit()
    response=api_client.post("/api/chat",headers=headers,json={"query":"Stejná otázka","search_strategy":"vector","search_index_id":index_id})
    assert response.status_code==200,response.text
    assert response.json()["metadata"]["search_index_id"]==index_id
    assert response.json()["sources"][0]["title"]=="Studium"  # publication never grants forbidden chunks
    assert e.db.get(DBActiveSearchIndex,tenant_key("alpha")).index_id==e.old.index_id
    before=len(list(e.db.scalars(select(DBChatThread))))
    e.local.embed_query.reset_mock()
    api_client.put("/api/models/registry/"+record["id"],headers=e.headers,json={"revision":2,"user_visible":False})
    assert api_client.post("/api/chat",headers=headers,json={"query":"x","search_index_id":index_id}).status_code==403
    assert len(list(e.db.scalars(select(DBChatThread))))==before
    e.local.embed_query.assert_not_called()


def test_live_registry_mxbai_and_small_llm(access_db, api_client, tmp_path, monkeypatch):
    if os.getenv("RUN_JHU_EMBEDDING_TESTS") != "1" or access_db.bind.dialect.name != "mssql":
        pytest.skip("Explicit real JHU service + isolated SQL Server opt-in")
    import asyncio
    from dotenv import dotenv_values
    import app.core.tenant_config as tc
    from app.providers.factory import create_embedding_profile
    from app.storage.vector_store import write_chunks, activate_index, coverage
    from test_search_access import document
    values = dotenv_values(".env.jhu-model")
    for key in ("JHU_LLM_ENDPOINT", "JHU_LLM_USERNAME", "JHU_LLM_PASSWORD"):
        monkeypatch.setattr(settings, key, os.getenv(key) or values.get(key))
    monkeypatch.setattr(settings, "JHU_LLM_ALLOW_HTTP", True)
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "sqlserver")
    monkeypatch.setattr(settings, "AZURE_SQL_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "AZURE_SQL_DB", "ai_search_local")
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr("app.storage.db.SessionLocal", sessionmaker(bind=access_db.bind))
    root=tmp_path/"catalogs"/"alpha";root.mkdir(parents=True)
    for name in ("model_config.json","embedding_config.json"):
        (root/name).write_bytes((Path(tc.TENANTS_DIR)/"jhu"/name).read_bytes())
    monkeypatch.setattr(tc,"LOCAL_TENANTS_DIR",str(root.parent))
    manager=user(access_db,groups=["User","Management"])
    headers={"Authorization":"Bearer "+create_token(manager)}
    scan=api_client.get("/api/models/discovery",headers=headers)
    assert scan.status_code==200,scan.text
    found=scan.json()["models"]
    embedding=next(m for m in found if m["name"]=="mxbai-embed-large:latest")
    small=next(m for m in found if m["name"]=="llama3.2:3b")
    response=add(api_client,headers,[embedding,small])
    assert response.status_code==200,response.text
    records=response.json()["models"]
    llm=next(r for r in records if r["kind"]=="chat")
    profile=registry.model_catalog(access_db,"alpha")
    profile=next(p for p in profile.profiles if p.id==llm["id"])
    # One short standalone probe followed by one grounded request; never loop over the inventory.
    answer=asyncio.run(ProfileLLMProvider(profile).generate([
        ChatMessage(role="user",content="Napiš jednu krátkou větu v češtině o univerzitní knihovně.")], max_tokens=64))
    assert isinstance(answer,str) and answer.strip()
    reference=create_embedding_profile()
    for i,text in enumerate(("Studijní oddělení přijímá žádosti v pondělí a ve středu.",
                             "Univerzitní knihovna půjčuje knihy na třicet dnů.")):
        doc=document(access_db,title=f"Synthetic university {i}")
        write_chunks(access_db,[dict(document_id=doc.document_id,chunk_index=0,content=text,
            embedding=[1.0]+[0.0]*(reference.dimensions-1),security_acl={"allowed_groups":["User"]})],reference)
    original=access_db.scalar(select(DBSearchIndex).where(DBSearchIndex.profile_id==reference.profile_id))
    activate_index(access_db,original);access_db.commit()
    ids=list(access_db.scalars(select(DBChunk.chunk_id)))
    entry=next(r for r in records if r["kind"]=="embedding")
    prepared=api_client.post("/api/search-indexes/prepare",headers=headers,json={"embedding_profile":entry["id"]})
    assert prepared.status_code==200,prepared.text
    chosen=prepared.json()["index"]["index_id"]
    assert coverage(access_db,access_db.get(DBSearchIndex,uuid.UUID(chosen)))==(2,2)
    from app.api.routes import chat
    monkeypatch.setattr(chat.SearchConfigManager,"load_config",AsyncMock(return_value={"context_expansion":"none","final_limit":1}))
    result=api_client.post("/api/chat",headers=headers,json={"query":"Jak dlouho si mohu půjčit knihy?",
        "model_id":llm["id"],"search_strategy":"vector","search_index_id":chosen})
    assert result.status_code==200,result.text
    assert result.json()["sources"][0]["title"]=="Synthetic university 1"
    assert result.json()["metadata"]["search_index_id"]==chosen
    assert list(access_db.scalars(select(DBChunk.chunk_id)))==ids
    assert access_db.get(DBActiveSearchIndex,tenant_key("alpha")).index_id==original.index_id
    print(json.dumps(dict(models=len(found),llm=small["name"],embedding=embedding["name"],dimensions=embedding["dimensions"])))
