# Lokální vývoj AI Search

## Požadavky

- Windows, VS Code a otevřený kořenový adresář tohoto repozitáře.
- Docker Desktop nebo Rancher Desktop spuštěný s Linux kontejnery; databáze běží v lokálním SQL Server Developer kontejneru.
- Python 3.12, lokální ODBC ovladač pro SQL Server 17 nebo 18 a Node.js/npm.
- Python závislosti v `.venv` a npm závislosti v `frontend-user/node_modules`.

SQL Server vyžaduje x64 systém a nejméně 2 GB paměti; pro běh databáze spolu s backendem a frontendem rezervuj Dockeru alespoň 4 GB. Podrobnosti uvádí [Microsoft SQL Server on Linux requirements](https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-setup?view=sql-server-ver17).

## První spuštění

V kořeni repozitáře spusť jednou v terminálu:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location frontend-user
npm ci
Set-Location ..
```

Ve VS Code nejprve spusť Rancher Desktop a počkej, až Docker Engine oznámí, že je připravený. Potom otevři **Terminal → Run Task… → AI Search: start local app**. Úloha vytvoří ignorovaný `.env.local` s náhodným lokálním heslem, spustí SQL Server a potom backend a uživatelský frontend. Po dokončení jsou aplikace dostupné na `http://localhost:3000` a `http://localhost:8000/docs`. Pokud úloha oznámí, že Docker Engine není dostupný, zkontroluj stav Rancher Desktopu a že používá Docker/Moby engine.

Při prvním spuštění Docker stáhne obraz SQL Serveru. Databázi `ai_search_local` a tabulky vytvoří backend. SQL data leží v pojmenovaném Docker volume, takže přežijí restart počítače i zastavení kontejneru. Po restartu počítače spusť Docker Desktop a znovu spusť stejnou VS Code úlohu.

## Automatické ukázkové dokumenty

Při spuštění backendu přes `./dev.ps1 -Action backend` nebo VS Code úlohu se do `ai_search_local` doplní dva jednostránkové české PDF o **fiktivní Vysoké škole Aurora**: Organizace studia a Služby pro studenty. Originály jsou verzované v `fixtures/local-university/`, pracovní kopie jsou v ignorovaném `data/local-demo/`. Ukázky mají přístup skupiny User, takže je vidí běžný demo účet. Vymyšlené informace jsou označené přímo v dokumentech.

Pokud v `.env.local` máš `AZURE_OPENAI_ENDPOINT` a `AZURE_OPENAI_API_KEY`, první start vytvoří skutečné embeddingy přes aktuální nakonfigurovaný provider v dokumentovém režimu. Bez těchto hodnot backend vypíše varování „Lokální demo čeká na…“; doplň ignorovaný soubor a restartuj backend. Náhodné vektory se nepoužívají. Pro odpověď chatu je potřeba také funkční chatové deployment nastavení.

Úspěšný start oznámí `Lokální demo Aurora: 2 dokumenty připravené, 2 nově indexováno.` Další start oznámí `0 nově indexováno.` Nezměněné embeddingy nepřepočítává; smazanou ukázku obnoví a změnu embeddingového profilu rozpozná i při stejném rozměru. Vlastní nahrané dokumenty nemaže. Databáze i ukázky přežijí restart počítače.

V uživatelském frontendu založ nový chat a vyzkoušej:

| Otázka | Očekávaná informace |
| --- | --- |
| Kolik kreditů potřebuji pro postup do druhého ročníku? | Alespoň 40 kreditů za první rok. |
| Kolik pokusů mám na zkoušku? | Jeden řádný a dva opravné pokusy. |
| Kdy má studijní oddělení úřední hodiny? | Pondělí a středa, 8:30–11:30. |
| Do kdy se podává přihláška na Erasmus? | Do 15. března. |

Otevři citaci a ověř načtení příslušného PDF a čitelnost češtiny. Pokud se seznam dokumentů po restartu neobnoví sám, obnov stránku frontendu.

Startup lokálního SQL také převede existující názvy dokumentů/konverzací a texty chunků/zpráv na Unicode sloupce. Neobnoví znaky ztracené starým VARCHAR uložením; staré postižené dokumenty znovu nahraj z originálu. Azure sloupce startup nemění. Aktuální lokální Docker image nemá nainstalované SQL Full-Text Search; jeho inicializační warning neblokuje současnou keyword větev, která používá SQL LIKE a výpočet ranku. Není to příčina původní chyby 500.

