"""
Unit tests for TenantConfigResolver and file-level tenant configuration fallback system.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.tenant_config import (
    resolve_tenant_file_path,
    load_tenant_json,
    save_tenant_json,
    get_tenant_base,
)
from app.core.prompts import get_tenant_prompts_map, get_system_prompt
from app.core.search_config import SearchConfigManager
from app.core.config import settings, _ENV_FILES


def test_tenant_base_extraction():
    assert get_tenant_base("alzbeta-prod") == "alzbeta"
    assert get_tenant_base("dolphin-dev") == "dolphin"
    assert get_tenant_base("jhu") == "jhu"
    assert get_tenant_base("") == "default"


def test_tenant_file_resolution_and_fallback():
    # Dolphin has prompts.json
    path, is_fallback = resolve_tenant_file_path("dolphin", "prompts.json")
    assert not is_fallback
    assert os.path.exists(path)
    assert "dolphin" in path

    # Alzbeta has prompts.json but no search_config.json -> falls back to default/search_config.json
    path_alz, is_fallback_alz = resolve_tenant_file_path("alzbeta", "search_config.json")
    assert is_fallback_alz
    assert os.path.exists(path_alz)
    assert "default" in path_alz


def test_tenant_env_files_priority():
    if settings.APP_ENV in {"local", "test"}:
        assert _ENV_FILES == (f".env.{settings.APP_ENV}",)
    else:
        assert len(_ENV_FILES) >= 4
        # Ensure tenant-specific directory env files are placed last (highest priority in Pydantic Settings)
        highest_priority_entry = _ENV_FILES[-1]
        assert "tenants" in highest_priority_entry


def test_tenant_prompts_loading():
    prompts_alz = get_tenant_prompts_map("alzbeta")
    assert "Nemocnice sv. Alžběty" in prompts_alz["cs"]

    prompts_jhu = get_tenant_prompts_map("jhu")
    assert "Jihočeské univerzity" in prompts_jhu["cs"]

    prompts_unknown = get_tenant_prompts_map("unknown-tenant-xyz")
    assert "AI Search Assistant" in prompts_unknown["cs"]


def test_system_prompt_formatting():
    sys_prompt = get_system_prompt("alzbeta", "cs", "Testovací kontext z PDF směrnice")
    assert "Nemocnice sv. Alžběty" in sys_prompt
    assert "Testovací kontext z PDF směrnice" in sys_prompt


def test_search_config_manager_tenant_loading():
    mgr = SearchConfigManager()
    cfg_sync = mgr.load_config_sync()
    assert "search_strategy" in cfg_sync
    assert cfg_sync["search_strategy"] == "hybrid"


def test_tenant_branding_key_parity_and_jhu():
    tenants = ["default", "dolphin", "alzbeta", "jhu", "showcase"]
    brandings = {}
    for tenant in tenants:
        branding_data = load_tenant_json(tenant, "branding.json")
        assert branding_data, f"branding.json for tenant '{tenant}' must exist and not be empty."
        brandings[tenant] = branding_data

    # Check 100% key parity across all tenants
    base_keys = set(brandings["default"].keys())
    base_color_keys = set(brandings["default"]["colors"].keys())

    for tenant, data in brandings.items():
        assert set(data.keys()) == base_keys, f"Key mismatch in branding.json for tenant '{tenant}': {set(data.keys()) ^ base_keys}"
        assert set(data["colors"].keys()) == base_color_keys, f"Color key mismatch in branding.json for tenant '{tenant}': {set(data['colors'].keys()) ^ base_color_keys}"

    # Specific assertions for JHU tenant
    jhu_data = brandings["jhu"]
    assert jhu_data["appName"] == "JCU AI Search"
    assert jhu_data["appTitle"] == "JCU AI Search"
    assert jhu_data["demoEmail"] == "user@jcu.cz"
    assert jhu_data["tenantScope"] == "JCU Tenant Scope"
    assert jhu_data["logoUrl"] == "/logos/logo-JHU.webp"


if __name__ == "__main__":
    test_tenant_base_extraction()
    test_tenant_file_resolution_and_fallback()
    test_tenant_env_files_priority()
    test_tenant_prompts_loading()
    test_system_prompt_formatting()
    test_search_config_manager_tenant_loading()
    test_tenant_branding_key_parity_and_jhu()
    print("ALL TENANT CONFIG AND ENV TESTS PASSED SUCCESSFULLY!")

