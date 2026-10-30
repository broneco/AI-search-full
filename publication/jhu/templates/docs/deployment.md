# Nasazení existujícího JHU prostředí


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

Cloudové prompty, search/chunkování a klasifikace nově používají SQL `tenant_settings`. Před prvním nasazením této verze proveď explicitní zachycení současných souborových/Blob nastavení a guarded insert-only import: [postup aktualizace](development/non-destructive-updates.md). `migrate_tenant_settings.py` standardně pouze plánuje; cloudový startup tabulku nevytváří. SQL převod ani jeho cloudová akceptace nejsou součástí publikace zdrojů.

| Skript / dokument | Použití |
|---|---|
| `migrate_search_schema.py` | Explicitní tenant/Unicode/FTS migrace pro potvrzený cíl |
| `migrate_search_acl.py` | Audit a doplnění relačních dokumentových/chunkových ACL |
| `migrate_search_vectors.py` | Audit, profilové tabulky, backfill, aktivace indexu a volitelné vytvoření DiskANN |
| `benchmark_search.py` | Příprava query cache a exact/ANN benchmark; bez automatické aktivace |

Výchozí režim je `exact`. DiskANN je volitelný a vyžaduje samostatné ověření kvality a výkonu; vytvoření indexu nezapíná ANN.

`deploy_all.ps1` je blokovaný. `reset_users_db.py` je destruktivní údržba účtů a historie. Provisioning pod infra/ není součástí běžného release; main.bicepparam má nevyřešený nesoulad se šablonou. Pro existující prostředí používej oddělené backend/frontend skripty.

Full-refresh je samostatná údržba. Výchozí spuštění jen ověří zdroje a vypíše plán; přesný tenant musí odpovídat již nakonfigurovanému `TENANT_ID`:

```powershell
.venv\Scripts\python.exe full_refresh_ingest.py --tenant ju-prod --data-dir "<zdrojové PDF/TXT>"
```

Zápis vyžaduje `--apply --expect-tenant ju-prod`, v cloudu také `--expect-host "<ověřený host>" --expect-db "<ověřená DB>"`. Dokumenty se nahrazují jednotlivě až po přípravě embeddingů. Původní nepoužité dokumenty se odstraní až po úspěšném zpracování všech vstupů; při pozdější chybě mohou zůstat úspěšné náhrady, zbytek se nepromaže. Nové souběžné uploady a změněné stale řádky jsou chráněné. Automatický scan sdíleného kořene `data/` se nepoužívá; API full-refresh potřebuje tenantí podadresář, jinak bezpečně skončí chybou. Fast reindexace zpracovává pouze dokumenty přesného přihlášeného tenantu.


## Ověření po release

Ověř připravenou revizi a verzi, přihlášení, dotaz s citacemi, načtení PDF a izolaci oprávnění. Backend image a obě SWA se vydávají samostatně. Pro návrat zachovej předchozí image; rollback aplikace nenahrazuje rollback schématu nebo bezpečný návrat heslových hashů.

Přihlašovací údaje nevkládej do commitů ani logů. Backend může používat managed identity/Key Vault podle existující konfigurace; změny RBAC, kapacity, klíčů a databáze vyžadují vlastní schválený postup. Běžná publikace zdrojů do Forgejo Azure nemění.

## JHU sidecar připojení

Pro dvoukontejnerovou variantu používej [cloudový runbook](development/jhu-sidecar-azure.md) a `deploy_jhu_sidecar.py`, standardně read-only. Běžný `deploy_backend.ps1` zůstává single-container image releasem. Azure aktivaci, dvě nové KV reference, kapacitu, migrace a SWA rollout proveď podle samostatně schváleného plánu. JHU MI/VPN/modelová funkční akceptace prošla. Otevřený zůstává Management vector/hybrid SQL timeout10s; explicitní keyword funguje. Další rollout ověřte nezávisle, neodvozujte jej ze zdrojového snapshotu.
