# AI Search

AI vyhledávání nad dokumenty s citacemi a PDF náhledy. Backend používá Python/FastAPI, uživatelská aplikace a administrace Next.js/React. Aktuální cloudová cesta je Azure SQL + Blob Storage + Azure OpenAI; lokální vývoj má vlastní SQL Server v Dockeru.

Aktuální vydání: **[v0.1.8](docs/releases/v0.1.8.md)** · [Changelog](docs/CHANGELOG.md) · [Mapa repozitáře](docs/navigation_guide.md)

## Rychlý start ve VS Code

Příkazy spouštěj z kořene repozitáře v PowerShellu. Potřebuješ Python 3.12, Node.js/npm, ODBC Driver 17 nebo 18 for SQL Server a spuštěný Rancher Desktop nebo Docker Desktop s Linux kontejnery. Pro Rancher zvol Docker/Moby engine; dostupnost ověří `docker info`. Dockeru rezervuj alespoň 4 GiB RAM.

### První instalace

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix frontend-user ci
npm --prefix frontend-admin ci
.\dev.ps1 -Action start-db
```

Poslední příkaz vytvoří ignorovaný `.env.local` s náhodným heslem a spustí databázi `ai_search_local` na `127.0.0.1:1433`. Data zůstávají v persistentním Docker volume.

Python závislosti jsou jednotně v `pyproject.toml`; `requirements.txt` instaluje projekt s vývojovým extra (`.[dev]`). Pro runtime bez testů použij `python -m pip install .`. Wheel zahrnuje backend a veřejné tenantí konfigurace/fixtures, nikdy soukromé env. Instalaci spouštěj z kořene repozitáře.

Pro skutečné embeddingy a odpovědi doplň do **existujícího** `.env.local` svoje modelové připojení. Zachovej automaticky vytvořené databázové hodnoty:

```dotenv
AZURE_OPENAI_ENDPOINT=<tvůj Azure OpenAI endpoint>
AZURE_OPENAI_API_KEY=<soukromý klíč>
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<název embedding deploymentu>
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large
AZURE_OPENAI_EMBEDDING_MODEL_REVISION=1
AZURE_OPENAI_EMBEDDING_DIMENSIONS=1536
AZURE_OPENAI_FLASH_DEPLOYMENT=<název chat deploymentu>
AZURE_OPENAI_THINKING_DEPLOYMENT=<název chat deploymentu>
```

Jména deploymentů musí odpovídat tvému Azure prostředí. Výchozí modelové připojení používá Azure. JHU navíc podporuje Qwen pro inference a Nomic pro embeddingy přes vlastní službu; aktivace embeddingového indexu je samostatná. Viz [lokální embeddingy a více indexů](docs/development/local-embeddings.md). Bez modelového připojení lze spustit API/UI a izolované testy. `.env.local` necommituj.

### Každodenní spuštění a restart počítače

**JHU s automatickým připojením:** po [první přípravě helperu a Key Vaultu](docs/development/jhu-managed-local.md) vyber úlohu **AI Search: start JHU local app**. Spustí i administraci a vlastní VPN helper; systémovou OpenVPN ručně nezapínej. V ručním bloku backendu níže použij pro tento režim `-JhuManaged`:

```powershell
$tenant = "jhu"
.\dev.ps1 -Action start-db
.\dev.ps1 -Action backend -Tenant $tenant -JhuManaged
# Stav: .\dev.ps1 -Action status-jhu -Tenant $tenant
# Ukončení spojení: .\dev.ps1 -Action stop-jhu -Tenant $tenant
```

Výchozí spuštění bez přepínače zachovává dosavadní připojení. Lokální managed RAG byl živě ověřen bez systémové VPN. [Stav, obnova připojení a testování výpadků](docs/development/jhu-connection-resilience.md) popisuje správní refresh bez restartu backendu. Azure nasazení zůstává samostatný krok.

Ve VS Code zvol **Terminal → Run Task… → AI Search: start local app**. Úloha spustí SQL Server, backend a uživatelský frontend s nastavením úlohy a `.env.local`.

#### Ruční spuštění pro vybraný tenant — JHU nebo jiný

Následující tři bloky spouštěj z kořene projektu, každý ve vlastním terminálu. **Tenant se zadává na řádku `$tenant = "jhu"` v každém bloku.** Pro jiný nakonfigurovaný tenant změň tuto hodnotu ve všech třech blocích, například na `"dolphin"` nebo `"showcase"`. Proměnné se mezi terminály nesdílejí. Pro JHU používej malé `jhu`.

Přepínač backendu `-Tenant $tenant` přepíše lokální nastavení pouze pro spuštěný proces, `.env.local` nemění.

```powershell
# Terminál 1: databáze a backend
$tenant = "jhu"  # Změň podle potřeby; v hlavním repu např. "dolphin" nebo "showcase"

