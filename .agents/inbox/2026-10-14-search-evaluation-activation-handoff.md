# Azure Deployment Handoff: evaluace a lidská aktivace search slice 5

- Status: waiting-for-human
- Created: 2026-10-14
- Related task: search slice 5 — dokončení skutečných cloudových bran
- Related ADR: docs/adr/ADR-0025-reproducible-search-evaluation-and-human-activation.md
- Related branch/PR: uncommitted local implementation; no cloud rollout

## Why this handoff exists

Lokálně je implementovaný a otestovaný benchmark/cache/report; lokální Docker má SQL Server 2022. Native integrace a cílový benchmark dosud neproběhly. Uživatel následně zvolil EXISTUJÍCÍ Showcase DB a potvrdil, že Showcase slouží jen pro testování/demonstrace a lze jej v rámci schválených zásahů upravit a na konci obnovit funkční stav. Potvrdil CLI přístup agenta k Azure a vyžaduje schválení cloudových změn. Starší pravidlo o výhradně ručním Azure přístupu zde nahrazuje tato přímá uživatelská instrukce; není to blanket souhlas s mutacemi.

## Aktuální postup a ověřený Azure inventář (2026-10-14)

### Funkční native exact/ANN test — schválen a proveden, oba scénáře prošly

**Konečný výsledek 2026-10-14:** explicitní schválení při spuštění nástroje pokrylo pouze níže popsané disposable schéma v existujícím Showcase. Native exact scénář skutečně prošel. Po opravách prošel native ANN lifecycle scénář (1 passed, 36 deselected), DiskANN **version3 / COSINE / enabled / 1536dim**, exact selected1 / ANN selected1, selective/empty/fullK, tenant/docACL/chunkACL, revize/reembedding/update/rollback/cascade. Každý běh odstranil vlastní schéma a potvrdil dbo counts **35docs/1385chunks/6users/5threads/10messages**. Žádný trvalý profilový/ANN index nezůstal v běžném dbo; běžící app/image/config se nezměnily.

Skutečné testy odhalily tři další opravy: (1) CREATE VECTOR INDEX error574 v user TX → samostatný AUTOCOMMIT DDL + zákaz neukončené caller TX; DDL nelze rollbacknout po verifikaci. (2) textové bind parametry musí zachovat typy a explicitní VARCHAR(MAX)/NVARCHAR(MAX), jinak DATALENGTH tenant parametru nesedí. (3) **SECURITY:** samostatná kompilace predikátů ztratila korelaci ACL EXISTS; nyní se kompiluje v kontextu outer chunks JOIN documents. Reálná lokální T-SQL regrese kontroluje zakázaný doc/chunk, cizí tenant, Management a empty filtr. Diagnostika během selhání rozlišovala raw ANN od hydratace, testová kritéria se nesnižovala.

Závěrečná celá lokální sada (RUN_LOCAL_SQL_TESTS=1, Azure/model opt-in vypnuté): **217 passed / 10 expected skips**, 120,80s. Cílená izolace/ANN/vector sada: **55 passed / 7 expected skips**. Compileall a diff check prošly. Native přesný test a native ANN test byly skutečně vykonány v samostatných schválených bězích; neplést s native skips v celé lokální sadě. No performance/recall acceptance: reprezentativní workload/cold start/runtime identita/HTTP/JWT/migrace běžné app jsou stále otevřené, výkon až na potvrzeném JHU cíli.

**Další jeden krok:** připravit konkrétní Showcase app schema/ACL/Unicode/profil migraci/backfill + matching backend deployment a API/PDF smoke s rollbackem, poté si vyžádat nové schválení. Testovací schéma souhlas neopravňuje měnit existující dbo, hesla/RBAC, Container App, kapacitu nebo JHU. Přímé Entra admin testovací přihlášení není důkazem připravené runtime identity nebo modelového bindingu.

Lokální harness je připravený a ověřený na SQLite / izolovaném lokálním SQL Serveru (při prvním schvalování 50 passed / 5 expected skips; novější výsledek výše). Produkční dbo se nemigruje. Oba skutečné native testy lze pustit postupně v jednom novém schématu, které fixture po každém testu odstraní a pro další znovu vytvoří. CREATE musí uspět na novém názvu, existující schéma se nikdy nepřebírá. Runtime aplikace se nemění.