## Zastavení a testy

Backendový autoreload v `dev.ps1` sleduje pouze `app/`. Změny testů, `.local/` a vygenerovaných kopií projektu jej nespouštějí znovu; při změně startovacího příkazu ukonči starý backend přes Ctrl+C a spusť jej znovu. Přepnutí modelu/indexu tím není dotčené.

Pytest bez dalších přepínačů ukládá pracovní data pod `.local/tmp/pytest/`, do samostatných číslovaných adresářů se zámkem aktivní relace. Nastavení uchovává tři poslední běhy, cache zůstává v `.local/pytest-cache/`. Operátor může umístění explicitně přepsat pomocí `PYTEST_DEBUG_TEMPROOT` nebo `--basetemp`; při běžném spouštění je nepoužívej. Pevný `--basetemp` pytest před použitím maže, proto jej nesdílej mezi běhy ani nesměřuj na uživatelské soubory.

Slice 3 přidává profilový katalog a úplné přesné hledání. U starších neoznačených dat je nutný jednorázový explicitní backfill; postup, kontrola pokrytí a aktivace jsou v [návodu slice 3](search-slice-3-testing.md). Nový lokální start připraví profilový index pro dokumenty Aurora; pokrytí závisí na aktuálním korpusu a nemá pevný počet chunků. Lokální SQL Server 2022 používá streamovanou JSON referenci; Azure native VECTOR se ověřuje samostatně.

Pro opakovatelnou lokální kontrolu latence bez generování odpovědí použij [benchmark slice 5](search-slice-5-testing.md). `prepare` jednou vytvoří cache osmi otázek přes aktuální embedding provider; `run` používá tuto cache a potřebuje jen SQL DB, ne běžící FE/BE ani modelová volání. Konkrétní příkazy a interpretace blokované ANN brány jsou v návodu.

Varování `daemon is not using the default seccomp profile` z Rancher Desktopu samo o sobě neznamená selhání Engine. Skript vyhodnocuje návratový kód Docker procesu, protože Windows PowerShell 5.1 jinak může stderr varování považovat za chybu. Stejné zpracování platí i pro Compose při stahování a spouštění kontejneru.

Ukonči běžící frontend a backend přes terminály jejich VS Code úloh (Ctrl+C). Databázi můžeš zastavit úlohou **AI Search: stop local database**; kontejner lze později znovu spustit se zachovanými daty. Tato úloha databázový volume nemaže.

Úloha **AI Search: run isolated tests** nastaví `APP_ENV=test`, vynechá tenantí cloud `.env` soubory a spustí pytest. Běžné testy používají izolovanou SQLite fixture; nepotřebují Docker SQL Server ani Azure databázi. Tenantí JSON overlay používá vlastní dočasný adresář každého pytest běhu, aby nepřebíral změny z minulých testů. Lokální SQL Server testy a reálné Azure modelové testy se povolují samostatnými opt-in příznaky; postup pro ACL slice popisuje [ověření slice 2](search-slice-2-testing.md).

## Konfigurace a limity

`APP_ENV` určuje režim spuštění a `DATABASE_BACKEND` určuje databázi samostatně. Režimy `local` a `test` načítají jen `.env.local` nebo `.env.test`; nenačítají tenantí cloud nastavení a nevolají Key Vault. Výchozí `dev`/`prod` nadále používají stávající tenantí konfiguraci a Azure SQL.

Lokální uživatelské rozhraní a API lze spustit bez Azure přihlašovacích údajů. Vyhledávání, ingestace a odpovědi vyžadují nakonfigurovaný embeddingový a chatový provider; samotná databáze ani testovací režim modely nenahrazují. Modelové volání prozatím zůstává na Azure OpenAI.

Lokální SQL Server ověřuje běžný SQL Server dialect, schéma, CRUD, profilovou synchronizaci a přesnou Python cosine referenci nad všemi platnými způsobilými vektory aktivního indexu bez capu. Neověřuje native VECTOR/VECTOR_DISTANCE, DiskANN ani výkon konkrétního Azure tieru; ty vyžadují samostatný Azure integrační cíl. Native funkční testy již prošly na Showcase a JHU má nativní exact úložiště; reprezentativní ANN/výkonová akceptace zůstává otevřená. Aktuální příkazy včetně admin frontendu a lokálních SQL testů shrnuje [README](../../README.md).
