"""Authoritative tenant/group checks for each model call, including background work."""
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.model_config import ModelError, load_model_catalog
from app.providers.model_runtime import availability
from app.retrieval.filters import exact_value
from app.storage.models import DBModelAccess, DBUser
from app.core.local_model_registry import model_catalog, check_publication


def policy_rows(db, tenant_id):
    try:
        return list(db.scalars(select(DBModelAccess).where(
            exact_value(DBModelAccess.tenant_id, tenant_id, db.bind.dialect.name))
            .execution_options(populate_existing=True)))
    except SQLAlchemyError:
        raise ModelError("model_policy_unavailable", "Úložiště oprávnění modelů není dostupné. Ověřte migraci.") from None


def current_groups(db, principal):
    db_user = db.get(DBUser, principal.user_id, populate_existing=True)
    if db_user is None or db_user.tenant_id != principal.tenant_id or not isinstance(db_user.groups, list):
        raise ModelError("model_forbidden", "Uživatel již nemá přístup k modelu.", 403)
    return set(db_user.groups) | {"User"}


def check_access(db, principal, profile):
    groups = current_groups(db, principal)
    check_publication(db, principal, profile.id, groups)
    rule = next((r for r in policy_rows(db, principal.tenant_id) if r.model_id == profile.id), None)
    if rule is not None and rule.allowed_groups is not None and not groups.intersection(rule.allowed_groups):
        raise ModelError("model_forbidden", "K vybranému modelu nemáte oprávnění.", 403)


def select_model(db, tenant_id, purpose, model_id=None, principal=None, mode="flash"):
    catalog = model_catalog(db, tenant_id)
    ident = model_id or (catalog.advanced_chat_model if purpose == "chat" and mode == "thinking"
                         else catalog.defaults[purpose])
    profile = next((p for p in catalog.profiles if p.id == ident), None)
    if profile is None or purpose not in profile.purposes:
        raise ModelError("model_unknown", "Vybraný model není dostupný pro tuto úlohu.", 422)
    if principal is not None:
        if principal.tenant_id != tenant_id:
            raise ModelError("model_forbidden", "Nesouhlasí tenant modelu.", 403)
        check_access(db, principal, profile)
    if not availability(profile)[0]:
        raise ModelError("model_unavailable", "Vybraný model není nakonfigurovaný nebo ověřený.")
    return profile


def model_provider(db, tenant_id, purpose, model_id=None, principal=None, mode="flash"):
    from app.providers.factory import create_profile_provider
    profile = select_model(db, tenant_id, purpose, model_id, principal, mode)
    # Create a fresh session for the authorization recheck: no long-running identity snapshot.
    def authorize():
        if principal is not None:
            from app.storage.db import SessionLocal
            with SessionLocal() as session:
                check_access(session, principal, profile)
    return create_profile_provider(profile, authorize=authorize)
