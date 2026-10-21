"""Revisioned generation settings without changing model or embedding identity."""
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.model_config import ModelError, ModelProfile
from app.core.model_metadata import metadata_rows
from app.retrieval.filters import exact_value
from app.storage.models import DBModelRuntimeSettings
from app.storage.vector_store import tenant_key

MIN_OUTPUT_TOKENS = 128
MAX_OUTPUT_TOKENS = 32768
MIN_LOCAL_INPUT = 1024
LOCAL_RESERVE = 256


def limit_rows(db: Session, tenant: str, *, required: bool = False) -> dict[str, DBModelRuntimeSettings]:
    return metadata_rows(db, tenant, DBModelRuntimeSettings, required=required,
                         error_prefix="model_limits", label="Limity modelů")


def output_bounds(profile: ModelProfile) -> tuple[int, int]:
    maximum = MAX_OUTPUT_TOKENS
    if profile.provider == "ollama_generate":
        # Legacy, unpinned local profiles have no verified context budget.
        maximum = (profile.context_tokens - MIN_LOCAL_INPUT - LOCAL_RESERVE
                   if profile.context_tokens else profile.max_output_tokens)
    return MIN_OUTPUT_TOKENS, min(MAX_OUTPUT_TOKENS, maximum)


def effective_profile(profile: ModelProfile, override: int | None) -> ModelProfile:
    if override is None:
        return profile
    minimum, maximum = output_bounds(profile)
    if type(override) is not int or not minimum <= override <= maximum:
        raise ModelError("model_output_limit_invalid", f"Limit výstupu musí být celé číslo od {minimum} do {maximum} tokenů.", 422)
    values = {"max_output_tokens": override}
    if profile.context_tokens:
        values["max_input_chars"] = min(profile.max_input_chars, profile.context_tokens - override - LOCAL_RESERVE)
    # Revalidate derived limits instead of bypassing the profile contract.
    return ModelProfile.model_validate({**profile.model_dump(), **values})


def runtime_info(profile: ModelProfile, row: DBModelRuntimeSettings | None) -> dict:
    minimum, maximum = output_bounds(profile)
    override = row.max_output_tokens if row else None
    effective = effective_profile(profile, override)
    return dict(revision=row.revision if row else 0, max_output_tokens=override,
                default_max_output_tokens=profile.max_output_tokens,
                effective_max_output_tokens=effective.max_output_tokens,
                effective_max_input_chars=effective.max_input_chars,
                minimum=minimum, maximum=maximum, context_tokens=profile.context_tokens)


def apply_limits(db: Session, tenant: str, profiles: list[ModelProfile]) -> list[ModelProfile]:
    rows = limit_rows(db, tenant)
    return [effective_profile(profile, rows[profile.id].max_output_tokens if profile.id in rows else None)
            for profile in profiles]


def save_limit(db: Session, tenant: str, actor: str, profile: ModelProfile, revision: int, value: int | None) -> dict:
    effective = effective_profile(profile, value)
    limit_rows(db, tenant, required=True)
    values = dict(max_output_tokens=value, revision=revision + 1,
                  updated_by=actor, updated_at=datetime.utcnow())
    try:
        if revision == 0:
            db.add(DBModelRuntimeSettings(tenant_key=tenant_key(tenant), tenant_id=tenant,
                                         model_id=profile.id, **values))
        else:
            changed = db.execute(update(DBModelRuntimeSettings).where(
                DBModelRuntimeSettings.tenant_key == tenant_key(tenant),
                exact_value(DBModelRuntimeSettings.model_id, profile.id, db.bind.dialect.name),
                DBModelRuntimeSettings.revision == revision).values(**values))
            if changed.rowcount != 1:
                raise IntegrityError("revision conflict", {}, None)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ModelError("model_limits_conflict", "Limit změnil jiný správce. Načtěte přehled znovu.", 409) from None
    row = limit_rows(db, tenant, required=True)[profile.id]
    from app.core.model_metadata import model_parameters
    return dict(runtime=runtime_info(profile, row), parameters=model_parameters(effective))
