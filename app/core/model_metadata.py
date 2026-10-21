"""Tenant presentation metadata; edits never change provider or embedding identity."""
from datetime import datetime

from sqlalchemy import inspect, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.model_config import ModelError
from app.storage.models import DBModelDescription
from app.storage.vector_store import tenant_key


def metadata_rows(db, tenant, model, *, required=False, error_prefix="model_metadata", label="Popisy modelů"):
    """Read optional tenant overrides; only actual missing tables permit defaults."""
    try:
        if not inspect(db.connection()).has_table(model.__tablename__):
            missing = True
            if db.bind.dialect.name == "mssql":
                try:
                    db.execute(select(model).limit(0))
                    missing = False
                except SQLAlchemyError as error:
                    args = getattr(getattr(error, "orig", None), "args", ())
                    if not args or args[0] != "42S02":
                        raise
            if missing:
                if required:
                    raise ModelError(error_prefix + "_migration_required", label + ": restartujte lokální backend; v Azure je nutná odpovídající migrace.")
                return {}
        rows = list(db.scalars(select(model).where(
            model.tenant_key == tenant_key(tenant)).execution_options(populate_existing=True)))
        if any(row.tenant_id != tenant for row in rows):
            raise ValueError("Tenant metadata mismatch")
        return {row.model_id: row for row in rows}
    except (SQLAlchemyError, ValueError):
        raise ModelError(error_prefix + "_unavailable", label + ": úložiště není dostupné.") from None


def description_rows(db, tenant, *, required=False):
    return metadata_rows(db, tenant, DBModelDescription, required=required)


def save_description(db, principal, ident, revision, description):
    description_rows(db, principal.tenant_id, required=True)
    values = dict(description=description, revision=revision + 1,
                  updated_by=str(principal.user_id), updated_at=datetime.utcnow())
    try:
        if revision == 0:
            db.add(DBModelDescription(tenant_key=tenant_key(principal.tenant_id),
                                     tenant_id=principal.tenant_id, model_id=ident, **values))
        else:
            from app.retrieval.filters import exact_value
            changed = db.execute(update(DBModelDescription).where(
                DBModelDescription.tenant_key == tenant_key(principal.tenant_id),
                exact_value(DBModelDescription.model_id, ident, db.bind.dialect.name),
                DBModelDescription.revision == revision).values(**values))
            if changed.rowcount != 1:
                raise IntegrityError("revision conflict", {}, None)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ModelError("model_metadata_conflict", "Popis změnil jiný správce. Načtěte přehled znovu.", 409) from None
    return dict(model_id=ident, revision=revision + 1, description=description)


def model_parameters(profile):
    return dict(model=profile.model, context_tokens=profile.context_tokens,
                max_input_chars=profile.max_input_chars, max_output_tokens=profile.max_output_tokens,
                timeout_seconds=profile.timeout_seconds)