Konkrétní schvalovaný cíl: `ai-search-showcase-sql-dev.database.windows.net` / `ai-search-showcase-sqldb-dev`, schéma **`ann_test_5d3dd2200872454b8f22d8287f8133af`**. Zásahy: CREATE SCHEMA, vlastní kopie ORM tabulek v tomto schématu (documents/chunks/ACL/profilové katalogy/users/chat; uživatelské/chat tabulky zůstávají prázdné), syntetické dokumenty/vektory, vlastní profilové VECTOR(2)/VECTOR(1536) tabulky, CREATE VECTOR INDEX cosine DiskANN MAXDOP1, testovací INSERT/UPDATE/DELETE/rollback, DROP výhradně vlastních tabulek/schématu. Původní dbo tabulky se jen spočítají před/po. Nic nezakládat v JHU, Key Vaultu, firewallu ani Container App; žádné modely/benchmark/změna kapacity. Po neočekávaných objektech cleanup zastaví pro review; neprovádět širší mazání.

```powershell
# Spuštění je cloudový zápis a vyžaduje explicitní schválení cíle/rozsahu výše.
$env:RUN_NATIVE_SQL_TESTS='1'
$env:RUN_NATIVE_ANN_TESTS='1'
$env:NATIVE_SQL_ALLOW_EXISTING='1'
$env:NATIVE_SQL_EXPECT_HOST='ai-search-showcase-sql-dev.database.windows.net'
$env:NATIVE_SQL_EXPECT_DB='ai-search-showcase-sqldb-dev'
$env:NATIVE_SQL_ISOLATED_SCHEMA='ann_test_5d3dd2200872454b8f22d8287f8133af'
.venv\Scripts\python.exe -m pytest tests/test_vector_store.py tests/test_ann_search.py -k 'native_vector_end_to_end or native_ann_filters' -q -s --tb=short --disable-warnings --basetemp .tmp-pytest-showcase-native-20261014-a
```

Fixture používá Entra token pouze v paměti; nevyžaduje `.env.native-test` ani heslo. Expected výsledek: oba testy skutečně provedené, v3+ index, tenant/docACL/chunkACL/metadata/selective/empty/fullK, změny revizí/update/rollback/cascade. Exact navíc nejlepší výsledek za 625 a oddělení profilů. Kontrola zachování dbo počtů a úplného odstranění schématu proběhne i při chybě. Tato integrační akceptace neměří recall/performance a neopravňuje přepnout běžný Showcase runtime na ANN. Starší empty-only návod níže není určen pro aplikační dbo.

### Aktuální výsledek: přímé Entra přihlášení BEZ Key Vaultu funguje

Uživatel následně požádal Key Vault prozatím vynechat. **Návrh přidělení KV role níže je odložený, neprovádět jej.** Read-only ARM audit zjistil, že existující SQL Entra administrator SID je shodné s aktuálním Azure CLI uživatelem (`27b07391-a506-4e13-9246-145830460d50`), azureADOnlyAuthentication=false. Připojení tokenem získaným přes Azure CLI pro `https://database.windows.net/` skutečně uspělo přes ODBC17. Token byl pouze v paměti a nebyl vypsán ani uložen. Žádné role/heslo/firewall ani cloudové nastavení se neměnily. Technický postup bez lokálního azure.identity je v `docs/development/search-slice-5-testing.md`, sekce Showcase.

**Skutečně ověřeno SELECTy:** DB `ai-search-showcase-sqldb-dev`, EngineEdition5, compatibility170; 35 dokumentů, 1385 chunků, 6 uživatelů, 5 threadů a 10 zpráv (jen agregované počty, bez textů a osobních údajů); existují pouze původní documents/chunks/users/chat tabulky. Profilový/aktivní/ACL katalog dosud chybí, vector indexy žádné, FTS chunks zapnuté. Původní title/content sloupce zůstávají VARCHAR, Unicode migrace neproběhla. CREATE TABLE/ALTER dbo/SELECT oprávnění existují, nebyla využita k zápisu.

