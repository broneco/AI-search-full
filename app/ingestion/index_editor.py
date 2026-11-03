"""Create/reconfigure a logical index, publishing a complete replacement atomically."""
from sqlalchemy import select
from sqlalchemy.orm import Session
import uuid
from app.api.identity import Principal
from app.core.model_config import ModelError
from app.core.search_config import SearchConfigManager
from app.core.search_index_selection import selected_index
from app.core.local_model_registry import embedding_catalog
from app.core.model_selection import model_provider
from app.ingestion.chunk_settings import ChunkingSettings
from app.ingestion import index_jobs
from app.storage import index_jobs as store
from app.storage.index_settings import available, initialize_legacy, metadata
from app.storage.models import DBIndexSettings
from app.storage.vector_store import index_profile, provision_index
from app.core.config import settings


def initialize(db: Session, principal: Principal) -> int:
    if not available(db):
        raise ModelError("index_settings_migration_required", "Editor indexů vyžaduje databázovou migraci.", 503)
    values = SearchConfigManager().load_config_sync()
    snapshot = ChunkingSettings.model_validate({k:v for k,v in values.items() if k in ChunkingSettings.model_fields}).model_dump()
    return initialize_legacy(db, principal.tenant_id, snapshot)


def save(db: Session, principal: Principal, *, chunking: dict, name: str | None, profile_name: str | None,
         index_id: uuid.UUID | None = None, expected_revision: int | None = None) -> dict:
    if index_id is None:
        if not profile_name:
            raise ModelError("embedding_profile_required", "Vyberte embeddingový model.", 422)
        return index_jobs.submit(db, principal, profile_name, "create", chunking=chunking, name=name, populate=True)
    allowed, reason = index_jobs.capability(db)
    if not allowed or not available(db):
        raise ModelError(reason or "index_settings_migration_required", "Editor indexů není dostupný.", 409)
    root = selected_index(db, principal.tenant_id, index_id, resolve=False)
    spec = metadata(db, root)
    if spec is None or spec.owner_index_id is not None:
        raise ModelError("index_settings_conflict", "Obnovte přehled a vyberte původní index.", 409)
    entry = next((p for p in embedding_catalog(db, principal.tenant_id).profiles if p.space()==index_profile(db, root)), None)
    if entry is None or (profile_name and profile_name != entry.id):
        raise ModelError("search_index_profile_mismatch", "Embeddingový model existujícího indexu nelze změnit.", 422)
    index_jobs.authorize(db, principal, entry.id)
    config = ChunkingSettings.model_validate(chunking)
    if config.enrich_with_summary:
        config.summary_model_id = model_provider(db, principal.tenant_id, "summary", config.summary_model_id, principal).profile.id
    if config.chunking_strategy == "agentic":
        config.classification_model_id = model_provider(db, principal.tenant_id, "classification", config.classification_model_id, principal).profile.id
    desired_name = name or spec.name
    # The singleton lease fences both construction and publication. A stale form writes nothing.
    if spec.revision != expected_revision:
        raise ModelError("index_settings_conflict", "Index se mezitím změnil; obnovte editor.", 409)
    previous = store.current(db, principal.tenant_id)
    pending_id = previous.index_id if previous else None
    row, started = store.begin(db, principal, entry, "backfill", pending_id)
    if not started:
        raise ModelError("index_preparation_busy", "Jiná úloha právě běží.", 409)
    try:
        store.owned(db, principal.tenant_id, row.job_id)
        spec = db.scalar(select(DBIndexSettings).where(DBIndexSettings.index_id==root.index_id)
            .with_hint(DBIndexSettings, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql").execution_options(populate_existing=True))
        if spec is None or spec.revision != expected_revision:
            raise ModelError("index_settings_conflict", "Index se mezitím změnil; obnovte editor.", 409)
        from app.storage.models import DBSearchIndex
        pending = db.get(DBSearchIndex, pending_id) if pending_id else None
        pending_spec = metadata(db, pending) if pending is not None and pending.tenant_id==principal.tenant_id else None
        if not (pending_spec and pending_spec.owner_index_id==root.index_id and pending_spec.base_revision==spec.revision
                and pending_spec.chunking==config.model_dump() and pending_spec.name==desired_name):
            pending = provision_index(db, principal.tenant_id, entry.space(), native=settings.DATABASE_BACKEND=="azure_sql", isolated=True)
            db.add(DBIndexSettings(index_id=pending.index_id, tenant_id=principal.tenant_id, name=desired_name,
                chunking=config.model_dump(), settings_origin="recorded", owner_index_id=root.index_id, base_revision=spec.revision))
        row.index_id = pending.index_id
        db.commit()
    except Exception:
        db.rollback()
        store.touch(db, principal.tenant_id, row.job_id, state="failed", error_code="index_reconfiguration_failed")
        raise
    result = store.public(db, store.current(db, principal.tenant_id))
    index_jobs.launch(principal.tenant_id, row.job_id)
    return result
