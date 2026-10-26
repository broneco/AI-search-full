# Modely, lokální JHU test a oprávnění

Embeddingový model má nezávislý katalog a aktivní index; JHU Nomic lze doplnit vedle Azure přes [samostatný postup](local-embeddings.md). Dropdown v konzolích vybírá inferenční model.

V administraci jsou všechny modelové volby v záložce **Modely a vyhledávání**, která nahrazuje původní záložku systémového promptu. Obsahuje model odpovědi, samostatné modely shrnutí a klasifikace, přípravu/výběr embeddingových indexů, načtení modelů z JHU API, oprávnění i editor promptu. Chat a dokumentové operace ukazují aktuální volby s odkazem pro změnu. Přepínání záložek zachovává volby, otevřené panely a rozepsaný prompt v dané relaci; prompt vyžaduje explicitní uložení. Samotné načtení modelů z API žádný model nestahuje ani neschvaluje.

Management přes **Dostupné modely a oprávnění → Obnovit z API** otevře dialog s živým inventářem. Discovery samo katalog nemění; explicitní přidání lokálních profilů, checkboxy a volbu embeddingů popisuje [tenantový registr](local-model-registry.md). Společný přehled umožňuje upravit CS/EN popisy, publikaci a skupiny; modelové volby podporují hledání podle popisu/parametrů. [Porovnání výsledků](admin-comparison.md) používá dvě oddělené konverzace na jednu otázku. Poslední sekce v Modely a vyhledávání sdružuje všechny tři prompty.

Modely se definují v `tenants/default/model_config.json`; celý tenantový soubor jej může nahradit. Výchozí profily pro chat, shrnutí a klasifikaci jsou nezávislé. `ju-prod` načítá JHU konfiguraci, ale jeho skutečná databázová identita zůstává `ju-prod`.

## Spuštění z VS Code po restartu

Pro nové opt-in automatické spojení použij [managed návod](jhu-managed-local.md) a úlohu **AI Search: start JHU local app** nebo backend s `-JhuManaged`; ruční OpenVPN v tomto režimu nezapínej. Následující postup popisuje původní direct variantu. Statický Qwen profil i nadále vyžaduje ověřený `JHU_LLM_VERIFIED_MODEL`; u profilů přidaných přes discovery se ověřuje jejich konkrétní digest.

1. Spusť Rancher Desktop/Docker Engine a připoj OpenVPN JHU.
2. Z kořene repozitáře spusť databázi a backend pro lokální tenant JHU:

```powershell
.\dev.ps1 -Action start-db
.\dev.ps1 -Action backend -Tenant jhu
```

`-Tenant` mění pouze tenant procesu; databáze zůstává lokální `ai_search_local`. Původní data ostatních tenantů se nepřepisují. Přihlas se lokálním účtem tenantu JHU; starý token jiného tenantu se odmítne. Frontendy spouštěj jako dosud, každý v samostatném terminálu:

```powershell
.\dev.ps1 -Action backend -Tenant jhu
npm --prefix frontend-admin run dev
```

V této pracovní kopii byl po ověření vytvořen ignorovaný `.env.jhu-model`. Obsahuje pouze JHU připojení; nikdy jej neposílej do Gitu, ZIPu ani image. Po novém klonu jej vytvoří interaktivní příkaz:

```powershell
.venv\Scripts\python.exe probe_jhu_model.py --save-env
```

Heslo se zadává skrytě. Skript vyžaduje ověřenou Windows OpenVPN trasu, provede dva neškodné dotazy a odmítne přepsat existující soubor. Bez `--save-env` pouze testuje již uložené údaje. První načtení modelu může trvat 40–90 sekund, pozdější syntetické dotazy trvaly přibližně 4–5 sekund; nejde o benchmark reálného RAG.

APP_ENV=local čte `.env.jhu-model` a potom `.env.local`; exportované process variables mají přednost. APP_ENV=test soubor s JHU údaji automaticky nečte. V `.env.local` proto nenechávej prázdné JHU hodnoty, které by záměrně přepsaly pomocný soubor. Výchozí lokální tenant Dolphin JHU model v katalogu nemá.