**Reálná chyba a lokální oprava:** scalar VECTOR_DISTANCE nad literal VECTOR(2) vrací 0/1, ale dlouhý parametr 1536dim (>4000 znaků) přes pyodbc a SQLAlchemy Text/Unicode skončil chybou 529: NTEXT nelze převést přímo na VECTOR. Opraveno jen lokálně v `vector_store.py`/`ann_search.py`: `CAST(CAST(:json AS NVARCHAR(MAX)) AS VECTOR(dim))` pro native INSERT binding, exact query a ANN deklaraci. Na skutečném Showcase prošly všechny 4 SELECTy používající společný write/exact převod a 2 SELECTy používající skutečný prefix produkční ANN deklarace, identické/kolmé vektory (0/1). Jde o ověření transportu/deklarace, **nikoli skutečný INSERT ani VECTOR_SEARCH**. Žádný profilový/native/ANN objekt nevznikl.

Cílené testy SQLite + izolovaného lokálního SQL Serveru po opravě: **41 passed, 3 expected skips** (native exact/ANN a SQLite varianta MSSQL-only timeoutu). Compileall a diff check prošly. Azure změny a deployment nadále vyžadují schválení; native transakční lifecycle, skutečné ANN prefiltry a aplikace po migraci zůstávají neověřené. Další krok: připravit konkrétní funkční integrační zásah na existujícím Showcase s návratem do funkčního stavu; pak vyžádat schválení zápisů. Výkon až později na potvrzeném JHU prostředí. Klientské Entra admin přihlášení není důkazem funkčních přístupů runtime identity Container App.

### Historie před funkčním Entra přihlášením — SQL heslo / Key Vault

Uživatel následně schválil zahájení funkčního ověření na Showcase; výkonové měření odkládá na vyvíjený JHU tenant. Nyní neměnit Showcase SKU/CPU/RAM kvůli benchmarku a nespouštět workload na JHU. Konkrétní JHU prostředí/DB a jeho zátěžové okno vyžadují pozdější potvrzení.

První SQL pokusy vrátily 40613 během probouzení; ARM následně potvrdil **Online**. Poté SELECT-only spojení (ODBC17, Encrypt=yes, TrustServerCertificate=no, read-only access mode) skončilo **28000 / 18456 — login failed**. Lokální SQL uživatel odpovídá server administratorLogin i backend AZURE_SQL_USER; lokální heslo však přihlášení neumožnilo. Příčinu neoznačovat za prokázané chybné heslo bez dalšího ověření autentizace. Žádný SQL SELECT, native VECTOR probe, čtení dokumentových dat, DDL ani DML dosud neproběhly.

Následné čtení nakonfigurovaného SQL password secretu `showcase-ai-search-sql-sqlaccount-password-dev` ve vaultu `showcase-ais-kv-dev` přes Azure CLI skončilo **Forbidden / ForbiddenByRbac**. Hodnota nebyla zpřístupněna/vypsána/uložena. `.venv` současně nemá `azure.identity`; nic se neinstalovalo a CLI je pro tento audit dostupná alternativa. Backend ARM metadata obsahují AZURE_SQL_USER, nikoli AZURE_SQL_PASSWORD env položku; runtime credentials tím nejsou ověřené. Bez dalšího schválení neměnit RBAC, heslo, firewall ani deployment a nehledat heslo v image/logách.

**Odložená alternativa, nyní NEPROVÁDĚT:** přidělit aktuálně přihlášenému uživateli object ID `27b07391-a506-4e13-9246-145830460d50` roli `Key Vault Secrets User` jen na scope jediného Showcase SQL password secretu. Umožní číst toto existující heslo, nikoli jej měnit. Nenastavuje práva na JHU, jiné secrets ani roli pro správu vaultu. Platnost/existence hesla se ověří teprve po zpřístupnění.

```powershell
# AŽ PO VÝSLOVNÉM SCHVÁLENÍ UŽIVATELEM; nyní nespouštět.
az role assignment create --subscription 98c78b19-eb42-42b9-8582-46c983bb4687 --assignee-object-id 27b07391-a506-4e13-9246-145830460d50 --assignee-principal-type User --role "Key Vault Secrets User" --scope /subscriptions/98c78b19-eb42-42b9-8582-46c983bb4687/resourceGroups/ai-search-showcase-rg-dev/providers/Microsoft.KeyVault/vaults/showcase-ais-kv-dev/secrets/showcase-ai-search-sql-sqlaccount-password-dev --query "{id:id,scope:scope,roleDefinitionId:roleDefinitionId}" --output json --only-show-errors
```

