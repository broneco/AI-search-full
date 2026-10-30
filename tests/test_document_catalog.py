"""Constant catalog SQL cost, unchanged ACLs and a responsive event loop during slow reads."""
import asyncio
import threading
import uuid

import httpx
import pytest
from sqlalchemy import event, insert
from sqlalchemy.exc import OperationalError

from app.api.dependencies import get_db_session
from app.api.identity import Principal, get_principal
from app.api.routes import documents as routes
from app.main import app
from app.retrieval.access import access_context
from app.storage.models import DBChunk
from app.storage.document_catalog import authorized_document_rows
from test_search_access import access_engine, access_db, document, chunk


@pytest.mark.parametrize("groups", [("User",), ("User", "HR"), ("Management",)])
def test_document_and_chunk_acl_counts_stay_exact_and_do_not_leak_tenants(access_db, groups):
    db = access_db
    public = document(db, title="Visible")
    chunk(db, public, index=0)
    chunk(db, public, index=1, acl={"allowed_groups": ["HR"]})
    chunk(db, public, index=2, acl={"allowed_groups": ["User", "HR"]})
    empty = document(db, title="Empty")
    private = document(db, title="HR", acl={"allowed_groups": ["HR"]})
    chunk(db, private, acl={"allowed_groups": ["HR"]})
    for tenant in ("beta", "ALPHA", "alpha "):
        foreign = document(db, tenant=tenant, title="Other tenant")
        chunk(db, foreign)
    db.flush()
    # Inconsistent legacy rows must never inflate a visible document's count.
    db.execute(insert(DBChunk), [dict(chunk_id=uuid.uuid4(), tenant_id="beta", document_id=public.document_id,
                                      chunk_index=9, content="foreign", language="cs")])
    db.commit()
    principal = Principal(uuid.uuid4(), "alpha", groups)
    result = {doc.document_id: count for doc, count in authorized_document_rows(db, access_context(principal))}
    assert result[public.document_id] == (3 if "HR" in groups or "Management" in groups else 2)
    assert result[empty.document_id] == 0
    if "HR" in groups or "Management" in groups:
        assert result[private.document_id] == 1
        assert len(result) == 3
    else:
        assert private.document_id not in result
        assert len(result) == 2


def test_document_list_has_two_queries_for_many_documents(access_db):
    db = access_db
    for i in range(30):
        doc = document(db, title=f"Doc {i}")
        chunk(db, doc)
    db.commit()
    statements = []
    def count_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db.bind, "before_cursor_execute", count_sql)
    try:
        result = routes.list_documents(db=db, principal=Principal(uuid.uuid4(), "alpha", ("Management",)))
    finally:
        event.remove(db.bind, "before_cursor_execute", count_sql)
    assert len(result) == 30
    assert all(item["chunk_count"] == 1 for item in result)
    assert len(statements) == 2


def test_slow_document_list_does_not_block_health(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    workers = []
    principal = Principal(uuid.uuid4(), "alpha", ("Management",))
    def blocked(db, identity):
        workers.append(threading.get_ident())
        entered.set()
        assert release.wait(5), "test must release the simulated SQL read"
        return []
    monkeypatch.setattr(routes, "authorized_document_rows", blocked)
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_db_session] = lambda: object()
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            task = asyncio.create_task(client.get("/api/documents/list"))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                assert workers[0] != threading.get_ident()
                assert not task.done()
                health = await asyncio.wait_for(client.get("/api/health"), 2)
                assert health.status_code == 200
                assert not task.done()
            finally:
                release.set()
                response = await task
            assert response.status_code == 200 and response.json() == []
    try:
        asyncio.run(check())
    finally:
        app.dependency_overrides.pop(get_principal, None)
        app.dependency_overrides.pop(get_db_session, None)


def test_sql_failure_returns_safe_json_without_driver_details(monkeypatch):
    def fail(*args):
        raise OperationalError("sensitive SQL", {"private": "secret"}, Exception("private driver details"))
    monkeypatch.setattr(routes, "authorized_document_rows", fail)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        routes.list_documents(db=object(), principal=Principal(uuid.uuid4(), "alpha", ("User",)))
    assert error.value.status_code == 503
    assert "secret" not in error.value.detail and "driver" not in error.value.detail


def test_slow_retrieval_does_not_block_health(monkeypatch):
    from app.retrieval.vector import VectorRetriever
    from app.retrieval.base import QueryContext
    entered, release = threading.Event(), threading.Event()
    workers = []
    def blocked(*args, **kwargs):
        workers.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return []
    retriever = VectorRetriever(object())
    monkeypatch.setattr(retriever, "_get_fts_candidates", blocked)
    async def check():
        task = asyncio.create_task(retriever.retrieve(QueryContext(query="synthetic"),
            search_config={"search_strategy": "keyword"}))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            assert workers[0] != threading.get_ident()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                assert (await asyncio.wait_for(client.get("/api/health"), 2)).status_code == 200
            assert not task.done()
        finally:
            release.set()
            result = await task
        assert result == []
    asyncio.run(check())


@pytest.mark.parametrize("path", ["/api/prompts", "/api/chat/config", "/api/documents/categories"])
def test_slow_cloud_settings_do_not_block_health(monkeypatch, path):
    from app.core import prompts, search_config
    from app.core.config import settings
    from app.ingestion import tagger
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    entered, release = threading.Event(), threading.Event()
    workers = []
    def blocked(*args, **kwargs):
        workers.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        if path == "/api/prompts":
            return {"cs": "synthetic", "en": "synthetic"}
        return {}
    if path == "/api/prompts":
        monkeypatch.setattr(prompts, "get_tenant_prompts_map", blocked)
        from app.api.routes import prompts as prompt_routes
        monkeypatch.setattr(prompt_routes, "get_tenant_prompts_map", blocked)
    elif path == "/api/chat/config":
        monkeypatch.setattr(search_config, "load_tenant_json", blocked)
    else:
        monkeypatch.setattr(tagger, "load_tenant_json", blocked)
        # Categories are configuration-only and must not require a live model.
        monkeypatch.setattr(tagger.MetadataTagger, "__init__", lambda self, **kwargs: setattr(self, "blob_provider", object()))
    app.dependency_overrides[get_db_session] = lambda: object()
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            task = asyncio.create_task(client.get(path))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                assert workers[0] != threading.get_ident()
                assert (await asyncio.wait_for(client.get("/api/health"), 2)).status_code == 200
                assert not task.done()
            finally:
                release.set()
                response = await task
            assert response.status_code == 200
    try:
        asyncio.run(check())
    finally:
        app.dependency_overrides.pop(get_db_session, None)
