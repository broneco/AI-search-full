"""Explicit tenant approvals of discovered local models; no endpoint or secret storage."""
from datetime import datetime
import hashlib
import json

from sqlalchemy import inspect, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.model_config import ModelError, ModelProfile, load_model_catalog
from app.core.embedding_config import EmbeddingEntry, load_embedding_catalog
from app.core.tenant_config import load_tenant_json
from app.providers.embeddings import EmbeddingProfile
from app.storage.models import DBTenantModel, DBActiveSearchIndex
from app.storage.vector_store import tenant_key


def registry_rows(db, tenant, *, required=False):
    try:
        if not inspect(db.connection()).has_table(DBTenantModel.__tablename__):
            missing = True
            if db.bind.dialect.name == "mssql":
                # SQL Server can hide metadata when table permissions are missing.
                # Only a real missing-table error permits legacy file catalogs.
                try:
                    db.execute(select(DBTenantModel).limit(0))
                    missing = False
                except SQLAlchemyError as error:
                    args = getattr(getattr(error, "orig", None), "args", ())
                    if not args or args[0] != "42S02":
                        raise
            if missing:
                if required:
                    raise ModelError("model_registry_migration_required", "Restartujte lokální backend; v Azure je nutná migrace registru modelů.")
                return []
        rows = list(db.scalars(select(DBTenantModel).where(DBTenantModel.tenant_key == tenant_key(tenant))
                               .execution_options(populate_existing=True)))
        if any(row.tenant_id != tenant for row in rows):
            raise ValueError("Tenant registry mismatch")
        return rows
    except (SQLAlchemyError, ValueError):
        raise ModelError("model_registry_unavailable", "Registr modelů není dostupný.") from None


def registered(db, tenant, ident):
    return next((row for row in registry_rows(db, tenant) if row.model_id == ident), None)


def model_catalog(db, tenant, *, runtime_settings=True):
    catalog = load_model_catalog(tenant)
    profiles = {p.id: p for p in catalog.profiles}
    for row in registry_rows(db, tenant):
        if row.kind == "chat":
            profile = ModelProfile.model_validate(row.profile_json)
            if profile.id != row.model_id or not profile.model_digest or profile.connection != "jhu":
                raise ModelError("model_registry_invalid", "Profil v registru modelů není platný.")
            profiles[profile.id] = profile
    result = list(profiles.values())
    if runtime_settings:
        from app.core.model_limits import apply_limits
        result = apply_limits(db, tenant, result)
    return catalog.model_copy(update={"profiles": result})


def embedding_catalog(db, tenant):
    catalog = load_embedding_catalog(tenant)
    profiles = {p.id: p for p in catalog.profiles}
    for row in registry_rows(db, tenant):
        if row.kind == "embedding":
            entry = EmbeddingEntry.model_validate(row.profile_json)
            if entry.id != row.model_id or entry.provider != "ollama_embed":
                raise ModelError("model_registry_invalid", "Embedding v registru modelů není platný.")
            profiles[entry.id] = entry
    return catalog.model_copy(update={"profiles": list(profiles.values())})


def check_publication(db, principal, ident, groups):
    row = registered(db, principal.tenant_id, ident)
    if row is not None and not row.user_visible and "Management" not in groups:
        raise ModelError("model_not_published", "Model není povolený v uživatelské aplikaci.", 403)


def check_embedding_access(db, principal, entry, index_id):
    from app.core.model_selection import current_groups, check_access
    groups = current_groups(db, principal)
    check_access(db, principal, entry)
    if "Management" in groups:
        return
    row = registered(db, principal.tenant_id, entry.id)
    if row is not None:
        return  # Publication and group checks above are authoritative.
    active = db.get(DBActiveSearchIndex, tenant_key(principal.tenant_id))
    if active is None or active.tenant_id != principal.tenant_id or str(active.index_id) != str(index_id):
        raise ModelError("embedding_not_published", "Experimentální embeddingový index zatím není povolený uživatelům.", 403)


def public_row(row):
    profile = row.profile_json
    return dict(id=row.model_id, kind=row.kind, model=profile.get("model", profile.get("profile", {}).get("model_id")),
                digest=profile.get("model_digest", profile.get("profile", {}).get("model_revision", "").removeprefix("sha256:")),
                user_visible=row.user_visible, revision=row.revision)


def require_connection(tenant):
    if not (any(p.connection == "jhu" for p in load_model_catalog(tenant).profiles)
            or any(p.provider == "ollama_embed" for p in load_embedding_catalog(tenant).profiles)):
        raise ModelError("model_discovery_not_configured", "Tenant nemá lokální modelové připojení.", 404)