Před případnou realizací ověřit existující přiřazení kvůli duplicitě, po ní zaznamenat ID pouze nově vytvořeného assignmentu. Odebrání tohoto konkrétního assignmentu po testech je navržený rollback, rovněž po souhlasu; nemažeme jiná existující oprávnění. Pokud aktuální identita nemá právo přiřazovat role, provede tento přesný schválený zásah správce. Alternativa bez změny Azure RBAC: člověk soukromě doplní ověřené SQL heslo do ignorovaného lokálního env, nikdy do chatu/Gitu. [Microsoft: RBAC role a jednotlivé secret scope](https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-guide).

Po vyřešení přístupu pokračovat pouze schváleným SELECT auditem. Nativní integrace s testovacími zápisy/migracemi nebo deployment jsou další odděleně schvalované kroky. Cloudová funkčnost exact/ANN dosud zůstává NEOVĚŘENÁ. Probuzení serverless compute bylo jediným provozním vedlejším účinkem čtecího připojení; žádné přepnutí tieru nebo změna dat se neprovedly.

**Tato část nahrazuje níže uvedený původní návrh nové prázdné DB. Nic nového zatím nezakládat.** Agent ověřil pouze ARM metadata přes Azure CLI, bez připojení k SQL datům, DDL/DML, deploymentu nebo změny kapacity:

| Položka | Skutečný stav |
|---|---|
| Subscription / resource group | `Microsoft Silver Partnership` / `ai-search-showcase-rg-dev` |
| SQL host / aplikační DB | `ai-search-showcase-sql-dev.database.windows.net` / `ai-search-showcase-sqldb-dev` |
| SQL region a SKU | West Europe; General Purpose serverless `GP_S_Gen5_1`, min 0,5 / max 1 vCore, 32 GiB storage limit |
| SQL stav | Paused; auto-pause 60 minut; metadata uvádějí earliestRestoreDate `2026-10-07T19:19:24.106307Z` (restore nebyl proveden/otestován) |
| SQL networking | publicNetworkAccess Enabled; min TLS 1.2; konkrétní přístup klienta dosud neověřen |
| Backend | `ai-search-showcase-ca-dev`, Running, CPU 0,25 / RAM 0,5 GiB, minReplicas 0 / maxReplicas 10 |
| Nasazený image | `aisearchshowcasecrdev.azurecr.io/ai-search-showcase-ca-dev:dev-v-20260903-142742`; latest ready revision `ai-search-showcase-ca-dev--0000002`; současné slicy v tomto image nejsou potvrzené |
| Backend config | APP_ENV `dev`, TENANT_ID `showcase-dev`, host/DB odpovídají výše; Driver 18 v cloud konfiguraci |
| Key Vault | `showcase-ais-kv-dev` existuje v North Europe; secrets/RBAC nebyly ověřeny ani vypsány |

Lokální tenant env obsahuje odlišné `AZURE_CONTAINER_APP_NAME=showcase-ai-search-ca-dev`; bez schválení jej neopravovat ani podle něj nenasazovat. Skutečná kapacita Showcase NEODPOVÍDÁ dosavadnímu cíli Basic5DTU / 0,5CPU / 1GiB. Correctness lze ověřovat na současném tieru; naměřené výkony se nesmějí označit za Basic5DTU acceptance. Případnou změnu tieru/runtime musí uživatel schválit zvlášť; nic automaticky nepřepínat.

### Původní plán SELECT auditu — již proveden přes Entra, viz aktuální výsledek výše

Připojit se k uvedené existující DB a provést pouze SELECT audit: compatibility/engine, seznam tabulek a sloupců, počty řádků (bez textů dokumentů a údajů uživatelů), případné profilové/ACL/native/FTS objekty a oprávnění účtu. Ověřit native VECTOR bez vytváření objektů, např. `SELECT VECTOR_DISTANCE('cosine', CAST('[1,0]' AS VECTOR(2)), CAST('[0,1]' AS VECTOR(2))) AS distance;`. Bez INSERT/UPDATE/DELETE/DDL, změn firewallu, modelových volání nebo deploymentu. Připojení již bylo zkuseno a probudilo DB, SELECTy však čekají na funkční autentizaci; viz výsledek výše.

Po auditu připravit konkrétní lokální úpravu harnessu/migračního postupu pro existující DB, seznam změn a návrat do funkčního Showcase stavu. Současné empty pytesty NAD TOUTO DB NESPOUŠTĚT: vyžadují `test` v názvu, prázdnou DB a při cleanup používají Base.metadata.drop_all. Souhlas s testovacím účelem Showcase tyto technické podmínky sám nemění. Každé vytvoření/smazání testovacích objektů, změna dat, migrace, backfill, build/deployment, oprava cloud konfigurace nebo změna SKU vyžaduje předchozí výslovné schválení konkrétního zásahu. Na konci ověřit funkční aplikaci, dokumenty/citace a uklizené testovací objekty; nemazat jiné tenanty ani zdroje.

