# Vysvětlení testovacího modulu `test_tenant_config.py`

Tento dokument vysvětluje účel, strukturu a fungování testovacího modulu `test_tenant_config.py`.

---

## 1. Vysoká technická úroveň (High Level Overview)

Testovací modul `test_tenant_config.py` ověřuje správnost fungování sjednoceného načítání konfigurací jednotlivých klientů (tenantů) ze složky `tenants/` a bezchybnou funkčnost **souborového fallback systému** z `tenants/default/`.

### Hlavní testované oblasti:
1. **Extrakce bázového názvu tenanta (`get_tenant_base`)**: Převod komplexních ID prostředí (např. `alzbeta-prod`, `dolphin-dev`) na bázový název tenanta (`alzbeta`, `dolphin`).
2. **Souborová rezoluce a fallback (`resolve_tenant_file_path`)**: Ověření, že pokud tenant nemá vlastní konfigurační soubor (např. `alzbeta` nemá vlastní `search_config.json`), systém automaticky a transparentně sbalí rezoluci na `tenants/default/search_config.json` a indikuje `is_fallback_used = True`.
3. **Načítání RAG promptů per tenant (`get_tenant_prompts_map`)**: Kontrola, že se správně načtou specifické systémové prompty pro Nemocnici sv. Alžběty, Jihočeskou Univerzitu i výchozí prompty pro neznámé tenanty.
4. **Formátování systémového promptu (`get_system_prompt`)**: Ověření, že se do načtené šablony promptu správně vloží získaný kontext dokumentů `{context_str}`.
5. **Integrovaný správce vyhledávání (`SearchConfigManager`)**: Ověření, že správce vyhledávací konfigurace korektně načte nastavení ze složky tenantů.

---

## 2. Nízká technická úroveň (Low Level Technical Details)

- **Importy**: Importuje funkce `resolve_tenant_file_path`, `load_tenant_json`, `save_tenant_json`, `get_tenant_base` z modulu `app.core.tenant_config` a `get_tenant_prompts_map`, `get_system_prompt` z `app.core.prompts`.
- **Testovací funkce**:
  - `test_tenant_base_extraction()`: Porovnává řetězce přes `assert get_tenant_base(...) == expected`.
  - `test_tenant_file_resolution_and_fallback()`: Testuje `resolve_tenant_file_path("dolphin", "prompts.json")` -> `is_fallback == False`; a `resolve_tenant_file_path("alzbeta", "search_config.json")` -> `is_fallback == True`.
  - `test_tenant_prompts_loading()`: Kontroluje přítomnost klíčových podřetězců ("Nemocnice sv. Alžběty", "Jihočeské univerzity") v načtených promptových mapách.
  - `test_system_prompt_formatting()`: Volá `get_system_prompt()` s testovací výplní a ověřuje řetězec odpovědi.
  - `test_search_config_manager_tenant_loading()`: Ověřuje `SearchConfigManager().load_config_sync()`.
  - `test_tenant_branding_key_parity_and_jhu()`: Načte `branding.json` pro 5 tenantů, ověří 100% paritu klíčů a otestuje JCU hodnoty pro tenant `jhu` (`appName == "JCU AI Search"`, `demoEmail == "user@jcu.cz"`).