def make_profile(tenant, model, existing_rows=()):
    """Only server metadata determines kind/digest/dimensions; recipes stay versioned."""
    if model.get("kind") not in {"chat_candidate", "embedding"}:
        raise ModelError("model_kind_unsupported", "Tento model není ověřený chatový ani embeddingový model.", 422)
    ident = "local-" + hashlib.sha256((model["kind"] + "\0" + model["name"] + "\0" + model["digest"]).encode()).hexdigest()[:48]
    context = model.get("context_length")
    if type(context) is not int or context < 1:
        raise ModelError("model_context_unknown", "Model nemá ověřený kontextový limit.", 422)
    if model["kind"] == "chat_candidate":
        if context < 2048:
            raise ModelError("model_context_too_small", "Model má příliš malý kontext pro chat.", 422)
        context = min(context, 8192)
        output = min(2048, context // 4)
        legacy = next((p for p in load_model_catalog(tenant).profiles
                       if p.connection == "jhu" and p.model == model["name"]), None)
        if legacy is not None:
            saved = next((r for r in existing_rows if r.model_id == legacy.id), None)
            if saved is None or saved.profile_json.get("model_digest") == model["digest"]:
                ident = legacy.id  # Pin the existing choice, without a duplicate or new default.
        return "chat", ModelProfile(id=ident, name=model["name"] + " · " + model["digest"][:8],
            description={"cs": "Lokální model z tenantové služby. Experimentální profil; kvalitu a dobu odpovědi ověřte na vlastních otázkách.",
                         "en": "Local tenant model. Experimental profile; validate answer quality and latency on your questions."},
            location="local", provider="ollama_generate", model=model["name"], connection="jhu",
            purposes=["chat", "summary", "classification"], timeout_seconds=180,
            max_input_chars=max(1000, context - output - 256), max_output_tokens=output,
            model_digest=model["digest"], context_tokens=context)
    if model["kind"] != "embedding":
        raise ModelError("model_kind_unsupported", "Tento model není chatový ani embeddingový.", 422)
    dimensions = model.get("dimensions")
    if type(dimensions) is not int or not 1 <= dimensions <= 1998:
        raise ModelError("embedding_dimensions_unsupported", "Rozměry modelu nejsou kompatibilní s SQL float32 indexem.", 422)
    recipes = load_tenant_json(tenant, "local_model_recipes.json")
    base = model["name"].rsplit("/", 1)[-1].split(":")[0]
    recipe = next((r for r in recipes.get("recipes", []) if base in r.get("models", [])), None)
    if recipe is None:
        raise ModelError("embedding_recipe_required", "Nejdříve nakonfigurujte query/document instrukce pro tento embeddingový model.", 422)
    space = EmbeddingProfile(model_id=model["name"], model_revision="sha256:" + model["digest"],
        dimensions=dimensions, normalization="l2", query_prefix=recipe["query_prefix"], document_prefix=recipe["document_prefix"],
        query_transform_version=recipe["version"], document_transform_version=recipe["version"])
    # Reuse a configured space, preserving existing Nomic indexes and identity.
    existing = next((p for p in load_embedding_catalog(tenant).profiles if p.space() == space), None)
    return "embedding", existing or EmbeddingEntry(id="local-" + space.profile_id, provider="ollama_embed", profile=space,
        max_input_chars=min(12000, context * 4), batch_size=8)


async def register_models(db, principal, requested):
    from app.core.model_selection import current_groups
    from app.providers.model_discovery import discover_models
    require_connection(principal.tenant_id)
    registry_rows(db, principal.tenant_id, required=True)
    if "Management" not in current_groups(db, principal):
        raise ModelError("model_forbidden", "Správa modelů vyžaduje Management.", 403)
    inventory = await discover_models()
    lookup = {(m["name"], m["digest"]): m for m in inventory["models"]}
    current = registry_rows(db, principal.tenant_id, required=True)
    prepared = []
    for item in requested:
        candidate = lookup.get((item.name, item.digest))
        if candidate is None:
            raise ModelError("model_inventory_changed", "Model zmizel nebo se změnil. Obnovte seznam z API.", 409)
        kind, profile = make_profile(principal.tenant_id, candidate, current)
        prepared.append((kind, profile))
    if "Management" not in current_groups(db, principal):
        raise ModelError("model_forbidden", "Oprávnění ke správě modelů bylo odebráno.", 403)
    try:
        existing = {row.model_id for row in registry_rows(db, principal.tenant_id, required=True)}
        configured_chat = {p.id for p in load_model_catalog(principal.tenant_id).profiles}
        for kind, profile in prepared:
            if profile.id not in existing:
                db.add(DBTenantModel(tenant_key=tenant_key(principal.tenant_id), tenant_id=principal.tenant_id,
                    model_id=profile.id, kind=kind, profile_json=profile.model_dump(mode="json"),
                    user_visible=kind == "chat" and profile.id in configured_chat,
                    revision=1, updated_by=str(principal.user_id)))
                existing.add(profile.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ModelError("model_registry_conflict", "Registr změnil jiný správce. Obnovte přehled.", 409) from None
    return {"models": [public_row(r) for r in registry_rows(db, principal.tenant_id)]}


def set_visibility(db, principal, ident, revision, visible):
    from app.core.model_selection import current_groups
    if "Management" not in current_groups(db, principal):
        raise ModelError("model_forbidden", "Správa modelů vyžaduje Management.", 403)
    row = registered(db, principal.tenant_id, ident)
    if row is None:
        raise ModelError("model_unknown", "Model není v registru tohoto tenantu.", 404)
    changed = db.execute(update(DBTenantModel).where(DBTenantModel.tenant_key == tenant_key(principal.tenant_id),
        DBTenantModel.model_id == ident, DBTenantModel.revision == revision).values(
            user_visible=visible, revision=revision+1, updated_by=str(principal.user_id), updated_at=datetime.utcnow()))
    if changed.rowcount != 1:
        db.rollback()
        raise ModelError("model_registry_conflict", "Registr změnil jiný správce. Obnovte přehled.", 409)
    db.commit()
    return public_row(registered(db, principal.tenant_id, ident))
