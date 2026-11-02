"""Bounded background index creation/backfill with durable, resumable SQL checkpoints."""
import asyncio
import logging
import re
import threading

from sqlalchemy import select

from app.api.identity import Principal
from app.core.config import settings
from app.core.embedding_config import embedding_entry
from app.core.model_config import ModelError
from app.core.model_selection import check_access
from app.ingestion.index_backfill import backfill_index
from app.retrieval.filters import exact_value
from app.providers.factory import catalog_embedding_provider
from app.storage import index_jobs as store
from app.storage.models import DBActiveSearchIndex, DBSearchIndex, DBUser
from app.storage.vector_store import coverage, index_profile, provision_index, tenant_key

logger = logging.getLogger(__name__)


def capability(db):
    from app.ingestion.admin_indexes import can_prepare_locally
    local = can_prepare_locally(db)
    cloud = (settings.APP_ENV in {"dev", "prod"} and settings.DATABASE_BACKEND == "azure_sql"
             and settings.INDEX_PREPARATION_ENABLED and db.bind.dialect.name == "mssql")
    if not (local or cloud):
        return False, "index_preparation_disabled"
    if not store.available(db):
        return False, "index_jobs_migration_required"
    return True, None


def authorize(db, principal, profile_name, expected_profile=None):
    user = db.get(DBUser, principal.user_id, populate_existing=True)
    if user is None or user.tenant_id != principal.tenant_id or not isinstance(user.groups, list) or "Management" not in user.groups:
        raise ModelError("index_preparation_forbidden", "Oprávnění ke správě indexů již není platné.", 403)
    entry = embedding_entry(principal.tenant_id, profile_name, session=db)
    if expected_profile is not None and entry.space().profile_id != expected_profile:
        raise ModelError("search_index_profile_mismatch", "Embeddingový profil se změnil. Založte novou úlohu.", 409)
    check_access(db, principal, entry)
    return entry


def submit(db, principal, profile_name, action, index_id=None):
    allowed, reason = capability(db)
    if not allowed:
        raise ModelError(reason, "Správa indexů vyžaduje povolení cloudové funkce a migraci tabulky úloh.", 409)
    entry = authorize(db, principal, profile_name)
    if action == "backfill" and index_id is None:
        raise ModelError("index_id_required", "Vyberte konkrétní index k dopočítání.", 422)
    if index_id is not None:
        index = get_index(db, principal.tenant_id, index_id, entry)
        protect_default(db, index, action)
    row, started = store.begin(db, principal, entry, action, index_id)
    result = store.public(db, row)
    if started:
        launch(principal.tenant_id, row.job_id)
    return result


def get_index(db, tenant, index_id, entry):
    index = db.get(DBSearchIndex, index_id, populate_existing=True)
    if index is None or index.tenant_id != tenant or index.corpus_id != "tenant-chunks-v1":
        raise ModelError("search_index_not_found", "Index nebyl nalezen v tomto tenantu.", 404)
    if index_profile(db, index) != entry.space():
        raise ModelError("search_index_profile_mismatch", "Profil nesouhlasí s indexem.", 422)
    if settings.DATABASE_BACKEND == "azure_sql" and index.storage_kind != "native":
        raise ModelError("index_native_required", "Cloudový index musí používat nativní SQL vektory.", 409)
    return index


def protect_default(db, index, action):
    active = db.get(DBActiveSearchIndex, tenant_key(index.tenant_id))
    if action == "backfill" and active is not None and active.tenant_id == index.tenant_id and active.index_id == index.index_id:
        raise ModelError("index_ingestion_default_protected", "Výchozí ingestovaný index se touto operací nepřepočítává. Vyberte jiný index.", 409)


def launch(tenant, job_id):
    """HTTP returns immediately; SQL/model calls never run on the API event loop."""
    threading.Thread(target=run_job, args=(tenant, job_id), daemon=True, name="embedding-index-job").start()


