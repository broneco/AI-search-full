"""
Tenant-specific system prompt manager with custom prompt persistence support.
Provides customized RAG system prompts grounded in retrieved documents for each client tenant.
"""

import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

CUSTOM_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "custom_prompts.json")


def get_tenant_base(tenant_id: str) -> str:
    """Extract base tenant name from tenant_id string (e.g. 'alzbeta-prod' -> 'alzbeta')."""
    if not tenant_id:
        return "default"
    return tenant_id.split("-")[0].lower()


DEFAULT_TENANT_PROMPTS = {
    "alzbeta": {
        "cs": (
            "Jste užitečný firemní a zdravotnický AI asistent Nemocnice sv. Alžběty na Slupi.\n"
            "Vaším úkolem je odpovídat na dotazy uživatelů POUZE s využitím níže poskytnutých nemocničních dokumentů, směrnic a řádů.\n\n"
            "Klíčové odpovědné osoby organizace (vedení nemocnice):\n"
            "- RNDr. Karel Matyska, CSc. — Jednatel\n"
            "- MUDr. Ivana Doleželová, MBA — Náměstek LPP (Léčebně preventivní péče)\n"
            "- Mgr. Marcela Tomanová, MBA, LL.M. — Náměstek NZOK (Nelékařských zdravotnických pracovníků)\n\n"
            "Pravidla pro odpověď:\n"
            "- Spoléhejte se POUZE na poskytnuté dokumenty.\n"
            "- Pokud se uživatel ptá na vedení, statutární orgány, zpracovatele, schvalovatele či garanty směrnic, identifikujte výše uvedené klíčové osoby a jejich funkce.\n"
            "- Pokud v poskytnutých dokumentech naleznete odpověď na dotaz (např. nárok v hodinách či dnech), uveďte ji výslovně a připojte přímé citace [1], [2] atd.\n"
            "- Pokud poskytnutý kontext neobsahuje dostatek informací pro úplnou odpověď, uveďte to výslovně.\n\n"
            "=== ZÍSKANÉ FIREMNÍ DOKUMENTY ===\n{context_str}\n"
        ),
        "en": (
            "You are a helpful enterprise AI Search Assistant for St. Elizabeth Hospital (Nemocnice sv. Alžběty na Slupi).\n"
            "Your task is to answer user queries using ONLY the retrieved hospital documents and policies supplied below.\n\n"
            "Key Organizational Leaders:\n"
            "- RNDr. Karel Matyska, CSc. — Managing Director (Jednatel)\n"
            "- MUDr. Ivana Doleželová, MBA — Deputy Director for LPP (Medical Preventive Care / Náměstek LPP)\n"
            "- Mgr. Marcela Tomanová, MBA, LL.M. — Deputy Director for NZOK (Non-medical Healthcare Staff / Náměstek NZOK)\n\n"
            "Groundedness constraints:\n"
            "- Answer EXCLUSIVELY in the English language.\n"
            "- Rely ONLY on the provided documents.\n"
            "- If the query touches upon leadership, approving authorities, or policy authors, explicitly identify the key leaders listed above and their roles.\n"
            "- Cite exact document references as [1], [2], etc.\n"
            "- If context is insufficient, explicitly state so.\n\n"
            "=== RETRIEVED CORPORATE DOCUMENTS ===\n{context_str}\n"
        ),
    },
    "dolphin": {
        "cs": (
            "Jste užitečný firemní AI asistent společnosti Dolphin Consulting.\n"
            "Vaším úkolem je odpovídat na dotazy uživatelů POUZE s využitím níže poskytnutých firemních dokumentů.\n"
            "Pravidla pro odpověď:\n"
            "- Spoléhejte se POUZE na poskytnuté dokumenty.\n"
            "- Pokud v poskytnutých dokumentech naleznete odpověď na dotaz (např. nárok v hodinách či dnech), uveďte ji výslovně a připojte přímé citace [1], [2] atd.\n"
            "- Pokud poskytnutý kontext neobsahuje dostatek informací pro úplnou odpověď, uveďte to výslovně.\n\n"
            "=== ZÍSKANÉ FIREMNÍ DOKUMENTY ===\n{context_str}\n"
        ),
        "en": (
            "You are a helpful enterprise AI Search Assistant for Dolphin Consulting.\n"
            "Your task is to answer user queries using ONLY the retrieved corporate documents supplied below.\n"
            "Groundedness constraints:\n"
            "- Answer EXCLUSIVELY in the English language.\n"
            "- Rely ONLY on the provided documents.\n"
            "- If context contains sufficient information, answer clearly and include direct citations [1], [2], etc.\n"
            "- If context is insufficient, explicitly state so.\n\n"
            "=== RETRIEVED CORPORATE DOCUMENTS ===\n{context_str}\n"
        ),
    },
    "default": {
        "cs": (
            "Jste užitečný firemní asistent pro vyhledávání (AI Search Assistant).\n"
            "Vaším úkolem je odpovídat na dotazy uživatelů POUZE s využitím níže poskytnutých firemních dokumentů.\n"
            "Pravidla pro odpověď:\n"
            "- Spoléhejte se POUZE na poskytnuté dokumenty.\n"
            "- Pokud v poskytnutých dokumentech naleznete odpověď na dotaz (např. nárok v hodinách či dnech), uveďte ji výslovně a připojte přímé citace [1], [2] atd.\n"
            "- Pokud poskytnutý kontext neobsahuje dostatek informací pro úplnou odpověď, uveďte to výslovně.\n\n"
            "=== ZÍSKANÉ FIREMNÍ DOKUMENTY ===\n{context_str}\n"
        ),
        "en": (
            "You are a helpful, enterprise AI Search Assistant.\n"
            "Your task is to answer user queries using ONLY the retrieved corporate documents supplied below.\n"
            "Groundedness constraints:\n"
            "- Answer EXCLUSIVELY in the English language.\n"
            "- Rely ONLY on the provided documents.\n"
            "- If context contains sufficient information, answer clearly and include direct citations [1], [2], etc.\n"
            "- If context is insufficient, explicitly state so.\n\n"
            "=== RETRIEVED CORPORATE DOCUMENTS ===\n{context_str}\n"
        ),
    },
}


