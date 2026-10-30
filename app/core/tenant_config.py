"""
Tenant Configuration Resolver with file-level fallback system.
Resolves configuration files (prompts.json, search_config.json, classification_config.json, branding.json)
for specific tenants from the root `tenants/` directory, with automatic file-level fallback to `tenants/default/`.
"""

import os
import json
import logging
from typing import Any, Dict, Tuple
from app.core.config import settings
from app.core.tenant_identity import tenant_config_name

logger = logging.getLogger(__name__)

# Root tenants directory path
TENANTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tenants"))
LOCAL_TENANTS_DIR = (
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".local", settings.APP_ENV, "tenants"))
    if settings.APP_ENV in {"local", "test"}
    else None
)


def get_tenant_base(tenant_id: str) -> str:
    """Extract base tenant name from tenant_id string (e.g. 'alzbeta-prod' -> 'alzbeta', 'dolphin-dev' -> 'dolphin')."""
    return tenant_config_name(tenant_id)


def resolve_tenant_file_path(tenant_id: str, filename: str) -> Tuple[str, bool]:
    """
    Resolve absolute path for a tenant config file.
    Checks tenants/<tenant_base>/<filename>.
    If missing, falls back to tenants/default/<filename>.
    
    Returns:
        Tuple[str, bool]: (resolved_file_path, is_fallback_used)
    """
    tenant_base = get_tenant_base(tenant_id)
    target_path = os.path.join(TENANTS_DIR, tenant_base, filename)
    default_path = os.path.join(TENANTS_DIR, "default", filename)

    # Local development and tests read tracked defaults but write into an ignored overlay.
    candidates = []
    if LOCAL_TENANTS_DIR:
        local_target = os.path.join(LOCAL_TENANTS_DIR, tenant_base, filename)
        local_default = os.path.join(LOCAL_TENANTS_DIR, "default", filename)
        candidates.extend([(local_target, False), (target_path, False), (local_default, True), (default_path, True)])
    else:
        candidates.extend([(target_path, False), (default_path, True)])

    for candidate, is_fallback in candidates:
        if os.path.exists(candidate):
            if is_fallback:
                logger.info(f"Tenant config file '{filename}' missing for tenant '{tenant_base}'. Falling back to: {candidate}")
            return candidate, is_fallback

    write_path = os.path.join(LOCAL_TENANTS_DIR, tenant_base, filename) if LOCAL_TENANTS_DIR else target_path
    logger.warning(f"Tenant config file '{filename}' not found for tenant '{tenant_base}' nor in default at {default_path}")
    return write_path, False


def load_tenant_json(tenant_id: str, filename: str, default_data: Any = None) -> Any:
    """
    Load cloud mutable SQL overrides first, then bundled file-level defaults.
    """
    if uses_sql_settings(filename):
        from app.storage.db import SessionLocal
        from app.storage.tenant_settings import read_setting, TenantSettingsError
        from sqlalchemy.exc import SQLAlchemyError
        try:
            with SessionLocal() as db:
                override = read_setting(db, tenant_id, filename)
        except (SQLAlchemyError, ValueError):
            raise TenantSettingsError() from None
        if override is not None:
            return override
    file_path, is_fallback = resolve_tenant_file_path(tenant_id, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading tenant JSON file at {file_path}: {e}")

    return default_data if default_data is not None else {}


def save_tenant_json(tenant_id: str, filename: str, data: Any) -> str:
    """
    Save cloud mutable configuration durably in SQL; keep local/test file overlays.
    """
    if uses_sql_settings(filename):
        from app.storage.db import SessionLocal
        from app.storage.tenant_settings import write_setting, TenantSettingsError
        from sqlalchemy.exc import IntegrityError, SQLAlchemyError
        from sqlalchemy.orm.exc import StaleDataError
        try:
            with SessionLocal.begin() as db:
                write_setting(db, tenant_id, filename, data)
        except (IntegrityError, StaleDataError):
            raise TenantSettingsError("tenant_settings_conflict", 409) from None
        except SQLAlchemyError:
            raise TenantSettingsError() from None
        return f"sql:tenant_settings/{tenant_id}/{filename}"
    tenant_base = get_tenant_base(tenant_id)
    tenant_root = LOCAL_TENANTS_DIR or TENANTS_DIR
    tenant_dir = os.path.join(tenant_root, tenant_base)
    os.makedirs(tenant_dir, exist_ok=True)
    
    target_path = os.path.join(tenant_dir, filename)
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved tenant config '{filename}' for tenant '{tenant_base}' to {target_path}")
    except Exception as e:
        logger.error(f"Failed to save tenant config '{filename}' for tenant '{tenant_base}': {e}")
        
    return target_path


def uses_sql_settings(filename: str) -> bool:
    """Cloud settings live outside the image; local/test keep their isolated overlays."""
    from app.storage.tenant_settings import MUTABLE_CONFIG_FILES
    return settings.APP_ENV in {"dev", "prod"} and filename in MUTABLE_CONFIG_FILES
