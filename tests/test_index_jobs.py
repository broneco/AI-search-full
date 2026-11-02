"""Durable background operations preserve old spaces, fence workers and resume committed batches."""
from datetime import timedelta
from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.model_config import ModelError
from app.ingestion import index_jobs
from app.storage import index_jobs as store
from app.storage.models import DBIndexPreparationJob, DBChunk, DBSearchIndex
from app.storage.vector_store import coverage
from test_admin_indexes import experiment
from test_search_access import access_engine, access_db, api_client, user


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def jobs(experiment, monkeypatch):
    e = experiment
    e.starts = []
    monkeypatch.setattr(index_jobs, "launch", lambda tenant, ident: e.starts.append((tenant, ident)))
    monkeypatch.setattr(index_jobs, "catalog_embedding_provider", lambda *args, **kwargs: e.local)
    e.factory = lambda: Session(bind=e.db.bind)
    return e


def submit(client, e, *, action="create", index_id=None, profile="jhu-nomic", status=202):
    response = client.post("/api/search-indexes/jobs", headers=e.headers,
        json={"embedding_profile": profile, "action": action, "index_id": str(index_id) if index_id else None})
    assert response.status_code == status, response.text
    return response.json().get("job", response.json())


def run(e, job):
    index_jobs.run_job("alpha", uuid.UUID(job["job_id"]), e.factory)
    e.db.expire_all()
    return store.public(e.db, store.current(e.db, "alpha"))


def create(client, e):
    job = submit(client, e)
    assert job["state"] == "queued" and job["index_id"] is None
    e.local.embed_documents.assert_not_called()
    result = run(e, job)
    assert result["state"] == "completed", result
    return uuid.UUID(result["index_id"])


def test_http_ack_then_separate_creation_and_backfill_preserve_default_and_chunks(jobs, api_client):
    e = jobs
    originals = {c.chunk_id: (c.content, c.content_hash, c.embedding) for c in e.db.scalars(select(DBChunk))}
    ident = create(api_client, e)
    index = e.db.get(DBSearchIndex, ident)
    assert coverage(e.db, index) == (0, 2)
    result = run(e, submit(api_client, e, action="backfill", index_id=ident))
    assert (result["state"], result["processed_chunks"], result["valid_chunks"], result["total_chunks"]) == ("completed", 2, 2, 2)
    assert coverage(e.db, index) == coverage(e.db, e.old) == (2, 2)
    assert originals == {c.chunk_id: (c.content, c.content_hash, c.embedding) for c in e.db.scalars(select(DBChunk))}
    e.local.embed_documents.assert_awaited_once()
    result = run(e, submit(api_client, e, action="backfill", index_id=ident))
    assert result["state"] == "completed" and result["processed_chunks"] == 0
    e.local.embed_documents.assert_awaited_once()
    assert api_client.get("/api/search-indexes", headers=e.headers).json()["job"]["state"] == "completed"


def test_file_progress_is_tenant_scoped_and_tracks_committed_coverage(jobs, api_client):
    e = jobs
    ident = create(api_client, e)
    job = submit(api_client, e, action="backfill", index_id=ident)
    url = f"/api/search-indexes/jobs/{job['job_id']}/files"
    before = api_client.get(url, headers=e.headers)
    assert before.status_code == 200
    files = before.json()["files"]
    assert sum(f["total"] for f in files) == 2
    assert sum(f["valid"] for f in files) == 0
    from app.storage.models import DBDocument
    own_ids = {str(doc.document_id) for doc in e.db.scalars(select(DBDocument).where(DBDocument.tenant_id == "alpha"))}
    assert {f["id"] for f in files} <= own_ids
    seen = []
    async def embed(texts):
        with e.factory() as db:
            activity = store.public(db, store.current(db, "alpha"))["activity"]
            seen.append(activity)
        return [[1.0] + [0.0] * (e.local.profile.dimensions-1) for _ in texts]
    e.local.embed_documents.side_effect = embed
    assert run(e, job)["state"] == "completed"
    assert seen[0]["phase"] == "embedding" and set(seen[0]["document_ids"]) <= own_ids
    after = api_client.get(url, headers=e.headers).json()["files"]
    assert sum(f["valid"] for f in after) == 2
    assert all(f["state"] in {"completed", "empty"} for f in after)
    assert api_client.get(f"/api/search-indexes/jobs/{uuid.uuid4()}/files", headers=e.headers).status_code == 404


