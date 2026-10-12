"""
Tenant-specific system prompt manager with custom prompt persistence support.
Provides customized RAG system prompts grounded in retrieved documents for each client tenant.
Loaded directly from tenants/<tenant_id>/prompts.json with automatic file-level fallback to tenants/default/prompts.json.
"""

import logging
from typing import Dict, Any

from app.core.tenant_config import get_tenant_base, load_tenant_json, save_tenant_json

logger = logging.getLogger(__name__)

# Core fallback dictionary if prompts.json is completely absent
FALLBACK_PROMPTS = {
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
}


def get_tenant_prompts_map(tenant_id: str) -> Dict[str, str]:
    """
    Get prompt templates map for CS and EN for a given tenant.
    Loads from tenants/<tenant_id>/prompts.json with automatic file-level fallback to tenants/default/prompts.json.
    """
    prompts_data = load_tenant_json(tenant_id, "prompts.json", default_data=FALLBACK_PROMPTS)
    return {
        "cs": prompts_data.get("cs", FALLBACK_PROMPTS["cs"]),
        "en": prompts_data.get("en", FALLBACK_PROMPTS["en"]),
    }


def update_tenant_prompt(tenant_id: str, locale: str, prompt_text: str) -> Dict[str, str]:
    """
    Update custom system prompt for a tenant and locale directly in tenants/<tenant_id>/prompts.json.
    """
    loc = "cs" if locale.lower() == "cs" else "en"
    current_map = get_tenant_prompts_map(tenant_id)
    current_map[loc] = prompt_text
    
    save_tenant_json(tenant_id, "prompts.json", current_map)
    return current_map


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