def run_job(tenant, job_id, session_factory=None):
    from app.storage.db import SessionLocal
    factory = session_factory or SessionLocal
    stopped = threading.Event()
    lease_lost = threading.Event()

    def heartbeat():
        while not stopped.wait(15):
            try:
                with factory() as heartbeat_db:
                    store.touch(heartbeat_db, tenant, job_id)
            except Exception:
                lease_lost.set()
                return

    with factory() as db:
        try:
            allowed, reason = capability(db)
            if not allowed:
                raise ModelError(reason, "Příprava indexů není povolená.", 409)
            row = store.owned(db, tenant, job_id)
            principal = Principal(row.requested_by, tenant, ())
            profile_name, profile_id, action = row.embedding_profile, row.profile_id, row.action
            entry = authorize(db, principal, profile_name, profile_id)
            # Fence any duplicate runner before DDL/model work.
            if row.state != "queued":
                return
            if not store.claim(db, tenant, job_id):
                return
            watcher = threading.Thread(target=heartbeat, daemon=True, name="embedding-index-heartbeat")
            watcher.start()

            def check():
                if lease_lost.is_set():
                    raise ModelError("index_job_lease_lost", "Úloha ztratila platnou rezervaci.", 409)
                store.owned(db, tenant, job_id)
                authorize(db, principal, profile_name, profile_id)

            check()
            row = store.current(db, tenant)
            if row.index_id is None:
                indexes = db.scalars(select(DBSearchIndex).where(
                    exact_value(DBSearchIndex.tenant_id, tenant, db.bind.dialect.name),
                    DBSearchIndex.profile_id == profile_id)).all()
                if len(indexes) > 1:
                    raise ModelError("search_index_ambiguous", "Existuje více indexů; vyberte konkrétní index.", 409)
                index = indexes[0] if indexes else provision_index(db, tenant, entry.space(), native=settings.DATABASE_BACKEND == "azure_sql")
                index = get_index(db, tenant, index.index_id, entry)
                # DDL, catalog and job index UUID commit together; resume never guesses a table.
                row.index_id = index.index_id
                db.commit()
            else:
                index = get_index(db, tenant, row.index_id, entry)
            protect_default(db, index, action)
            initial_valid, initial_total = coverage(db, index)
            store.touch(db, tenant, job_id, valid_chunks=initial_valid, total_chunks=initial_total)
            if action == "backfill" and initial_valid != initial_total:
                if not initial_total:
                    raise ModelError("search_index_empty_corpus", "Tenant nemá žádné chunky k dopočítání.", 409)
                provider = catalog_embedding_provider(tenant, profile_name, session=db)
                def progress(completed):
                    check()
                    store.touch(db, tenant, job_id, processed_chunks=completed,
                                valid_chunks=min(initial_valid+completed, initial_total),
                                activity={"phase": "scanning", "document_ids": []})
                def activity(phase, document_ids):
                    check()
                    store.touch(db, tenant, job_id, activity={"phase": phase, "document_ids": document_ids})
                asyncio.run(backfill_index(db, index, provider=provider, batch_size=32,
                                          authorize=check, progress=progress, strict_revisions=True, activity=activity))
            elif action == "backfill" and not initial_total:
                raise ModelError("search_index_empty_corpus", "Tenant nemá žádné chunky k dopočítání.", 409)
            check()
            valid, total = coverage(db, index)
            if action == "backfill" and (valid != total or total != initial_total):
                raise ModelError("index_corpus_changed", "Korpus se během výpočtu změnil. Hotové dávky zůstaly uložené; doplňte index znovu.", 409)
            store.touch(db, tenant, job_id, state="completed", valid_chunks=valid, total_chunks=total, activity=None)
        except Exception as error:
            db.rollback()
            code = error.code if isinstance(error, ModelError) and re.fullmatch(r"[a-z][a-z0-9_]{0,79}",error.code) else "index_preparation_failed"
            try:
                store.touch(db, tenant, job_id, state="cancelled" if code == "index_job_cancelled" else "failed", error_code=code)
            except Exception:
                db.rollback()  # A superseded/expired worker cannot overwrite a newer job.
            logger.warning("Embedding index job %s ended: %s (%s)", job_id, code, type(error).__name__)
        finally:
            stopped.set()