def test_failed_second_batch_is_resumable_without_repeating_first(jobs, api_client, monkeypatch):
    e = jobs
    ident = create(api_client, e)
    from app.ingestion.index_backfill import backfill_index
    async def small_batches(*args, **kwargs):
        kwargs["batch_size"] = 1
        return await backfill_index(*args, **kwargs)
    monkeypatch.setattr(index_jobs, "backfill_index", small_batches)
    e.local.embed_documents.side_effect = [[[1.0]+[0.0]*767], ModelError("model_timeout", "synthetic", 504)]
    result = run(e, submit(api_client, e, action="backfill", index_id=ident))
    assert result["state"] == "failed" and result["error_code"] == "model_timeout"
    assert result["valid_chunks"] == 1 and coverage(e.db, e.db.get(DBSearchIndex, ident)) == (1, 2)
    e.local.embed_documents.reset_mock(side_effect=True)
    e.local.embed_documents.return_value = [[1.0]+[0.0]*767]
    result = run(e, submit(api_client, e, action="backfill", index_id=ident))
    assert result["state"] == "completed" and result["processed_chunks"] == 1
    e.local.embed_documents.assert_awaited_once()


@pytest.mark.parametrize("reason", ["cancel", "revoke", "supersede"])
def test_no_batch_written_after_cancel_revocation_or_lease_takeover(jobs, api_client, reason):
    e = jobs
    ident = create(api_client, e)
    job = submit(api_client, e, action="backfill", index_id=ident)
    new_job = []
    async def interrupted(texts):
        with e.factory() as db:
            row = store.current(db, "alpha")
            if reason == "cancel":
                store.cancel(db, "alpha", row.job_id)
            elif reason == "revoke":
                from app.storage.models import DBUser
                db.get(DBUser, e.manager.user_id).groups = ["User"]
                db.commit()
            else:
                row.lease_until = store.now(db)-timedelta(seconds=1)
                db.commit()
                from app.core.embedding_config import embedding_entry
                entry = embedding_entry("alpha", "jhu-nomic", session=db)
                from app.api.identity import Principal
                replacement, _ = store.begin(db, Principal(e.manager.user_id, "alpha", ()), entry, "backfill", ident)
                new_job.append(replacement.job_id)
        return [[1.0]+[0.0]*767 for _ in texts]
    e.local.embed_documents.side_effect = interrupted
    result = run(e, job)
    assert coverage(e.db, e.db.get(DBSearchIndex, ident)) == (0, 2)
    assert coverage(e.db, e.old) == (2, 2)
    if reason == "supersede":
        assert result["job_id"] == str(new_job[0]) and result["state"] == "queued"
    else:
        assert result["state"] == ("cancelled" if reason == "cancel" else "failed")
        assert result["error_code"] == ("index_job_cancelled" if reason == "cancel" else "index_preparation_forbidden")


def test_duplicate_http_request_does_not_launch_second_worker(jobs, api_client):
    e = jobs
    job = submit(api_client, e)
    assert submit(api_client, e)["job_id"] == job["job_id"]
    assert len(e.starts) == 1
    submit(api_client, e, profile="azure-default", status=409)
    with e.factory() as db:
        assert store.claim(db, "alpha", uuid.UUID(job["job_id"]))
        assert not store.claim(db, "alpha", uuid.UUID(job["job_id"]))


