from app.core.prompts import get_system_prompt, get_tenant_base


def test_tenant_base_extraction():
    assert get_tenant_base("alzbeta-prod") == "alzbeta"
    assert get_tenant_base("alzbeta-dev") == "alzbeta"
    assert get_tenant_base("dolphin-prod") == "dolphin"
    assert get_tenant_base("unknown-tenant") == "unknown"
    assert get_tenant_base("") == "default"


def test_alzbeta_tenant_prompt_identifies_leaders():
    context = "[1] Název: Test Doc\nObsah: Testovací směrnice\n"
    prompt_cs = get_system_prompt("alzbeta-prod", "cs", context)
    
    # Assert hospital name and key leadership personalities are present in Czech prompt
    assert "Nemocnice sv. Alžběty" in prompt_cs
    assert "RNDr. Karel Matyska, CSc." in prompt_cs
    assert "Jednatel" in prompt_cs
    assert "MUDr. Ivana Doleželová, MBA" in prompt_cs
    assert "Náměstek LPP" in prompt_cs
    assert "Mgr. Marcela Tomanová, MBA, LL.M." in prompt_cs
    assert "Náměstek NZOK" in prompt_cs
    assert "[1] Název: Test Doc" in prompt_cs

    prompt_en = get_system_prompt("alzbeta-dev", "en", context)
    assert "St. Elizabeth Hospital" in prompt_en
    assert "RNDr. Karel Matyska, CSc." in prompt_en
    assert "Managing Director" in prompt_en


def test_dolphin_tenant_prompt():
    context = "[1] Název: Pracovní řád\nObsah: Testovací obsah\n"
    prompt_cs = get_system_prompt("dolphin-prod", "cs", context)
    assert "Dolphin Consulting" in prompt_cs
    assert "Karel Matyska" not in prompt_cs
