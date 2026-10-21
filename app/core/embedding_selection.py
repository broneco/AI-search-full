"""Resolve one provider from the tenant's active index for reads and writes."""
from app.providers.factory import catalog_embedding_provider
from app.providers.embeddings import EmbeddingProvider
from app.core.embedding_config import load_embedding_catalog
from app.core.local_model_registry import embedding_catalog
from app.core.model_config import ModelError
from sqlalchemy.orm import Session
from app.storage.models import DBActiveSearchIndex, DBSearchIndex
from app.storage.vector_store import active_index, index_profile, tenant_key, SearchIndexError


def active_embedding_provider(session: Session, tenant: str, *, fallback: EmbeddingProvider | None = None) -> EmbeddingProvider:
    catalog = embedding_catalog(session, tenant)
    active = session.get(DBActiveSearchIndex, tenant_key(tenant))
    if active is None:
        # Bootstrap ingestion before the first explicit activation.
        space = next(entry.space() for entry in catalog.profiles if entry.id == catalog.default_profile)
    else:
        index = session.get(DBSearchIndex, active.index_id)
        if active.tenant_id != tenant or index is None or index.tenant_id != tenant:
            raise SearchIndexError("Active embedding index does not belong to this tenant.")
        space = index_profile(session, index)
        active_index(session, tenant, space)  # includes corpus and storage checks
    if not any(entry.space() == space for entry in catalog.profiles):
        raise ModelError("embedding_profile_unavailable", "Profil aktivního indexu není v tenantovém katalogu.")
    if fallback is not None and fallback.profile == space:
        return fallback
    return catalog_embedding_provider(tenant, space=space, session=session)
