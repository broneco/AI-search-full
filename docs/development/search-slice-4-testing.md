# Slice 4: explicitní exact / DiskANN a lokální ověření

## Co je nyní implementované

Backend podporuje režimy `exact` (výchozí) a `ann`. ANN vyžaduje native profilovou tabulku a skutečně ověřený enabled cosine DiskANN index verze ≥3. Chybějící index vrátí 503 s doporučením explicitně zvolit exact. SQL timeout vrátí 504 bez dalšího scanu. Na nynějším lokálním SQL Serveru 2022 ponech `exact`.

## Lokální automatické testy

Spusť Rancher/Docker Engine a `./dev.ps1 -Action start-db`. V kořeni repozitáře z terminálu VS Code vlož pouze příkazy uvnitř bloku, bez řádků s trojicí zpětných apostrofů:

```powershell
Remove-Item Env:RUN_NATIVE_SQL_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:RUN_NATIVE_ANN_TESTS -ErrorAction SilentlyContinue
$env:RUN_LOCAL_SQL_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_ann_search.py tests/test_vector_store.py tests/test_search_access.py tests/test_search_config.py tests/test_rechunk.py -q --tb=short
Remove-Item Env:RUN_LOCAL_SQL_TESTS -ErrorAction SilentlyContinue
```

Testy mají fake modely a izolovanou SQLite / dočasnou lokální SQL Server DB. Zachovávají `ai_search_local`, uživatelské dokumenty i staré indexy. Nová sada kontroluje ANN SQL a prefiltry před top K, parametry/aliased sloupce, odmítnutí verze <3, kompatibilitu profilu, žádný fallback, bezpečnou hydrataci, diagnostiku a HTTP chyby. MSSQL varianta skutečně ověřuje ODBC timeout na třísekundovém WAITFOR s limitem 1 s a následné funkční připojení. SQLite tuto konkrétní variantu přeskočí.

Nativní exact a ANN testy zůstávají skipped bez samostatného explicitního opt-in. ANN lokální dispatch test má simulované ID/vzdálenosti, ale skutečné SQL kontroly oprávnění při načítání obsahu. Výsledky nejsou důkazem skutečného ANN recall či Azure latence.

## Ruční kontrola aplikace

Ověření při implementaci 2026-10-14: celá sada s lokálním SQL měla **176 passed, 6 skipped**. Závěrečná ANN sada po doplnění SQL varianty 1536 rozměrů měla **28 passed, 2 skipped**. Compileall a diff check prošly. Read-only audit současného lokálního setupu potvrdil dva existující indexy s pokrytím 3/3 a právě jeden aktivní; `ann_index: null` je zde správně. Tyto výsledky jsou lokální, nikoli Azure/ANN benchmark.

Po restartu backendu vyzkoušej otázku „Kolik kreditů potřebuji pro postup do druhého ročníku?“ a otevři PDF citaci. V Network → odpověď POST `/api/chat` očekávej `metadata.retrieval_strategy: hybrid_exact` a `metadata.search_diagnostics` s `vector_mode: exact`, `storage: local_json`, aktuálním `index_id`/`profile_id` a časy. `retrieval_latency_ms` je čas hledání/fusion/expansion bez modelových volání; čas preflight před embeddingem je oddělený a zatím není v tomto poli.

Volitelný audit z lokálního terminálu:

```powershell
$env:APP_ENV = "local"
.venv\Scripts\python.exe migrate_search_vectors.py --ann-status
```

Pro lokální JSON tabulky je `ann_index: null` očekávané. Nepoužívej `--create` pro opakovaný audit; vytváří nový logický index. ANN konfiguraci na současném lokálním backendu nezapínej.

## Konfigurace a návrat

Search konfigurace má dva nové serverové klíče: `vector_search_mode` (`exact` / `ann`) a `vector_query_timeout_seconds` (výchozí 10, celé číslo 1..120). Staré konfigurace bez klíčů používají výchozí hodnoty. Nejde o request filtry ani volbu modelu.

Management může přes existující POST `/api/chat/config` uložit celou konfiguraci s požadovaným režimem. Neodesílej jen dva klíče: ostatní parametry by schema doplnilo výchozími hodnotami. Nejprve načti aktuální celou konfiguraci GET `/api/chat/config`, změň režim a zachovej ostatní pole. Pro cloudový chat použij tento API postup, který zapisuje i jeho Blob konfiguraci; samotná editace diskového JSON nemusí změnit cloudový chat (sjednocení konfigurace je stále odloženo). UI přepínač režimů není součástí slice 4.

Zpět do exact přepni stejným postupem `vector_search_mode: exact`. Profil/index/tabulka a embeddingy zůstávají stejné, není potřeba reembedding. ODBC limit je na jednotlivé SQL statementy vektorové větve/preflight; neomezuje embedding/LLM, keyword SQL ani celý HTTP požadavek.

## Azure integrační brána odložená do slice 5

Postup je v [handoffu DiskANN](../../.agents/inbox/2026-10-14-diskann-search-handoff.md). Nativní test používá prázdnou Azure test DB, vytvoří diverzní syntetické embeddingy, ověří index verze ≥3, selective/empty/top K, obě ACL, tenant a update/rollback/delete. Nevolá embeddingový ani odpovědní model. Nepouštěj jej nyní nad běžnou databází.

Po lidském zřízení a ověření `.env.native-test` / očekávaného cíle:

```powershell
$env:RUN_NATIVE_SQL_TESTS = "1"
$env:RUN_NATIVE_ANN_TESTS = "1"
$env:NATIVE_SQL_EXPECT_HOST = "<potvrzený testovací SQL host>"
$env:NATIVE_SQL_EXPECT_DB = "<potvrzená prázdná DB s test v názvu>"
.venv\Scripts\python.exe -m pytest tests/test_vector_store.py tests/test_ann_search.py -k "native_vector_end_to_end or native_ann_filters" -q --tb=short
Remove-Item Env:RUN_NATIVE_SQL_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:RUN_NATIVE_ANN_TESTS -ErrorAction SilentlyContinue
```

Samotné vytvoření DiskANN pomocí CLI používá existující profilový index a potvrzený host/DB/tenant. `--create-ann` vyžaduje kompletní pokrytí a ≥100 aktuálních vektorů a MAXDOP1. Skutečné Azure ověření zjistilo chybu574 při DDL uvnitř transakce: vytváření proto běží na odděleném AUTOCOMMIT připojení až po uzavření vlastní read preflight transakce. Caller nesmí mít neukončenou transakci; funkce ji odmítne bez commitnutí cizích zápisů. Verze/metrika/enabled se ověřují po DDL; jeho rollback nelze slíbit. Při neověřeném indexu ponechat exact a ručně prověřit stav, automaticky nic nemazat. Režim vyhledávání se nemění. Reálný výkon a reprezentativní recall nadále nejsou ověřené.

Pro uživatelem zvolenou existující Showcase DB je připravený schvalovaný izolovaný schema režim přes Entra CLI, viz aktuální slice5 handoff. Nepoužívej tam starý empty-only příkaz bez schema/allow-existing příznaků; ten zůstává jen pro prázdnou samostatnou DB. Výkon se bude řešit později na potvrzeném JHU cíli.