## Goal

Ověřit skutečné exact a ANN SQL v existujícím Showcase, poté reprezentativní recall a výkon s přesně zaznamenaným skutečným tierem. Původní cíl Basic 5 DTU / backend 0,5 CPU / 1 GiB zůstává samostatnou neověřenou branou, dokud uživatel nepotvrdí cílovou kapacitu. Až po review a schválení aktivovat index/režim s návratem na stejnoprofilový exact. Bez výsledků nechat exact.

## Resources to create or modify

| Resource | Action | Suggested name | Required settings | Notes |
|---|---|---|---|---|
| Existing Showcase SQL DB | read-only audit, následné konkrétní změny jen po schválení | `ai-search-showcase-sqldb-dev` | aktuálně serverless, viz inventář výše | Empty fixture se musí přizpůsobit nebo nahradit; nevytvářet novou DB automaticky. |
| Benchmark corpus DB/index | připravit až po native integraci | `<representative-test-corpus>` | úplné profilové coverage, DiskANN ≥3, oprávnění a původ dat doložený | Může jít o nově naplněnou stejnou test DB po skončení empty fixture; další pytest cleanup už nad naplněnou DB nespouštět. |
| Backend test runtime | ověřit existující / vyhradit člověkem | `<confirmed-container-runtime>` | 0,5 CPU / 1 GiB a ověřená verze kódu | Workstation vůči vzdálené SQL není tento runtime. Kapacitu automaticky nezvyšovat. |
| Query dataset/cache/report | soukromě připravit | `.local/benchmarks/` / chráněný test storage | ≥100 různých neprázdných otázek + empty/ACL/metadata | Žádné privátní datasety/vectors/secrets do Gitu/image. |
| Search config | lidsky přepnout až po review | existující tenant | zachovat celý config, změnit vector_search_mode | Nový profil/logický index aktivovat explicitně až s úplným coverage. |

## Historická alternativa — nová prázdná test DB (nyní nezvolená)

Následující postup zůstává pouze jako alternativa pro případ, že uživatel později schválí samostatnou DB. Nejde o aktuální pokyn pro existující Showcase. Živý inventář a aktuální workflow výše mají přednost před níže uvedenými staršími konfiguračními hodnotami a pořadím.

Uživatel zvolil Showcase pro cloudovou verifikaci. Následující existující názvy jsou přečtené z lokální tenant konfigurace, nikoli potvrzené živým Azure inventářem:

| Položka | Konfigurovaná hodnota / návrh | Stav |
|---|---|---|
| Tenant aplikace | `showcase-dev` | konfigurace |
| Resource group | `ai-search-showcase-rg-dev` | potvrdit v Azure |
| SQL server / host | `ai-search-showcase-sql-dev` / `ai-search-showcase-sql-dev.database.windows.net` | potvrdit v Azure |
| Existující aplikační DB | `ai-search-showcase-sqldb-dev` | nepoužít pro empty pytest fixture |
| Nová samostatná integrační DB | `ai-search-showcase-vector-test-dev` | navržený název, vytvoří člověk |
| Backend | `showcase-ai-search-ca-dev` | konfigurace; starší zářijový handoff uvádí odlišné jméno `ai-search-showcase-ca-dev`, potvrdit aktuální zdroj |
| Key Vault | `showcase-ais-kv-dev` | konfigurace; starší KV handoff stále čeká na potvrzení |

### 1. Potvrzení zdrojů a vytvoření prázdné DB člověkem

V Azure Portálu otevřít správnou subscription → `ai-search-showcase-rg-dev` → SQL server `ai-search-showcase-sql-dev` → vytvořit **SQL database** `ai-search-showcase-vector-test-dev`, **Blank database**, DTU **Basic / 5 DTU**. Nevybírat sample data, restore ani kopii aplikační DB. Jde o další účtovanou databázi na existujícím serveru, nikoli nový server. Neměnit kapacitu existující DB nebo backendu. Dostupnost nativních funkcí na tomto skutečném cíli musí potvrdit test, ne pouze volba SKU.