.\dev.ps1 -Action start-db
.\dev.ps1 -Action backend -Tenant $tenant
```

```powershell
# Terminál 2: uživatelská aplikace
$tenant = "jhu"  # Stejný tenant jako u backendu

$env:NEXT_PUBLIC_CLIENT_THEME = $tenant
$env:NEXT_PUBLIC_BACKEND_URL = "http://localhost:8000"
& .\frontend-user\node_modules\.bin\next.cmd dev .\frontend-user --webpack --hostname 127.0.0.1 --port 3000
```

```powershell
# Terminál 3: volitelná administrace
$tenant = "jhu"  # Stejný tenant jako u backendu

$env:NEXT_PUBLIC_CLIENT_THEME = $tenant
$env:NEXT_PUBLIC_BACKEND_URL = "http://localhost:8000"
& .\frontend-admin\node_modules\.bin\next.cmd dev .\frontend-admin --webpack --hostname 127.0.0.1 --port 3001
```

`NEXT_PUBLIC_CLIENT_THEME` vybírá vzhled konzole, nikoli datová oprávnění. Ta určuje přihlášený účet a backend; použij účet odpovídající zvolenému tenantu. Po změně tenantu restartuj příslušné služby a přihlas se odpovídajícím účtem. Jiný tenant musí mít dostupnou konfiguraci a frontendové téma; čistý JHU export obsahuje pouze JHU. Přímé volání `next.cmd` zachovává přepínače i v PowerShellu, kde předávání přes `npm --prefix … run dev -- …` může selhat.

| Služba | Adresa |
|---|---|
| Uživatelská aplikace | http://localhost:3000 |
| Administrace | http://localhost:3001 |
| API / Swagger | http://localhost:8000/docs |

Lokální prázdná databáze vytvoří demo účty: `user@dolphin.cz` / `password123` a `admin@dolphin.cz` / `DolphinAdmin26`. Platí pouze pro local/test; cloud demo účty automaticky nevytváří. Pokud už databáze uživatele obsahuje, použij existující přihlášení.

Po doplnění modelového připojení startup automaticky naindexuje dva české dokumenty o fiktivní Vysoké škole Aurora. Další start je nepřepočítává, pokud se nezměnil profil nebo obsah. Vyzkoušej „Kolik pokusů mám na zkoušku?“ nebo „Kdy má studijní oddělení úřední hodiny?“ a otevři citaci PDF. Podrobnosti jsou v [lokálním návodu](docs/development/local-setup.md).

Backend a frontend zastav přes Ctrl+C. Databázi zastavíš bez smazání dat:

```powershell
.\dev.ps1 -Action stop-db
```

Po restartu počítače zapni Docker/Rancher a znovu spusť stejnou VS Code úlohu. Zachovej `.env.local` i SQL volume, aby souhlasilo heslo a zůstala uložená data.

## Lokální testování

| Varianta | Co ověřuje | Co potřebuje |
|---|---|---|
| Izolované testy | API, profily, ACL, repository a SQL kontrakty; modely jsou nahrazené | Python závislosti; bez Azure a Dockeru |
| Lokální SQL testy | Skutečný SQL Server dialect, transakce a přesná JSON reference | Běžící lokální SQL Server a `.env.local`; bez Azure modelů |
| Azure native testy | Skutečný VECTOR, DiskANN a fulltext | Explicitní opt-in, potvrzený Azure SQL cíl a oprávnění |

Základní izolovaná sada:

```powershell
.\dev.ps1 -Action test
```

Stejný příkaz nabízí VS Code úloha **AI Search: run isolated tests**.

Dočasné pracovní soubory pytest ukládá pod `.local/tmp/pytest/`, cache pod `.local/pytest-cache/`. Výchozí číslované adresáře oddělují souběžné běhy; pytest uchovává tři poslední běhy s ochranou aktivních relací. Není potřeba zadávat `--basetemp`. Backend sleduje pro automatický restart pouze `app/`, takže testovací kopie zdrojů jej nerestartují.

Pro lokální SQL regrese spusť v samostatném terminálu:

```powershell
.\dev.ps1 -Action start-db
$env:RUN_LOCAL_SQL_TESTS = "1"
.\dev.ps1 -Action test
Remove-Item Env:RUN_LOCAL_SQL_TESTS
```

SQL testy vytvářejí vlastní testovací databáze a nepracují nad aplikační `ai_search_local`. SQL Server 2022 lokálně neověřuje nativní Azure VECTOR/DiskANN ani cloudový fulltext. Skips u nepovolených integračních testů jsou očekávané. Postupy: [ACL](docs/development/search-slice-2-testing.md), [vektorové úložiště](docs/development/search-slice-3-testing.md), [ANN](docs/development/search-slice-4-testing.md), [benchmark](docs/development/search-slice-5-testing.md).

Izolovaná sada nepotřebuje soukromé tenantí env. Strukturální kontrola skutečných env přijme alespoň jeden vyplněný tenant; nevyplněné placeholdery ignoruje a při chybějících env přeskočí jen tuto kontrolu. Syntetický jednotenantový test běží vždy. Nejde o ověření funkčnosti skutečných Azure credentials.

Skutečné sestavení a import wheelu mimo checkout:

```powershell
.venv\Scripts\python.exe -m pip install setuptools wheel
$env:RUN_PACKAGE_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_packaging.py -q
Remove-Item Env:RUN_PACKAGE_TESTS
```

Dotaz z CLI používá běžící API a stejnou autorizaci jako web; heslo zadáš skrytě, případně použij neveřejnou proměnnou `AI_SEARCH_TOKEN`:

```powershell
.venv\Scripts\python.exe ask.py --email user@dolphin.cz "Kolik pokusů mám na zkoušku?"
```

Pro kontrolu obou frontendů bez nasazení:

```powershell
npm --prefix frontend-user run build
npm --prefix frontend-admin run build
```

## Deployment do Azure

Přechod k aktualizacím se zachováním stavu: [trvalá nastavení, první import a bezpečný release](docs/development/non-destructive-updates.md). První převod vyžaduje aditivní migraci `migrate_tenant_settings.py` a zachycení současných promptů/search/classification. Pro JHU je převod i restart skutečně ověřený: [výsledek nasazení](docs/deployments/2026-10-29-durable-settings-rollout.md).

JHU backend, VPN sidecar a obě konzole jsou nasazené; [ověřený stav, provozní hranice a návrat](docs/deployments/2026-10-29-jhu-sidecar-rollout.md). Administrátorský vector/hybrid má otevřený SQL timeout; explicitní keyword funguje. Lokální helper se stejným VPN účtem nespouštěj souběžně s ACA bez koordinace relací.

Cloudové JHU připojení má samostatný [runbook pro dvoukontejnerový sidecar](docs/development/jhu-sidecar-azure.md). Nový `deploy_jhu_sidecar.py` nejprve vytvoří read-only plán; lokální managed start ani zdrojové vydání jej v Azure nezapínají.



Release backendu, migrace databáze a release frontendů jsou samostatné kroky. Příkazy spouštěj v novém terminálu bez lokálně exportovaných SQL/modelových proměnných. Ověř aktivní Azure účet a subscription:

```powershell
az login
az account show --query "{subscription:id,tenant:tenantId,name:name}" --output table
```

Pro běžný release existujícího prostředí používej níže uvedené skripty. Neveřejná konfigurace je v `tenants/<client>/.env.dev` nebo `.env.prod`; nikdy se nekopíruje do image. Identita a modelové parametry backendu musí být nastavené předem. Pro JHU používá adresář konfigurace `jhu`, skutečný tenant korpusu je `ju-prod` a Azure názvy začínají `ju-`; tyto hodnoty nezaměňuj podle vzhledu názvu.

### Backend: nejdřív čtecí plán

```powershell
.\deploy_backend.ps1 -Client jhu -Environment prod
```

Bez `-Apply` skript nic nestaví ani nemění v Azure. Plán vypíše cíl, současnou image a blokery. Chybějící RG/ACR lze zadat přes `-ResourceGroup` / `-RegistryName`. Po vyřešení blokérů a samostatném ověření migrací spusť:

```powershell
.\deploy_backend.ps1 -Client jhu -Environment prod `
  -ExpectedSubscriptionId "<ověřené subscription ID>" `
  -ExpectedAzureTenantId "<ověřené Azure directory ID>" `
  -ExpectedCurrentImage "<přesná image ze zkontrolovaného plánu>" `
  -MigrationConfirmed -JwtMigrationConfirmed -Apply
