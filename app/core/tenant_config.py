"""
Tenant Configuration Resolver with file-level fallback system.
Resolves configuration files (prompts.json, search_config.json, classification_config.json, branding.json)
for specific tenants from the root `tenants/` directory, with automatic file-level fallback to `tenants/default/`.
"""

import os
import json
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# Root tenants directory path
TENANTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tenants"))


def get_tenant_base(tenant_id: str) -> str:
    """Extract base tenant name from tenant_id string (e.g. 'alzbeta-prod' -> 'alzbeta', 'dolphin-dev' -> 'dolphin')."""
    if not tenant_id:
        return "default"
    clean = tenant_id.strip().lower()
    return clean.split("-")[0]


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

    if os.path.exists(target_path):
        return target_path, False

    if os.path.exists(default_path):
        logger.info(f"Tenant config file '{filename}' missing for tenant '{tenant_base}'. Falling back to default: {default_path}")
        return default_path, True

    logger.warning(f"Tenant config file '{filename}' not found for tenant '{tenant_base}' nor in default at {default_path}")
    return target_path, False


def load_tenant_json(tenant_id: str, filename: str, default_data: Any = None) -> Any:
    """
    Load JSON configuration file for a tenant with fallback to default tenant folder.
    """
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
    Save JSON configuration file for a tenant in tenants/<tenant_base>/<filename>.
    Ensures directory exists.
    """
    tenant_base = get_tenant_base(tenant_id)
    tenant_dir = os.path.join(TENANTS_DIR, tenant_base)
    os.makedirs(tenant_dir, exist_ok=True)
    
    target_path = os.path.join(tenant_dir, filename)
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved tenant config '{filename}' for tenant '{tenant_base}' to {target_path}")
    except Exception as e:
        logger.error(f"Failed to save tenant config '{filename}' for tenant '{tenant_base}': {e}")
        
    return target_path