Pro první běh z VS Code musí SQL networking umožnit přístup z aktuální klientské veřejné IP na port 1433, případně existující schválenou privátní cestou. Pro veřejný endpoint povolit konkrétní klientskou IP, nikoli libovolné adresy. Testovací SQL účet musí v této test DB umět CREATE TABLE, ALTER/index DDL, REFERENCES, SELECT a DML; např. databázový vlastník pouze pro tento izolovaný test. SQL credentials uložit soukromě, neposílat do chatu. Aktuální fixture používá SQL uživatele/heslo; `APP_ENV=test` automaticky nenačítá Key Vault.

Volitelné read-only potvrzení po přihlášení do správné subscription (žádné secret hodnoty):

```powershell
az sql db list --resource-group ai-search-showcase-rg-dev --server ai-search-showcase-sql-dev --query "[].{name:name,status:status,tier:sku.tier,capacity:sku.capacity}" --output table
az containerapp show --resource-group ai-search-showcase-rg-dev --name showcase-ai-search-ca-dev --query "{name:name,location:location,containers:properties.template.containers[].{name:name,image:image,resources:resources},scale:properties.template.scale}" --output json
```

### 2. Soukromá konfigurace integračních testů

V kořeni repozitáře ručně vytvořit ignorovaný `.env.native-test`. Následující obsah je šablona; placeholdery SQL účtu/hesla doplnit pouze do tohoto soukromého souboru. Lokálně je k 2026-10-14 dostupný **ODBC Driver 17**, nikoli 18; test nemá automatický driver fallback. Zde proto použít skutečně instalovaný Driver 17. Tenant/cloud konfiguraci s Driver 18 neměnit. TLS v testu zůstává `Encrypt=yes;TrustServerCertificate=no`.

```dotenv
APP_ENV=test
DATABASE_BACKEND=azure_sql
AZURE_SQL_HOST=ai-search-showcase-sql-dev.database.windows.net
AZURE_SQL_PORT=1433
AZURE_SQL_DB=ai-search-showcase-vector-test-dev
AZURE_SQL_USER=<testovaci-SQL-ucet>
AZURE_SQL_PASSWORD="<soukrome-heslo>"
AZURE_SQL_DRIVER=ODBC Driver 17 for SQL Server
```

Ověřit ignorování příkazem `git check-ignore .env.native-test`. Soubor je také vyloučen z Docker build contextu. `.env.local` ani tenant `.env.dev` kvůli tomuto testu nepřepisovat. Nový terminál musí být bez dříve exportovaných `AZURE_SQL_*` hodnot, které mají přednost před env souborem; lze je odebrat **pouze z aktuálního procesu terminálu**:

```powershell
Get-ChildItem Env:AZURE_SQL_* | ForEach-Object { Remove-Item -LiteralPath ("Env:" + $_.Name) }
Remove-Item Env:RUN_LOCAL_SQL_TESTS -ErrorAction SilentlyContinue
$env:RUN_NATIVE_SQL_TESTS = "1"
$env:RUN_NATIVE_ANN_TESTS = "1"
$env:NATIVE_SQL_EXPECT_HOST = "ai-search-showcase-sql-dev.database.windows.net"
$env:NATIVE_SQL_EXPECT_DB = "ai-search-showcase-vector-test-dev"
try {
    .venv\Scripts\python.exe -m pytest tests/test_vector_store.py tests/test_ann_search.py -k "native_vector_end_to_end or native_ann_filters" -q --tb=short
} finally {
    Remove-Item Env:RUN_NATIVE_SQL_TESTS -ErrorAction SilentlyContinue
    Remove-Item Env:RUN_NATIVE_ANN_TESTS -ErrorAction SilentlyContinue
    Remove-Item Env:NATIVE_SQL_EXPECT_HOST -ErrorAction SilentlyContinue
    Remove-Item Env:NATIVE_SQL_EXPECT_DB -ErrorAction SilentlyContinue
}
```

Příkaz použít až po potvrzení skutečně prázdné test DB a odpovídajících jmen. Očekáváme dva provedené native testy, nikoli dva skipped. Fixture vytváří syntetické tenanty `alpha`/`beta` a embeddingy přímo v testu: ověřuje Showcase **infrastrukturu**, zatím nikoli Showcase aplikační účty, model nebo dokumenty. Vytvoří a odstraní své tabulky, samotnou Azure databázi nemaže. Nepotřebuje nový model, Blob Storage, Key Vault setup ani deployment aplikace. Při selhání vrátit redigovaný výpis; pokud po neúplném cleanup zůstanou tabulky, před dalším během je ručně prověřit v této vyhrazené DB, nepouštět bezhlavé mazání.

