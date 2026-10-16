"""Prompt isolation with synthetic clients, independent of exported tenant count."""
import json

import pytest

import app.core.tenant_config as tenant_config
from app.core.prompts import get_system_prompt, get_tenant_base


@pytest.fixture
def prompt_files(tmp_path, monkeypatch):
    for name in ("alpha", "beta"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "prompts.json").write_text(json.dumps({
            "cs": f"Asistent {name}. Kontext: {{context_str}}",
            "en": f"Assistant {name}. Context: {{context_str}}",
        }), encoding="utf-8")
    monkeypatch.setattr(tenant_config, "TENANTS_DIR", str(tmp_path))
    monkeypatch.setattr(tenant_config, "LOCAL_TENANTS_DIR", None)


def test_tenant_base_extraction():
    assert get_tenant_base("alpha-prod") == "alpha"
    assert get_tenant_base("alpha-dev") == "alpha"
    assert get_tenant_base("ju-prod") == "jhu"
    assert get_tenant_base("unknown-tenant") == "unknown"
    assert get_tenant_base("") == "default"


def test_tenant_prompt_formats_both_languages(prompt_files):
    context = "[1] Testovací dokument"
    assert get_system_prompt("alpha-prod", "cs", context) == f"Asistent alpha. Kontext: {context}"
    assert get_system_prompt("alpha-dev", "en", context) == f"Assistant alpha. Context: {context}"


def test_tenant_prompt_does_not_mix_clients(prompt_files):
    prompt = get_system_prompt("beta-prod", "cs", "Testovací obsah")
    assert "beta" in prompt
    assert "alpha" not in prompt
