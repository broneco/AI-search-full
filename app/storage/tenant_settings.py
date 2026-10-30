"""Exact-tenant SQL overrides for the three administrator-editable JSON documents."""
from copy import deepcopy
import hashlib
import json

from sqlalchemy.orm import Session

from app.storage.models import DBTenantSetting

MUTABLE_CONFIG_FILES = frozenset({"prompts.json", "search_config.json", "classification_config.json"})


class TenantSettingsError(Exception):
    """A safe public failure: callers must never report an ephemeral save as durable."""

    def __init__(self, code: str = "tenant_settings_unavailable", status: int = 503):
        self.code = code
        self.status = status
        super().__init__("Nastavení nelze bezpečně načíst nebo uložit. Ověřte připojení a migraci tenant_settings.")


def setting_key(tenant: str, filename: str) -> tuple[str, str]:
    if not tenant or len(tenant) > 255 or filename not in MUTABLE_CONFIG_FILES:
        raise ValueError("Invalid tenant setting identity.")
    return hashlib.sha256(tenant.encode("utf-8")).hexdigest(), filename


def validate_payload(filename: str, data: dict) -> dict:
    if filename not in MUTABLE_CONFIG_FILES or not isinstance(data, dict):
        raise ValueError("Invalid tenant setting document.")
    # Validate before any write, including migrations; reject non-JSON/NaN values.
    json.dumps(data, allow_nan=False)
    if filename == "prompts.json":
        if set(data) != {"cs", "en"} or any(not isinstance(value, str) or not value.strip()
                                               for value in data.values()):
            raise ValueError("Prompts require nonempty cs/en text.")
    elif filename == "search_config.json":
        from app.core.search_config import SearchConfigSchema
        SearchConfigSchema.model_validate(data)
    else:
        from app.schemas.documents import CategoryConfigRequest
        CategoryConfigRequest.model_validate(data)
    return deepcopy(data)


def read_setting(db: Session, tenant: str, filename: str) -> dict | None:
    row = db.get(DBTenantSetting, setting_key(tenant, filename))
    if row is None:
        return None
    if row.tenant_id != tenant:
        raise TenantSettingsError()
    return validate_payload(filename, row.payload)


def write_setting(db: Session, tenant: str, filename: str, data: dict, *, insert_only: bool = False) -> bool:
    """Stage one document; the caller owns commit/rollback. Imports never overwrite."""
    key, name = setting_key(tenant, filename)
    payload = validate_payload(filename, data)
    row = db.get(DBTenantSetting, (key, name))
    if row is not None:
        if row.tenant_id != tenant:
            raise TenantSettingsError()
        if insert_only:
            return False
        row.payload = payload
    else:
        db.add(DBTenantSetting(tenant_key=key, tenant_id=tenant, filename=name, payload=payload))
    db.flush()
    return True