Microsoft aktuálně uvádí vector index / VECTOR_SEARCH jako GA v Azure SQL Database; PREVIEW_FEATURES je požadavek SQL Serveru 2025, ne tohoto Azure cíle. Nadále ověřujeme skutečnou verzi indexu ≥3 a jeho prefiltry/DML testem. [CREATE VECTOR INDEX — dostupnost, verze a nejméně 100 řádků](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-vector-index-transact-sql?view=sql-server-ver17).

### 3. Co vrátit po první bráně a co následuje

Vrátit pouze potvrzený host/test DB, region, Basic/5 DTU, použitý ODBC driver a souhrn obou pytestů nebo redigovanou chybu. Až pak připravit v testovacím cíli Showcase korpus s úplnými profilovými embeddingy, skutečné serverové uživatele/skupiny a reprezentativní dataset. Stejnou nyní prázdnou DB lze po testech naplnit; potom nad ní empty fixture již nespouštět.

Pro benchmark je potřeba ≥100 různých otázek s neprázdnou referencí plus okrajové případy, ≥100 platných vektorů pro vytvoření DiskANN a dostatečně velký korpus pro případ za původní hranicí 600. Měření provést v potvrzeném backendovém runtime 0,5 CPU / 1 GiB s aktuálním kódem a konfigurací test DB. Běžící Showcase app přesměrovat jen po domluveném maintenance okně; pro paralelní provoz vyhradit testovací runtime. Nevyhodnocovat notebook → Azure SQL jako Container App p95. Migrace stávajícího korpusu, nasazení, aktivace ANN a cloudové účty/Key Vault jsou až další lidsky potvrzené kroky podle zbytku tohoto handoffu.

## Required app configuration keys (společné pro další fázi)

Používají se existující AZURE_SQL_HOST/DB/PORT/USER/PASSWORD/DRIVER, aktuální profilové/provider klíče a search JSON z předchozích sliců. Nové tenant env klíče nejsou potřeba. SQL heslo a modelové credentials zůstávají v Key Vaultu nebo ignorovaných env souborech. `prepare` může volat současný embedding provider; `run` žádné modely nevolá.

## Human-completed values

Vrátit jen non-secret: test SQL host/DB/port, region, engine/SKU a potvrzení 5 DTU, runtime CPU/RAM/OS/Python a worker count, auth/ODBC driver, native exact/ANN test summary, index UUID/profil/verze/metrika/enabled, dataset/cache/corpus fingerprint, použitou retrieval konfiguraci a benchmark report. Přidat potvrzení runtime permissions, skutečného cold startu/HTTP kontrol a zastavení writerů po dobu validovaného běhu. Nikdy sem nevkládat tokeny, hesla, embeddingové cache nebo soukromé otázky.

## Secrets that must exist but must not be pasted here

Stávající SQL credentials nebo managed identity oprávnění a stávající embedding provider credentials pro přípravu query cache. Odpovědní model není pro benchmark potřeba. Dataset uživatelé musí existovat ve správném tenantu a mít skutečné serverové skupiny; nespoléhat na demo/cloud self-registration účty.

## Validation steps for human

