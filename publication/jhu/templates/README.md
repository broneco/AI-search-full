# JHU AI Search

Vyhledávání v dokumentech pro Jihočeskou univerzitu s odpověďmi s citacemi a PDF náhledy. FastAPI backend a dva Next.js frontendy používají Azure SQL, Blob Storage a Azure OpenAI. Lokální prostředí používá SQL Server v Dockeru; AI modely se zatím volají přes Azure.

Zdrojová verze: **@@VERSION@@**. Tento repozitář obsahuje samostatný výchozí snapshot a následná předání. Původní Git historie, pracovní archivy ani provozní deníky nejsou součástí předání.

Jediný přibalený tenant je `jhu`. Jeho search/classification konfigurace jsou přímo v tenants/jhu, bez potřeby tenants/default. Lokální identita je `jhu`; cloudový korpus používá přesné `ju-prod`. Alias mění pouze adresář konfigurace, nikoli data nebo oprávnění. Privátní env a vlastní dokumenty se předávají odděleně bezpečnou cestou.

[Architektura](docs/architecture/search.md) · [Testování](docs/development/testing.md) · [Nasazení](docs/deployment.md) · [Aktualizace](docs/updates.md) · [Mapa](docs/navigation_guide.md)

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

Jména deploymentů musí odpovídat tvému Azure prostředí. Lokální databáze nahrazuje cloudovou SQL databázi; modelové volání zatím stále používá Azure. Bez modelového připojení lze spustit API/UI a izolované testy, ale nelze vyhledávat ani generovat skutečné odpovědi. `.env.local` necommituj.

### Každodenní spuštění a restart počítače

Ve VS Code zvol **Terminal → Run Task… → AI Search: start local app**. Úloha spustí SQL Server, backend a uživatelský frontend. Ručně použij následující příkazy, backend a frontend každý ve vlastním terminálu:

```powershell
# Terminál 1: databáze a backend
.\dev.ps1 -Action start-db
.\dev.ps1 -Action backend
```

```powershell
# Terminál 2: uživatelská aplikace
npm --prefix frontend-user run dev -- --hostname 127.0.0.1 --port 3000
```

```powershell
# Terminál 3: volitelná administrace
npm --prefix frontend-admin run dev -- --hostname 127.0.0.1 --port 3001
```

| Služba | Adresa |
|---|---|
| Uživatelská aplikace | http://localhost:3000 |
| Administrace | http://localhost:3001 |
| API / Swagger | http://localhost:8000/docs |

Lokální prázdná databáze vytvoří demo účty: `user@jcu.cz` / `password123` a `admin@jcu.cz` / `DolphinAdmin26`. Platí pouze pro local/test; cloud demo účty automaticky nevytváří. Pokud už databáze uživatele obsahuje, použij existující přihlášení.

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

Stejný příkaz nabízí VS Code úloha **AI Search: run isolated tests**. Pro lokální SQL regrese spusť v samostatném terminálu:

```powershell
.\dev.ps1 -Action start-db
$env:RUN_LOCAL_SQL_TESTS = "1"
.\dev.ps1 -Action test
Remove-Item Env:RUN_LOCAL_SQL_TESTS
```

SQL testy vytvářejí vlastní testovací databáze a nepracují nad aplikační `ai_search_local`. SQL Server 2022 lokálně neověřuje nativní Azure VECTOR/DiskANN ani cloudový fulltext. Skips u nepovolených integračních testů jsou očekávané. Podrobnosti: [testování](docs/development/testing.md).

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
.venv\Scripts\python.exe ask.py --email user@jcu.cz "Kolik pokusů mám na zkoušku?"
```

Pro kontrolu obou frontendů bez nasazení:

```powershell
npm --prefix frontend-user run build
npm --prefix frontend-admin run build
```


## Deployment do Azure

Pro existující prostředí začni čtecím plánem `./deploy_backend.ps1 -Client jhu -Environment prod`. Backend, frontendy, databázové migrace a aktivace indexu jsou oddělené kroky. Zápisy vyžadují explicitní Apply a ověřený cíl; podrobné příkazy jsou v [návodu nasazení](docs/deployment.md).

## Struktura

- app/: API, retrieval, modeloví provideři, ingestace a repository.
- frontend-user/ a frontend-admin/: uživatelská aplikace a administrace.
- tenants/jhu/: veřejná konfigurace a branding JHU.
- tests/ a fixtures/: automatizované testy a dvě fiktivní univerzitní PDF.
- docs/: aktuální návody a popis architektury.
- .agents/: instrukce a aktuální paměť pro další AI práci.
- infra/: provisioning šablony; neslouží jako ověřený release postup.

Kořenové Python/PowerShell skripty zůstávají přímo spustitelné. Env, data, Docker volume, dependency instalace a privátní zálohy nejsou určené k automatickému mazání.
