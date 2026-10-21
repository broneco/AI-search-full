"""
Unit tests for TenantConfigResolver and file-level tenant configuration fallback system.
"""

import sys
import os
import json
from pathlib import Path
import pytest

import app.core.tenant_config as tenant_config

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
    assert get_tenant_base("ju-prod") == "jhu"
    assert get_tenant_base("") == "default"


def test_tenant_file_resolution_and_fallback(tmp_path, monkeypatch):
    # Synthetic files keep fallback coverage independent of bundled clients.
    for tenant, filename in (("alpha", "prompts.json"), ("default", "search_config.json")):
        folder = tmp_path / tenant
        folder.mkdir()
        (folder / filename).write_text('{}', encoding="utf-8")
    monkeypatch.setattr(tenant_config, "TENANTS_DIR", str(tmp_path))
    monkeypatch.setattr(tenant_config, "LOCAL_TENANTS_DIR", None)
    path, is_fallback = resolve_tenant_file_path("alpha", "prompts.json")
    assert not is_fallback
    assert os.path.exists(path)
    assert "alpha" in path

    path_alz, is_fallback_alz = resolve_tenant_file_path("alpha", "search_config.json")
    assert is_fallback_alz
    assert os.path.exists(path_alz)
    assert "default" in path_alz


def test_tenant_env_files_priority():
    if settings.APP_ENV in {"local", "test"}:
        assert _ENV_FILES == ((".env.jhu-model", ".env.local") if settings.APP_ENV == "local" else (".env.test",))
    else:
        assert len(_ENV_FILES) >= 4
        # Ensure tenant-specific directory env files are placed last (highest priority in Pydantic Settings)
        highest_priority_entry = _ENV_FILES[-1]
        assert "tenants" in highest_priority_entry


def test_tenant_prompts_loading():
    prompts_jhu = get_tenant_prompts_map("jhu")
    assert "Jihočeské univerzity" in prompts_jhu["cs"]
    assert get_tenant_prompts_map("ju-prod") == prompts_jhu

    prompts_unknown = get_tenant_prompts_map("unknown-tenant-xyz")
    assert "AI Search Assistant" in prompts_unknown["cs"]


def test_system_prompt_formatting():
    sys_prompt = get_system_prompt("ju-prod", "cs", "Testovací kontext z PDF směrnice")
    assert "Jihočeské univerzity" in sys_prompt
    assert "Testovací kontext z PDF směrnice" in sys_prompt


def test_search_config_manager_tenant_loading():
    mgr = SearchConfigManager()
    cfg_sync = mgr.load_config_sync()
    assert "search_strategy" in cfg_sync
    assert cfg_sync["search_strategy"] == "hybrid"


def test_tenant_branding_key_parity_and_jhu():
    # One real bundled tenant is sufficient; check every branding that ships.
    brandings = {path.parent.name: json.loads(path.read_text(encoding="utf-8"))
                 for path in Path(tenant_config.TENANTS_DIR).glob("*/branding.json")}
    assert "jhu" in brandings

    # Check 100% key parity across all tenants
    base_keys = set(brandings["jhu"].keys())
    base_color_keys = set(brandings["jhu"]["colors"].keys())

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
    raise SystemExit(pytest.main([__file__]))

