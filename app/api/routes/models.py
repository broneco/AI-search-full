"""Public model catalog and management-only access rules; never returns connections."""
from datetime import datetime
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.identity import Principal, get_principal, require_manager
from app.core.model_config import Purpose, load_model_catalog, ModelError
from app.core.embedding_config import load_embedding_catalog
from app.core.model_selection import current_groups, policy_rows
from app.providers.model_runtime import availability
from app.retrieval.filters import exact_value
from app.storage.models import DBModelAccess, DBUser
from app.core.model_metadata import description_rows, save_description, model_parameters
from app.core.model_limits import effective_profile, limit_rows, runtime_info, save_limit
from app.core.local_model_registry import (model_catalog, embedding_catalog, registry_rows, public_row,
    require_connection, make_profile, register_models, set_visibility)

router = APIRouter()


@router.get("/discovery")
async def discover_tenant_models(db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.core.model_config import ModelError
    from app.providers.model_discovery import discover_models
    catalog = model_catalog(db, principal.tenant_id)
    embeddings = embedding_catalog(db, principal.tenant_id)
    if not (any(p.connection == "jhu" for p in catalog.profiles)
            or any(p.provider == "ollama_embed" for p in embeddings.profiles)):
        raise ModelError("model_discovery_not_configured", "Tenant nemá JHU modelové připojení.", 404)
    result = await discover_models()
    approval_rows = registry_rows(db, principal.tenant_id)
    approvals = [public_row(r) for r in approval_rows]
    for model in result["models"]:
        model["registration"] = None
        try:
            _, candidate = make_profile(principal.tenant_id, model, approval_rows)
            model["candidate_id"] = candidate.id
            model["registration"] = next((r for r in approvals if r["id"] == candidate.id), None)
            model["registration_error"] = None
        except ModelError as error:
            model["registration_error"] = str(error)
        model["configured_chat_ids"] = [p.id for p in catalog.profiles
                                        if p.connection == "jhu" and p.model == model["name"]]
        # An updated mutable tag is a different embedding space, not an existing profile.
        model["configured_embedding_ids"] = [p.id for p in embeddings.profiles
            if p.provider == "ollama_embed" and p.space().model_id == model["name"]
            and p.space().model_revision == "sha256:" + model["digest"]]
    return result


class RegisterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class RegisterModels(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: list[RegisterModel] = Field(min_length=1, max_length=200)


class VisibilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    user_visible: bool


@router.get("/registry")
def get_registry(db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    return {"models": [public_row(r) for r in registry_rows(db, principal.tenant_id, required=True)]}


@router.post("/registry")
async def add_registry(request: RegisterModels, db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    return await register_models(db, principal, request.models)


@router.put("/registry/{model_id}")
def publish_registry(model_id: str, request: VisibilityUpdate, db: Session = Depends(get_db_session),
                     principal: Principal = Depends(require_manager)):
    return set_visibility(db, principal, model_id, request.revision, request.user_visible)


@router.get("")
def list_models(purpose: Purpose = "chat", db: Session = Depends(get_db_session),
                principal: Principal = Depends(get_principal)):
    catalog = model_catalog(db, principal.tenant_id)
    groups = current_groups(db, principal)
    approvals = {r.model_id: r for r in registry_rows(db, principal.tenant_id)}
    rules = {r.model_id: r.allowed_groups for r in policy_rows(db, principal.tenant_id)}
    visible = []
    descriptions = description_rows(db, principal.tenant_id)
    for p in catalog.profiles:
        if p.id in approvals and not approvals[p.id].user_visible and "Management" not in groups:
            continue
        allowed = rules.get(p.id)
        if purpose not in p.purposes or (allowed is not None and not groups.intersection(allowed)):
            continue
        ready, reason = availability(p)
        visible.append(dict(id=p.id, name=p.name,
                            description=descriptions[p.id].description if p.id in descriptions else p.description,
                            location=p.location, purposes=p.purposes, parameters=model_parameters(p),
                            available=ready, unavailable_reason=reason))
    return {"models": visible, "default_model_id": catalog.defaults[purpose]}


@router.get("/access")
def get_access(db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    catalog = model_catalog(db, principal.tenant_id)
    embeddings = embedding_catalog(db, principal.tenant_id)
    rows = {r.model_id: r for r in policy_rows(db, principal.tenant_id)}
    known_groups = {"User", "Management"}
    for groups in db.scalars(select(DBUser.groups).where(
            exact_value(DBUser.tenant_id, principal.tenant_id, db.bind.dialect.name))):
        if isinstance(groups, list):
            known_groups.update(g for g in groups if isinstance(g, str))
    for row in rows.values():
        known_groups.update(row.allowed_groups or [])
    return {"groups": sorted(known_groups), "models": [dict(id=p.id, name=p.name,
        allowed_groups=rows[p.id].allowed_groups if p.id in rows else None,
        revision=rows[p.id].revision if p.id in rows else 0) for p in [*catalog.profiles,
            *(SimpleNamespace(id=e.id, name=e.space().model_id) for e in embeddings.profiles)]]}


@router.get("/management")
def get_management(db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    """Current configured models, publication, access and descriptions; no live scan."""
    access = get_access(db, principal)
    policies = {row["id"]: row for row in access["models"]}
    descriptions = description_rows(db, principal.tenant_id)
    approvals = {row.model_id: public_row(row) for row in registry_rows(db, principal.tenant_id)}
    limits = limit_rows(db, principal.tenant_id)
    rows = []
    for p in model_catalog(db, principal.tenant_id, runtime_settings=False).profiles:
        ready, reason = availability(p)
        runtime = runtime_info(p, limits.get(p.id))
        effective = effective_profile(p, runtime["max_output_tokens"])
        rows.append(dict(id=p.id, name=p.name, kind="chat", location=p.location, purposes=p.purposes,
                         parameters=model_parameters(effective), description=p.description, runtime=runtime,
                         available=ready, unavailable_reason=reason))
    for entry in embedding_catalog(db, principal.tenant_id).profiles:
        space = entry.space()
        rows.append(dict(id=entry.id, name=space.model_id, kind="embedding",
                         location="local" if entry.provider == "ollama_embed" else "cloud",
                         purposes=["embedding"], description={"cs": "", "en": ""},
                         parameters=dict(model=space.model_id, dimensions=space.dimensions,
                                         max_input_chars=entry.max_input_chars, timeout_seconds=entry.timeout_seconds),
                         available=True, unavailable_reason=None))
    for row in rows:
        ident = row["id"]
        row["access"] = policies[ident]
        row["registration"] = approvals.get(ident)
        row["description_revision"] = descriptions[ident].revision if ident in descriptions else 0
        if ident in descriptions:
            row["description"] = descriptions[ident].description
    return dict(models=rows, groups=access["groups"])


class RuntimeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, le=2147483646, strict=True)
    max_output_tokens: int | None = Field(ge=128, le=32768, strict=True)


@router.put("/runtime/{model_id}")
def put_runtime(model_id: str, request: RuntimeUpdate, db: Session = Depends(get_db_session),
                principal: Principal = Depends(require_manager)):
    profile = next((p for p in model_catalog(db, principal.tenant_id, runtime_settings=False).profiles
                    if p.id == model_id), None)
    if profile is None:
        raise HTTPException(422, "Unknown tenant LLM model.")
    return save_limit(db, principal.tenant_id, str(principal.user_id), profile,
                      request.revision, request.max_output_tokens)


class DescriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    description: dict[str, str]

    @field_validator("description")
    @classmethod
    def valid_description(cls, value):
        if set(value) != {"cs", "en"} or any(len(text) > 4000 for text in value.values()):
            raise ValueError("Descriptions require cs/en and at most 4000 characters per language")
        return {key: text.strip() for key, text in value.items()}


@router.put("/descriptions/{model_id}")
def put_description(model_id: str, request: DescriptionUpdate, db: Session = Depends(get_db_session),
                    principal: Principal = Depends(require_manager)):
    known = {p.id for p in model_catalog(db, principal.tenant_id).profiles} | {
        p.id for p in embedding_catalog(db, principal.tenant_id).profiles}
    if model_id not in known:
        raise HTTPException(422, "Unknown tenant model.")
    return save_description(db, principal, model_id, request.revision, request.description)


class AccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    allowed_groups: list[str] | None

    @field_validator("allowed_groups")
    @classmethod
    def valid_groups(cls, value):
        if value is not None:
            if len(value) > 100 or any(not g.strip() or len(g) > 100 for g in value):
                raise ValueError("Invalid group names")
            return sorted({g.strip() for g in value})
        return None


@router.put("/access/{model_id}")
def put_access(model_id: str, request: AccessUpdate, db: Session = Depends(get_db_session),
               principal: Principal = Depends(require_manager)):
    if model_id not in {p.id for p in model_catalog(db, principal.tenant_id).profiles} | {p.id for p in embedding_catalog(db, principal.tenant_id).profiles}:
        raise HTTPException(422, "Unknown tenant model.")
    # Check schema availability before issuing writes.
    policy_rows(db, principal.tenant_id)
    values = dict(allowed_groups=request.allowed_groups, revision=request.revision + 1,
                  updated_by=str(principal.user_id), updated_at=datetime.utcnow())
    try:
        if request.revision == 0:
            db.add(DBModelAccess(tenant_id=principal.tenant_id, model_id=model_id, **values))
        else:
            changed = db.execute(update(DBModelAccess).where(
                exact_value(DBModelAccess.tenant_id, principal.tenant_id, db.bind.dialect.name),
                exact_value(DBModelAccess.model_id, model_id, db.bind.dialect.name),
                DBModelAccess.revision == request.revision).values(**values))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, "Pravidla mezitím změnil jiný správce. Načtěte je znovu.")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Pravidla mezitím změnil jiný správce. Načtěte je znovu.") from None
    return {"model_id": model_id, "revision": request.revision + 1, "allowed_groups": request.allowed_groups}