1. Dokončit předchozí schema/ACL/Unicode/profilové handoffy a nativní exact+ANN pytesty podle `docs/development/search-slice-4-testing.md`. Fixture musí začínat na prázdné samostatné DB; na naplněném benchmark korpusu ji nespouštět.
2. Připravit reprezentativní test korpus a explicitní profilový index/backfill podle slice 3. Neznámé historické vektory nekopírovat pouze podle dnešní konfigurace; standardně `--reembed` přes doložený provider. Nový index nemusí být aktivní: benchmark podporuje `--index <UUID>`. DiskANN vytvořit explicitně podle slice 4, úplná coverage a ≥100 platných vektorů, verze ≥3. Texty/ACL se kvůli jinému modelu neduplikují.
3. Připravit soukromý dataset ≥100 různých otázek s neprázdnou exact referencí a navíc empty, <K, selective metadata a více skutečných ACL subjectů (`user_id` v case). Zahrnout relevantní výsledek za původním limitem 600 v dostatečně velkém korpusu. Duplicity query/filter/subject jsou odmítané. Osm Aurora otázek ani opakování jedné otázky nejsou quality eval.
4. V potvrzeném kontextu spustit `benchmark_search.py prepare` s novým cache output, stejným datasetem, explicitním profilem/indexem a --expect-host/db/tenant. Cache příprava není měření; vzniklé soubory ukládat soukromě. Běžné runtime nastavení providera neměnit kvůli experimentálnímu modelu; případné odlišné bindingy nastavit jen procesu benchmarku/test prostředí.
5. Zastavit ingestující writery, konfiguraci i DDL. V cílovém runtime spustit `run --compare-ann --requests 200 --require-gates` podle návodu slice 5, s cache, datasetem, user-id, indexem a potvrzeným targetem. Měří se session/identity/config-load/preflight/retrieval/fusion/expansion uvnitř procesu na jednom event loop, včetně per-request Blob config I/O; HTTP/JWT jsou mimo tuto metriku. Ověřit config_load_included=true. Změna retrieval konfigurace během běhu se odmítne. Současný Docker spouští jeden uvicorn proces; ověřit skutečnou deployment konfiguraci a vliv souběžného app provozu, benchmark neduplikovat přes více kontejnerů/modelů najednou.
6. Vrátit report: mean recall@30 ≥95 % na ≥100 neprázdných různých otázkách, rozpad selektivity, nulové chyby, stabilní coverage/hash, ANN p95 ≤1000 ms při concurrency 1 i 3 s ≥200 requesty každé varianty. Přezkoumat i runtime query plans a exact referenci. Exit 3 znamená nesplněné brány, report přesto existuje; timeout nepovoluje automatický scan ani navýšení kapacity.
7. Samostatně změřit skutečný restart/first-request chování cílové aplikace a HTTP smoke. Nástroj má cold_start_measured=false: jeho první request už následuje po DB preflight/snapshotu. Nelze z něj odvodit app/SQL cold start ani celkovou chatovou latenci bez zvláštního měření. Metadata chatového retrievalu rozlišují časy modelů a retrievalu, ale preflight je před embeddingem; při ručním měření jej zohlednit.
8. Teprve po lidském review případně aktivovat nový kompletní index přes existující coverage-checked CLI se zastavenými writery a zachováním starého indexu. Management načte celou aktuální search konfiguraci přes GET /api/chat/config, zachová pole odpovídající změřenému reportu a POSTem přepne vector_search_mode na ann. Stejný profil/provider binding musí odpovídat indexu, jinak endpoint bezpečně odmítne. Při jiném profilu coordinačně změnit binding backendu a aktivaci v maintenance okně, bez nahrazování jiným modelem stejného rozměru.

## Validation steps for agent after completion

Přečíst non-secret výsledky, ověřit dataset/cache/profile/index/coverage shodu, skutečný service tier/runtime, native testy, ACL/plány, oba load scénáře a cold start. Nepřekládat lokální/mock výsledky do Azure acceptance. Report je pouze podklad pro review; lokální nástroj nemá právo sám nastavit cloud acceptance.

## Rollback

Při problému Management uloží stejnou celou konfiguraci s vector_search_mode=exact přes config API, které synchronizuje používanou Blob konfiguraci. Native tabulka/profil zůstávají stejné a reembedding není potřeba. Pro návrat na předchozí logický index ověřit coverage aktuálních chunků a kompatibilní provider binding, stopnout writery a explicitně aktivovat starý index. Žádný automatický fallback na legacy JSON nebo jiný model. Nemažeme předchozí indexy ani Azure zdroje.

## Open issues

- [x] Native exact/ANN funkční scénáře skutečně prošly na schváleném izolovaném Showcase schématu; nová prázdná DB nebyla potřeba, vlastní objekty uklizeny.
- [ ] Běžná Showcase app dbo schema/ACL/Unicode/profile migrace/backfill a matching deployment/runtime identity/API/PDF smoke čekají na konkrétní schválení.
- [ ] Reprezentativní ≥100-query workload s oprávněními a velkým korpusem chybí.
- [ ] Skutečný Basic 5 DTU / Container App benchmark, cold start/HTTP review a aktivace neprovedeny.
- [ ] SQL Server 2025 Docker zůstává volitelný navržený lokální mezikrok; není instalovaný a nenahrazuje cílový runtime.
