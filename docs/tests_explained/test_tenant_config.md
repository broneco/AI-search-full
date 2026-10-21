# Vysvětlení testovacího modulu `test_tenant_config.py`

Tento dokument vysvětluje účel, strukturu a fungování testovacího modulu `test_tenant_config.py`.

---

## 1. Vysoká technická úroveň (High Level Overview)

Testovací modul `test_tenant_config.py` ověřuje správnost fungování sjednoceného načítání konfigurací jednotlivých klientů (tenantů) ze složky `tenants/` a bezchybnou funkčnost **souborového fallback systému** z `tenants/default/`.

### Hlavní testované oblasti:
1. **Extrakce bázového názvu tenanta (`get_tenant_base`)**: Převod komplexních ID prostředí (např. `alzbeta-prod`, `dolphin-dev`) na bázový název tenanta (`alzbeta`, `dolphin`).
2. **Souborová rezoluce a fallback (`resolve_tenant_file_path`)**: Dočasné syntetické složky alpha/default ověřují fallback chybějícího souboru a příznak `is_fallback_used`, bez závislosti na dalších skutečných klientech.
3. **Načítání RAG promptů per tenant (`get_tenant_prompts_map`)**: Kontrola JHU, aliasu `ju-prod` a obecného fallbacku pro neznámou identitu.
4. **Formátování systémového promptu (`get_system_prompt`)**: Ověření, že se do načtené šablony promptu správně vloží získaný kontext dokumentů `{context_str}`.
5. **Integrovaný správce vyhledávání (`SearchConfigManager`)**: Ověření, že správce vyhledávací konfigurace korektně načte nastavení ze složky tenantů.

---

## 2. Nízká technická úroveň (Low Level Technical Details)

- **Importy**: Importuje funkce `resolve_tenant_file_path`, `load_tenant_json`, `save_tenant_json`, `get_tenant_base` z modulu `app.core.tenant_config` a `get_tenant_prompts_map`, `get_system_prompt` z `app.core.prompts`.
- **Testovací funkce**:
  - `test_tenant_base_extraction()`: Porovnává řetězce přes `assert get_tenant_base(...) == expected`.
  - `test_tenant_file_resolution_and_fallback()`: Ověřuje vlastní syntetický prompt a sdílený syntetický search_config; přesměrování resolveru platí pouze během testu.
  - `test_tenant_prompts_loading()`: Kontroluje text JHU a stejný prompt přes alias, i fallback bez přibaleného default tenantu.
  - `test_system_prompt_formatting()`: Volá `get_system_prompt()` s testovací výplní a ověřuje řetězec odpovědi.
  - `test_search_config_manager_tenant_loading()`: Ověřuje `SearchConfigManager().load_config_sync()`.
  - `test_tenant_branding_key_parity_and_jhu()`: Ověří paritu všech skutečně přibalených brandingů vůči JHU a jeho konkrétní hodnoty; nevyžaduje pět tenantů, postačuje samotný JHU.

## Aktualizace aliasů

Současné regrese ověřují, že `ju-prod` načítá stejný JHU prompt jako `jhu`, zatímco databázové ID zůstává přesné. Sdílený resolver se používá pro modelové env i JSON konfiguraci; lokální overlay a file-level fallback zůstávají zachované.

## Modelové profily

Lokální profil může načíst ignorovaný JHU model env před .env.local; test profil čte pouze .env.test.