def test_interrupted_status_is_read_only_and_old_worker_cannot_touch_new_job(jobs, api_client):
    e = jobs
    job = submit(api_client, e)
    row = store.current(e.db, "alpha")
    row.lease_until = store.now(e.db)-timedelta(seconds=1)
    e.db.commit()
    assert api_client.get("/api/search-indexes/jobs/current", headers=e.headers).json()["job"]["state"] == "interrupted"
    replacement = submit(api_client, e)
    assert replacement["job_id"] != job["job_id"]
    result = run(e, job)
    assert result["job_id"] == replacement["job_id"] and result["state"] == "queued"
    assert len(e.db.scalars(select(DBSearchIndex)).all()) == 1


def test_default_foreign_profile_and_current_manager_checks_precede_work(jobs, api_client):
    e = jobs
    submit(api_client, e, action="backfill", profile="azure-default", index_id=e.old.index_id, status=409)
    submit(api_client, e, action="backfill", index_id=e.old.index_id, status=422)
    submit(api_client, e, action="backfill", index_id=uuid.uuid4(), status=404)
    submit(api_client, e, action="backfill", status=422)
    assert e.starts == [] and store.current(e.db, "alpha") is None
    from app.api.routes.auth import create_token
    normal = user(e.db, email="index-user@example.test")
    headers = {"Authorization":"Bearer "+create_token(normal), "X-User-Groups":"Management"}
    for method, path in [("GET", "/api/search-indexes/jobs/current"), ("POST", "/api/search-indexes/jobs"),
                         ("POST", f"/api/search-indexes/jobs/{uuid.uuid4()}/cancel")]:
        assert api_client.request(method, path, headers=headers).status_code == 403


def test_cloud_requires_explicit_flag_mssql_and_migration(jobs, monkeypatch):
    e = jobs
    from app.ingestion import admin_indexes
    monkeypatch.setattr(admin_indexes, "can_prepare_locally", lambda db:False)
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "azure_sql")
    monkeypatch.setattr(settings, "INDEX_PREPARATION_ENABLED", False)
    assert index_jobs.capability(e.db) == (False, "index_preparation_disabled")
    monkeypatch.setattr(settings, "INDEX_PREPARATION_ENABLED", True)
    if e.db.bind.dialect.name == "mssql":
        assert index_jobs.capability(e.db) == (True, None)
        monkeypatch.setattr(store, "available", lambda db:False)
        assert index_jobs.capability(e.db) == (False, "index_jobs_migration_required")
    else:
        assert index_jobs.capability(e.db) == (False, "index_preparation_disabled")


def test_additive_migration_and_cli_target_guards(jobs, monkeypatch, capsys):
    import migrate_index_jobs as migration
    e = jobs
    migration.migrate(e.db.bind)
    migration.migrate(e.db.bind)
    assert coverage(e.db, e.old) == (2, 2)
    monkeypatch.setattr(migration, "migrate", lambda engine:pytest.fail("Wrong target must not write"))
    with pytest.raises(ValueError):
        migration.main(["--apply", "--expect-host", "wrong", "--expect-db", "wrong", "--expect-tenant", "wrong"])
    assert migration.main([]) is None
    assert "index_preparation_jobs" in capsys.readouterr().out


def test_previous_image_console_script_is_target_guarded_and_uses_canonical_ddl(jobs):
    import ast
    import migrate_index_jobs as migration
    code=migration.console_script('reviewed.database.windows.net','reviewed-db','ju-prod')
    ast.parse(code)
    assert 'CREATE TABLE index_preparation_jobs' in code
    assert 'UNIQUEIDENTIFIER' in code and 'NVARCHAR(255)' in code
    assert 'DBIndexPreparationJob' not in code
    with pytest.raises(ValueError,match='target mismatch'):
        exec(code,{})
    with pytest.raises(ValueError,match='all three'):
        migration.console_script(None,'db','tenant')
