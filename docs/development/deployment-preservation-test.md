# Test zachování dat při nasazení

`verify_deployment.py` pořídí read-only checkpoint před a po výměně image. Porovnání probíhá offline; nástroj nenasazuje, nemigruje, neaktivuje indexy a neopravuje data. Úspěšné porovnání je důkaz zachování zachyceného stavu, nikoli samo o sobě důkaz funkčnosti loginu/RAG, obnovitelnosti zálohy či bezpečnosti budoucích migrací.

## Co se porovnává

- Celé řádky účtů včetně heslových hashů a skupin, konverzací, zpráv, dokumentů, chunků a obou relačních ACL projekcí.
- Všechny indexy přesného tenantu, jejich neměnné profily, aktivní index a každá profilová vektorová tabulka včetně hodnot vektorů a revizí vstupu. Cizí vektor v tenantové tabulce je chyba.
- SQL prompty CS/EN, nastavení vyhledávání/chunkování/shrnutí a klasifikace, modelové registrace, publikace, oprávnění, popisy a limity.
- Otisky identity, SQL/Storage připojení a podpisových/legacy klíčů. APP_VERSION, revize a replika se evidují odděleně; nová verze není změnou chráněného stavu.
- S `--blobs` se přímo z nakonfigurovaného Blob úložiště postupně čtou a hashují všechny přesně odkazované originály. Cache, podobnost názvů ani lokální soubory se nepoužijí. Neexistující/nepřístupný soubor nebo zdroj mimo tenantový kontejner ukončí capture chybou. Bez přepínače je výsledek výslovně SQL-only (`blobs_checked: false`).

Manifest obsahuje pouze počty a SHA-256 otisky, indexová UUID/modely a provozní metadata. Neobsahuje texty dokumentů/zpráv/promptů, e-maily, heslové hashe, vektory ani credentials. Přesto je to interní provozní artefakt: ukládej ho soukromě mimo Git, například pod `.local/deployment-check/`. Není to záloha a nelze z něj obnovit data. SQL Server počítá řádkové otisky server-side; SQLite je izolovaná testovací reference.

## Podmínky akceptace

1. Připrav přesný obraz k nasazení a rollback; ověř subscription/directory, SQL host/DB, přesný tenant, existující ACA/SWA a beze změny kapacit/klíčů. Nasazení potřebuje vlastní autorizaci. Běžný release nepouští migrace, ingestaci ani backfill.
2. Po dobu obou checkpointů a nasazení zastav editace/ingestaci/chatové zápisy. Capture používá jednu SERIALIZABLE čtecí transakci a 30s limit SQL statementu; během čtení může blokovat souběžné zápisy. Čtení Blobů může trvat déle a má běžné náklady na čtení/přenos. Snapshot není distribuovanou transakcí mezi SQL a Blob; dodržení klidu zápisů je nutné.
3. Před nasazením musí požadované indexy mít úplné neprázdné pokrytí a existovat aktivní tenantový index. `--require-settings` vyžaduje všechny tři skutečné SQL overrides; fallback na image default neprojde jako zachované vlastní nastavení.
4. Po nasazení zachyť druhý manifest, stále před funkčními testy vytvářejícími zprávy. Striktní porovnání nepovoluje ani přidané řádky. Legitimizovat změnu jen shodným počtem není možné.
5. Samostatně proveď login původního účtu a původní skupiny, otevření původní konverzace/PDF, přečtení vlastních nastavení z API i synchronního loaderu, JHU readiness a citovaný dotaz přes každý index se správnou provenance. Eviduj vlastní testovací zápisy odděleně a ověř běžného Usera i Management hranici. Stejný text generované odpovědi není podmínkou zachování dat.

## Checkpoint v běžícím kontejneru

V shellu backendu `/app` použij skutečný ověřený cíl. Očekávané hodnoty se kontrolují před otevřením SQL spojení; nenastavují konfiguraci a nezmění cíl.

```sh
python verify_deployment.py capture --output /tmp/before.json \
  --expect-host <overeny-host> --expect-db <overena-db> --expect-tenant <presny-tenant> \
  --require-index <azure-uuid> --require-index <nomic-uuid> --require-settings --blobs
```

Existující soubor se nikdy nepřepisuje. Ještě před zastavením kontejneru ulož celý JSON do soukromého trvalého umístění mimo kontejner. `/tmp` ani `/app` nepřežívají výměnu image. Po nasazení vytvoř analogicky `after.json` a také ho ulož mimo kontejner. Capture nemá průběhové zprávy; při chybě nevypíše úspěšný checkpoint a vrátí exit 2. Dočasné artefakty neukládej mezi originály dokumentů.

Pokud stará image tento nový nástroj ještě neobsahuje, v lokálním PowerShellu v kořeni checkoutu vytvoř veřejný samostatný konzolový příkaz:

```powershell
.venv\Scripts\python.exe verify_deployment.py console-script `
  --expect-host <overeny-host> --expect-db <overena-db> --expect-tenant <presny-tenant> `
  --require-index <azure-uuid> --require-index <nomic-uuid> --require-settings --blobs
```

Celý výstup (od `cd /app` po poslední `DEPLOYMENT_AUDIT_PY`) vlož do shellu stávajícího backendového kontejneru. Obsahuje pouze komprimovaný veřejný skript a ne-secret argumenty, žádné místní env ani credentials. Použije prostředí a knihovny existujícího kontejneru, nezapisuje do image a vypíše jediný JSON checkpoint. Stejný konzolový příkaz použij před i po nasazení, aby formát otisků zůstal stejný. Výstup každého běhu ulož jako `before.json`/`after.json` mimo kontejner.

## Offline vyhodnocení

V lokálním PowerShellu; nepotřebuje Azure, VPN, secrets ani databázové spojení:

```powershell
.venv\Scripts\python.exe verify_deployment.py compare `
  --before .local/deployment-check/before.json `
  --after .local/deployment-check/after.json --require-new-revision
```

Exit 0: `state_preserved: true`, shodné všechny chráněné otisky a doložená jiná neprázdná ACA revize. Pro úplnou Blob kontrolu musí být také `blobs_checked: true`. Exit 1: rozdíl/nezjištěná nová revize; `changes` obsahuje jen názvy oblastí/tabulek. Exit 2: neplatný/neúplný manifest, jiný cíl nebo technická chyba. Neinterpretuj chybu jako úspěšné zachování. Ruční editace manifestů ruší důkaz; soubory nejsou kryptograficky podepsané a mají sloužit důvěryhodnému operátorovi.

Při rozdílu neprováděj automatický reset, import výchozích nastavení nebo reembedding. Zachovej oba manifesty a runtime image, zjisti konkrétní příčinu. Aplikační rollback na předchozí immutable image je oddělený od obnovy databáze; produkční DB nepřepisuj zálohou bez samostatného ověřeného plánu.

## Izolované ověření nástroje

```powershell
.venv\Scripts\python.exe -m pytest tests/test_deployment_preservation.py tests/test_tenant_settings.py -q
```

Pro skutečný lokální SQL Server přidej explicitně `RUN_LOCAL_SQL_TESTS=1`. Test používá vlastní jedinečnou dočasnou DB; nikdy neprodukční data. SQL Server 2022 prokazuje řádkové hashování a scope, nikoli Azure native VECTOR. Nativní SQL má kompilační regresi; skutečný JHU native/Blob/redeploy důkaz vzniká až samostatným provedením výše.
