"""Bind an explicit administrative query to one existing tenant index."""
import uuid

from sqlalchemy.orm import Session

from app.core.embedding_config import embedding_entry
from app.core.model_config import ModelError
from app.providers.factory import catalog_embedding_provider
from app.storage.models import DBSearchIndex
from app.storage.vector_store import coverage, index_profile


def selected_index(session: Session, tenant: str, ident: uuid.UUID) -> DBSearchIndex:
    index = session.get(DBSearchIndex, ident)
    if index is None or index.tenant_id != tenant or index.corpus_id != "tenant-chunks-v1":
        raise ModelError("search_index_unavailable", "Vybraný index není dostupný pro tento tenant.", 404)
    return index


def selected_embedding_provider(session: Session, tenant: str, ident: uuid.UUID, *, fallback=None):
    index = selected_index(session, tenant, ident)
    space = index_profile(session, index)
    embedding_entry(tenant, space=space, session=session)  # no same-dimension substitution or unknown profile
    valid, total = coverage(session, index)
    if valid != total or total == 0:
        raise ModelError("search_index_incomplete", "Vybraný index není naplněný pro aktuální dokumenty. Doplňte embeddingy.", 409)
    provider = fallback if fallback is not None and fallback.profile == space else catalog_embedding_provider(tenant, space=space, session=session)
    return index, provider