HTTP je povolené jen explicitním `JHU_LLM_ALLOW_HTTP=true` pro chráněné spojení. Lokální Windows adaptér před voláním kontroluje trasu přes `JHU_LLM_VPN_INTERFACE` (výchozí OpenVPN). VPN není end-to-end TLS a samotná existence `.env` neprokazuje dosažitelnost serveru.

## Ruční ověření konzolí

- Ověř dvě cloudové položky a v JHU také Qwen. Nenakonfigurovaný model je označený jako nedostupný; jeho chybu nelze obejít automatickým cloudovým fallbackem.
- Polož stejnou otázku dvěma modelům a zkontroluj název modelu, odpověď a citace. Změň model uprostřed konverzace a znovu načti historii.
- V administraci samostatně zvol model klasifikace a shrnutí. Shrnutí se použije, jen pokud je zapnuté obohacení shrnutím. Změna klasifikátoru vyžaduje novou analýzu konceptu; potvrzení používá serverový záznam původní analýzy.
- Jako Management povol GPT-5.4 jen vybrané skupině. Běžný uživatel mimo skupinu jej nemá v katalogu a přímý request skončí 403. Odebraná oprávnění neovlivňují existující oprávnění dokumentů.
- Vyzkoušej selhání modelu při shrnutí: nesmí se uložit zástupný AI text ani nahradit předchozí verze dokumentu.

`available` v katalogu potvrzuje konfiguraci, nikoli okamžitou dostupnost sítě nebo Azure deploymentu. Skutečný model Azure odpovědi se kontroluje vůči profilu; deployment se špatným modelem je chyba. Existující env s THINKING_DEPLOYMENT nastaveným na mini je nutné opravit na skutečný GPT-5.4 deployment.

## Testy a databáze

```powershell
.venv\Scripts\python.exe -m pytest tests/test_model_catalog.py -q
```

Živý syntetický test je explicitní, vyžaduje VPN a privátní soubor:

```powershell
$env:RUN_JHU_MODEL_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_model_catalog.py -k live_jhu_synthetic_rag -q
Remove-Item Env:RUN_JHU_MODEL_TESTS
```

Lokální SQL tabulku pravidel vytvoří běžný start backendu. Pro Azure spusť nejprve pouze plán:

```powershell
.venv\Scripts\python.exe migrate_model_access.py
```

Zápis vyžaduje `--apply --expect-host "<ověřený host>" --expect-db "<ověřená DB>" --expect-tenant "<přesný tenant>"`. Migrace pouze vytvoří chybějící tabulku; nedoplňuje restrikce, nemaže data ani nereindexuje. Návrat předchozího image může tabulku ponechat.

API full/fast reindex přijímá volitelné `summary_model_id` a `classification_model_id`; UI je předává ze samostatných voleb. CLI `full_refresh_ingest.py` má stejnojmenné přepínače `--summary-model-id` / `--classification-model-id`; bez nich použije tenantové výchozí hodnoty. Dosavadní Apply/target guardy zůstávají.

## Azure a předání zdrojů

VPN na notebooku nepropojí Container App s JHU. Ověřenou cloudovou trasu a secrets je nutné nastavit samostatně podle připraveného handoffu. Runtime podporuje i Key Vault reference `AZURE_KEY_VAULT_SECRET_JHU_LLM_USERNAME` a `AZURE_KEY_VAULT_SECRET_JHU_LLM_PASSWORD`; žádné nové RBAC granty aplikace sama nevytváří.

Backend image, frontend release, SQL migrace a aktivace JHU spojení jsou samostatné operace. Změna LLM nevyžaduje migraci vektorových tabulek ani ANN aktivaci. JHU source export musí zahrnout jeho model_config a tento aktuální návod, nikdy privátní `.env.jhu-model`.