```

Přepínači potvrzuješ hotovou databázovou a JWT/heslovou přípravu; skript tyto migrace neprovádí. Apply sestaví image přes ACR a aktualizuje image existující Container App. Nemění její secrets, identitu, kapacitu ani korpus. Po dokončení ověř připravenou revizi, přihlášení, chat s citacemi a PDF. Předchozí image uchovej pro návrat; starý verifier nemusí rozumět novým Argon2 hashům.

### Frontendy: samostatný build a zápis do SWA

Předem nainstaluj závislosti přes `npm --prefix frontend-user ci` a `npm --prefix frontend-admin ci`. Nejdřív zobraz čtecí plán pro obě aplikace:

```powershell
.\deploy_frontend.ps1 -Client jhu -Environment prod -AppType user `
  -ClientTheme jhu -ResourceGroup "ju-ai-search-rg-prod" `
  -BackendUrl "<ověřená HTTPS URL backendu>"

.\deploy_frontend.ps1 -Client jhu -Environment prod -AppType admin `
  -ClientTheme jhu -ResourceGroup "ju-ai-search-rg-prod" `
  -BackendUrl "<ověřená HTTPS URL backendu>"
```

Bez `-Apply` skript pouze čte. Název existující SWA bere z `AZURE_SWA_USER_NAME` / `AZURE_SWA_ADMIN_NAME` nebo explicitního `-StaticWebAppName`; nepoužívá odhad cíle ani fallback na cizí backend. Pro skutečný release přidej k příslušnému výše uvedenému příkazu `-Apply -ExpectedSubscriptionId "<ověřené ID>" -ExpectedAzureTenantId "<ověřené directory ID>"`. Zkontroluj plán před přidáním těchto přepínačů. Skript nikdy nevytváří SWA a při chybě čtení, buildu nebo publikování končí nenulovým kódem. Po nasazení ověř verzi, přihlášení, CORS a citace; samotný build není dokončená cloudová akceptace.

### Migrace a stav hledání

| Skript / dokument | Použití |
|---|---|
| `migrate_search_schema.py` | Explicitní tenant/Unicode/FTS migrace pro potvrzený cíl |
| `migrate_search_acl.py` | Audit a doplnění relačních dokumentových/chunkových ACL |
| `migrate_search_vectors.py` | Audit, profilové tabulky, backfill, aktivace indexu a volitelné vytvoření DiskANN |
| `benchmark_search.py` | Příprava query cache a exact/ANN benchmark; bez automatické aktivace |
| [JHU deployment report](docs/deployments/2026-10-15-jhu-search-rollout.md) | Skutečný stav, výsledky ověření a návrat nasazení |
| [JHU migrační handoff](.agents/inbox/2026-10-15-jhu-search-rollout-handoff.md) | Pořadí databázových/modelových kroků pro JHU |
| [JWT a heslový handoff](.agents/inbox/2026-10-15-jhu-jwt-password-migration-handoff.md) | Key Vault, oddělený legacy klíč a Argon2 přechod |

Dokončené JHU migrace se při běžném release neopakují. **Výchozí i současný JHU režim je `exact`.** DiskANN v3 je připravené volitelné rozšíření; některé filtrované dotazy timeoutovaly a reprezentativní recall/p95 akceptace zůstává otevřená. Vytvoření ANN indexu jej neaktivuje.

`deploy_all.ps1` je úmyslně blokovaný. `reset_users_db.py` slouží k destruktivní obnově účtů/historie. Staré infrastrukturní návody nejsou náhradou aktuálního release postupu; `infra/main.bicepparam` má dosud zdokumentovaný nesoulad se současnou šablonou. Historické workflow pro již neexistující jediný `frontend/` bylo odstraněno; aktuální frontendy se nasazují výše uvedeným postupem.

Full-refresh je samostatná údržba. Výchozí spuštění jen ověří zdroje a vypíše plán; přesný tenant musí odpovídat již nakonfigurovanému `TENANT_ID`:

```powershell
.venv\Scripts\python.exe full_refresh_ingest.py --tenant ju-prod --data-dir "<zdrojové PDF/TXT>"
```

Zápis vyžaduje `--apply --expect-tenant ju-prod`, v cloudu také `--expect-host "<ověřený host>" --expect-db "<ověřená DB>"`. Dokumenty se nahrazují jednotlivě až po přípravě embeddingů. Původní nepoužité dokumenty se odstraní až po úspěšném zpracování všech vstupů; při pozdější chybě mohou zůstat úspěšné náhrady, zbytek se nepromaže. Nové souběžné uploady a změněné stale řádky jsou chráněné. Automatický scan sdíleného kořene `data/` se nepoužívá; API full-refresh potřebuje tenantí podadresář, jinak bezpečně skončí chybou. Fast reindexace zpracovává pouze dokumenty přesného přihlášeného tenantu.

## Vydání a předání JHU

Hlavní GitHub repozitář, izolovaný JHU repozitář na Forgejo a nasazení do Azure jsou tři samostatné operace. Verzi zdrojů vydáváme v hlavním repu; JHU dostává jen očištěný snapshot a navazující souhrnné commity bez naší vývojové historie. Předání zachovává úplnou veřejnou dokumentaci včetně changelogu, release notes a testových vysvětlení; vynechává ADR soubory. Runtime konfigurace a branding zůstávají pouze JHU. Aktuální exportéry a templates jsou verzované, takže postup funguje i po novém klonu.

- Přehled a příkazy: [předávání JHU](docs/development/jhu-publication.md).
- Podrobný postup pro AI, kontroly obou Gitů, obnovení po přerušení a oddělený Azure release: [kanonický workflow](.agents/workflows/jhu-publication.md).
- `export_jhu.py` vytváří balíček z konkrétního commitnutého tagu/refu; `prepare_jhu_publication.py` vypíše plán a soubory mění až s `--apply --expect-head`.

Tyto nástroje samy necommitují, nepushují a nenasazují Azure. Existující privátní env může přepsat `APP_VERSION`; před skutečným releasem aplikace je nutné ověřit běžící verzi zvlášť.

## Co je kde

Pro přenos do nového repozitáře použij aktuální veřejné zdroje včetně `.agents/`, tenantích JSON/assets, fixtures a obou frontendových lock souborů. Nepřenášej starou `.git` historii, `.env*` kromě `.env.example`, `.local/`, uživatelská data, `.venv`, `node_modules` ani build/cache výstupy. Nové prostředí nainstaluj příkazy výše a spusť izolované testy; jeden skutečně vyplněný tenant pro volitelnou kontrolu env stačí. Při převzetí původní Git historie zůstávají relevantní historicky zveřejněné credentials a jejich samostatná rotace.

| Cesta | Účel |
|---|---|
| Kořenové `.py` / `.ps1` | CLI pro vývoj, dotazy, ingestaci, migrace, benchmark a deployment |
| `app/` | Backend, retrieval, providery, ingestace a repository |
| `frontend-user/`, `frontend-admin/` | Dvě aktuální webové aplikace |
| `tenants/` | Verzované konfigurace a branding; neveřejné `.env*` jsou ignorované |
| `fixtures/` | Veřejné fiktivní dokumenty a smoke otázky |
| `tests/` | Izolované, lokální SQL a opt-in Azure testy |
| `docs/` | Changelog, release notes, návody, architektura a ADR |
| `infra/` | Infrastrukturní zdroje; historický PostgreSQL compose je v `infra/legacy/` |
| `.agents/` | Kanonická pravidla, paměť projektu a handoffy |
| `.local/` | Ignorované overlay, benchmarky, provozní skripty a chráněné zálohy |

`Dockerfile`, aktuální Compose, `.gitignore`, `.dockerignore`, `pyproject.toml`, `requirements.txt` a `AGENTS.md` zůstávají v kořeni kvůli nástrojům a spuštění. Uživatelské dokumenty v `data/`, původní záloha `data - full backup/`, env soubory, databázový volume, `.venv` a `node_modules` nejsou odpad pro automatické mazání. Přehled provedeného úklidu a zbývajících kandidátů je v [inventuře repozitáře](docs/development/repository-cleanup.md).

## Výběr modelů

Tenantový `model_config.json` definuje GPT-5.4-mini, GPT-5.4 a v JHU také Qwen. Obě konzole vybírají model pro další dotaz. V administraci záložka **Modely a vyhledávání** sdružuje modely odpovědí/shrnutí/klasifikace, načtení z JHU API, skupinová oprávnění, přípravu/výběr embeddingových indexů a systémový prompt. Chat ukazuje aktuální model/index s odkazem pro změnu. Výběr odpovědního modelu embeddingy nemění; explicitní volba indexu nemění výchozí ingestaci.

[Spuštění a testování modelů](docs/development/model-selection.md), [architektura a slices](docs/architecture/model-catalog-roadmap.md). Pro lokální JHU backend použij [automatický managed start](docs/development/jhu-managed-local.md), případně přímý režim s vlastní ověřenou VPN. Azure má [samostatný sidecar rollout](docs/development/jhu-sidecar-azure.md) a potřebuje ověřené modelové SQL tabulky.

Experiment automatického připojení bez systémové VPN je oddělený [Docker probe](docs/development/jhu-vpn-spike.md). Ověřuje vlastní tunel, modelové API, embeddingy a reconnect; zatím se nezapojuje do `dev.ps1` ani aplikace.

Navazující [pomocná JHU služba a Key Vault](docs/development/jhu-connection-helper.md) už má samostatné příkazy `jhu_connection.py start/status/reconnect/restart/stop` a kontrolu čtyř secrets. Jde zatím o operátorský nástroj; běžná aplikace použije nový transport až v dalším slicu.


Další lokální modely přidáš přes **Modely a vyhledávání → Dostupné modely a oprávnění → Obnovit z API**. Inventář se otevře v dialogu; trvalý přehled spojuje účely/parametry, publikaci, skupiny a editovatelný popis CS/EN. Pro embeddingy Nomic/MXBAI následně připrav konkrétní index. [Návod a lokální/cloudové hranice](docs/development/local-model-registry.md).

**Porovnání výsledků** v administraci (`Management`) odešle jednu otázku do dvou nezávislých konverzací s vlastními modely, filtry a indexy. Vyhledávatelné modelové volby a všechny tři prompty jsou v **Modely a vyhledávání**. Po aktualizaci restartuj lokální backend kvůli tabulce popisů; Azure potřebuje samostatnou migraci `migrate_model_metadata.py` a schválené nasazení. [Podrobný postup porovnání a správy promptů](docs/development/admin-comparison.md).

Limit výstupu modelu nastavíš v **Dostupné modely a oprávnění → Konfigurace aplikace → Maximální délka výstupu (tokeny)**. **Uložit limit** platí pro nové chatové/dokumentové operace daného modelu, **Použít výchozí** obnoví původní hodnotu. Lokálně restartuj backend pro vytvoření `model_runtime_settings`; Azure vyžaduje samostatný schválený `migrate_model_limits.py`. [Rozsahy a vliv na lokální kontext](docs/development/admin-comparison.md#nastavení-maximální-délky-výstupu).