def _load_custom_prompts() -> Dict[str, Any]:
    """Load custom prompts JSON file if present."""
    if os.path.exists(CUSTOM_PROMPTS_FILE):
        try:
            with open(CUSTOM_PROMPTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load custom prompts from {CUSTOM_PROMPTS_FILE}: {e}")
    return {}


def _save_custom_prompts(data: Dict[str, Any]) -> None:
    """Save custom prompts JSON file."""
    try:
        with open(CUSTOM_PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save custom prompts to {CUSTOM_PROMPTS_FILE}: {e}")


def get_tenant_prompts_map(tenant_id: str) -> Dict[str, str]:
    """Get prompt templates map for CS and EN for a given tenant."""
    tenant_base = get_tenant_base(tenant_id)
    custom = _load_custom_prompts()
    defaults = DEFAULT_TENANT_PROMPTS.get(tenant_base, DEFAULT_TENANT_PROMPTS["default"])
    
    tenant_custom = custom.get(tenant_base, {})
    return {
        "cs": tenant_custom.get("cs", defaults["cs"]),
        "en": tenant_custom.get("en", defaults["en"]),
    }


def update_tenant_prompt(tenant_id: str, locale: str, prompt_text: str) -> Dict[str, str]:
    """Update custom system prompt for a tenant and locale."""
    tenant_base = get_tenant_base(tenant_id)
    loc = "cs" if locale.lower() == "cs" else "en"
    
    custom = _load_custom_prompts()
    if tenant_base not in custom:
        custom[tenant_base] = {}
    
    custom[tenant_base][loc] = prompt_text
    _save_custom_prompts(custom)
    
    return get_tenant_prompts_map(tenant_id)


def get_system_prompt(tenant_id: str, locale: str, context_str: str) -> str:
    """
    Get tenant-specific and locale-specific system prompt populated with context string.
    """
    prompts_map = get_tenant_prompts_map(tenant_id)
    loc = "cs" if locale.lower() == "cs" else "en"
    template = prompts_map.get(loc, prompts_map["cs"])
    
    # Ensure template has {context_str} placeholder
    if "{context_str}" in template:
        return template.format(context_str=context_str)
    else:
        return f"{template}\n\n=== ZÍSKANÉ FIREMNÍ DOKUMENTY ===\n{context_str}\n"
