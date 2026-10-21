"""Local administrative preparation reuses transactional, resumable backfill."""
import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embedding_config import embedding_entry, load_embedding_catalog
from app.core.model_config import ModelError
from app.core.local_model_registry import embedding_catalog, check_embedding_access
from app.core.search_index_selection import selected_index
from app.ingestion.index_backfill import backfill_index
from app.providers.factory import catalog_embedding_provider
from app.retrieval.filters import exact_value
from app.storage.models import DBActiveSearchIndex, DBChunk, DBDocument, DBSearchIndex, DBUser
from app.storage.vector_store import coverage, index_profile, provision_index, tenant_key

_prepare_slot = threading.BoundedSemaphore(1)


def can_prepare_locally(session: Session) -> bool:
    return (settings.APP_ENV == "local" and settings.DATABASE_BACKEND == "sqlserver"
            and settings.AZURE_SQL_HOST in {"localhost", "127.0.0.1", "::1"}
            and settings.AZURE_SQL_DB == "ai_search_local" and session.bind.dialect.name == "mssql")


def index_description(session, index, entries, active):
    space = index_profile(session, index)
    entry = next((entry for entry in entries if entry.space() == space), None)
    valid, total = coverage(session, index)
    return dict(index_id=str(index.index_id), model=space.model_id, dimensions=space.dimensions,
                embedding_location=("local" if entry.provider == "ollama_embed" else "cloud") if entry else None,
                profile_id=space.profile_id, embedding_profile=entry.id if entry else None,
                valid_chunks=valid, total_chunks=total, ready=bool(entry and total and valid == total),
                ingestion_default=bool(active and active.tenant_id == index.tenant_id and active.index_id == index.index_id))


def list_indexes(session: Session, tenant: str) -> dict:
    catalog = embedding_catalog(session, tenant)
    indexes = session.scalars(select(DBSearchIndex).where(
        exact_value(DBSearchIndex.tenant_id, tenant, session.bind.dialect.name)).order_by(DBSearchIndex.index_id)).all()
    active = session.get(DBActiveSearchIndex, tenant_key(tenant))
    documents = session.scalar(select(func.count()).select_from(DBDocument).where(
        exact_value(DBDocument.tenant_id, tenant, session.bind.dialect.name)))
    return dict(indexes=[index_description(session, index, catalog.profiles, active) for index in indexes],
                profiles=[dict(id=entry.id, model=entry.space().model_id, dimensions=entry.space().dimensions)
                          for entry in catalog.profiles], documents=documents,
                can_prepare=can_prepare_locally(session))


def available_query_indexes(session: Session, principal) -> dict:
    """Check publication/ACL before expensive coverage; expose no corpus counts."""
    tenant = principal.tenant_id
    entries = {e.space().profile_id: e for e in embedding_catalog(session, tenant).profiles}
    active = session.get(DBActiveSearchIndex, tenant_key(tenant))
    candidates = session.scalars(select(DBSearchIndex).where(
        exact_value(DBSearchIndex.tenant_id, tenant, session.bind.dialect.name)))
    indexes = []
    for index in candidates:
        entry = entries.get(index.profile_id)
        if entry is None or index.corpus_id != "tenant-chunks-v1":
            continue
        try:
            check_embedding_access(session, principal, entry, index.index_id)
        except ModelError as error:
            if error.status == 403:
                continue
            raise
        valid, total = coverage(session, index)
        if total and valid == total:
            indexes.append(dict(index_id=str(index.index_id), model=entry.space().model_id,
                dimensions=entry.space().dimensions,
                ingestion_default=bool(active and active.tenant_id == tenant and active.index_id == index.index_id)))
    return {"indexes": indexes}


async def prepare_index(session: Session, principal, profile_name: str, index_id=None) -> dict:
    if not can_prepare_locally(session):
        raise ModelError("index_preparation_requires_handoff", "Příprava z konzole je dostupná jen pro lokální SQL. Cloud vyžaduje řízenou migraci.", 409)
    entry = embedding_entry(principal.tenant_id, profile_name, session=session)
    provider = catalog_embedding_provider(principal.tenant_id, profile_name, session=session)
    if not _prepare_slot.acquire(blocking=False):
        raise ModelError("index_preparation_busy", "Jiný index se právě připravuje. Zkuste to později.", 429)
    def authorize():
        user = session.get(DBUser, principal.user_id, populate_existing=True)
        if (user is None or user.tenant_id != principal.tenant_id or not isinstance(user.groups, list)
                or "Management" not in user.groups):
            raise ModelError("index_preparation_forbidden", "Oprávnění ke správě indexů již není platné.", 403)
        from app.core.model_selection import check_access
        check_access(session, principal, entry)
    try:
        authorize()
        if index_id is not None:
            index = selected_index(session, principal.tenant_id, index_id)
            if index.profile_id != entry.space().profile_id:
                raise ModelError("search_index_profile_mismatch", "Profil nesouhlasí s vybraným indexem.", 422)
        else:
            indexes = session.scalars(select(DBSearchIndex).where(
                exact_value(DBSearchIndex.tenant_id, principal.tenant_id, session.bind.dialect.name),
                DBSearchIndex.profile_id == entry.space().profile_id)).all()
            if len(indexes) > 1:
                raise ModelError("search_index_ambiguous", "Existuje více indexů tohoto profilu. Zvolte konkrétní index k doplnění.", 409)
            total = session.scalar(select(func.count()).select_from(DBChunk).join(DBDocument).where(
                exact_value(DBChunk.tenant_id, principal.tenant_id, session.bind.dialect.name),
                exact_value(DBDocument.tenant_id, principal.tenant_id, session.bind.dialect.name)))
            if not total:
                raise ModelError("search_index_empty_corpus", "Nejdříve nahrajte dokumenty do tohoto tenantu.", 409)
            index = indexes[0] if indexes else provision_index(session, principal.tenant_id, entry.space(), native=False)
            session.commit()  # preserve a resumable index even if a later provider call fails
        count = await backfill_index(session, index, provider=provider, authorize=authorize)
        authorize()
        active = session.get(DBActiveSearchIndex, tenant_key(principal.tenant_id))
        return dict(index=index_description(session, index, [entry], active), backfilled_chunks=count)
    finally:
        _prepare_slot.release()
