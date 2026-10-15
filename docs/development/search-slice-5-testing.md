# Slice 5: benchmark, recall a podmínky aktivace

## Co lze nyní spustit lokálně

`benchmark_search.py` je operátorský read-only nástroj. `prepare` jednou vytvoří query embeddingy přes nakonfigurovaný provider (dnes Azure); `run` už používá cache, nevolá embedding ani odpovědní model a nemění dokumenty, indexy ani nastavení. Existující Docker/VS Code start zůstává stejný.

Malý verzovaný dataset `fixtures/local-university/search-smoke.json` má osm českých otázek o Aurora ukázkách, včetně metadat, méně než K výsledků a prázdného filtru. Je určený pro smoke, nikoli pro ANN akceptaci. Reálné privátní otázky/cache/reporty ukládej do `.local/benchmarks/`, která je ignorovaná Gitem i Dockerem.

## Spuštění z terminálu VS Code

Nejprve spusť Docker a `./dev.ps1 -Action start-db`. Backend musí alespoň jednou připravit ukázky a aktivní profilový index. Použij nový terminál bez exportovaných cloudových AZURE_SQL proměnných. Ve všech příkazech potvrď skutečný lokální target:

```powershell
$env:APP_ENV = "local"
.venv\Scripts\python.exe benchmark_search.py prepare --dataset fixtures/local-university/search-smoke.json --output .local/benchmarks/aurora-cache.json --expect-host 127.0.0.1 --expect-db ai_search_local --expect-tenant dolphin
```

Tento krok volá embeddingový provider pro osm otázek. Pokud už máš odpovídající cache, neopakuj jej. Existující soubor se nepřepíše; pro jiný dataset/profil zvol nový název. Cache neobsahuje credentials, ale obsahuje vektory a profilové instrukce, proto zůstává lokální.

Z již přihlášené aplikace zjisti `user_id`: v prohlížeči Network otevři odpověď autentizovaného GET `/api/auth/me` (nebo odpověď přihlášení `user.user_id`). Jde o UUID, nikoli email nebo access token. Zadej je do následujícího příkazu:

```powershell
$benchmarkUserId = "<UUID existujícího lokálního uživatele>"
.venv\Scripts\python.exe benchmark_search.py run --dataset fixtures/local-university/search-smoke.json --cache .local/benchmarks/aurora-cache.json --output .local/benchmarks/aurora-report.json --user-id $benchmarkUserId --requests 200 --expect-host 127.0.0.1 --expect-db ai_search_local --expect-tenant dolphin
```

Backend/FE nemusí být pro vlastní `run` zapnuté, potřebná je běžící SQL DB se stejným korpusem a konfigurací. Příkaz provede 200 requestů při souběhu 1 a dalších 200 při souběhu 3, první request/warmup vykáže zvlášť. Ostatní parametry retrieval převezme z aktuální serverové konfigurace. Dotazy se cyklicky opakují jen kvůli zátěži, nikoli pro splnění 100 kvalitativních otázek.

Výsledek na současném SQL Serveru 2022 očekávej `storage: local_json`, `quality.status: ann_not_requested`, recall `null` a `gates.activation: blocked`. To je správně: lokální exact smoke není ANN validace. `--requests 20` dovolí rychlejší kontrolu, ale nepokryje výkonovou bránu. Pro opakování použij nový output název; nic nemusíš znovu ingestovat ani aktivovat.

## Lokální výsledek z implementace

2026-10-14 proběhla skutečná příprava osmi query embeddingů a read-only benchmark aktivního profilu nad třemi místními chunky. Aktuální artefakty: `.local/benchmarks/aurora-query-cache-20261014.json` a `.local/benchmarks/aurora-local-full-report-20261014.json`. Druhý běh zahrnuje načtení konfigurace pro každý request (`config_load_included=true`), korpus před/po zůstal stejný, bez chyb a bez změny aktivace. Starší `aurora-local-report-20261014.json` je zachovaný diagnostický běh s konfigurací mimo časování; k posouzení úplného retrievalu používej full report.

| Režim | Souběh | Požadavky | p95 retrievalu |
|---|---:|---:|---:|
| exact / local_json | 1 | 200 | 62,15 ms |
| exact / local_json | 3 | 200 | 151,10 ms |

Jde o Windows lokální proces a Docker SQL, nikoli Azure Basic 5 DTU / Container App ani velký korpus. ANN nebylo vykonáno, recall nebyl měřen a aktivace zůstala blokovaná. První retrieval není skutečný cold start.

## Dataset a interpretace reportu

V1 JSON obsahuje `version: 1` a `cases`; každý případ má `case_id`, `query`, volitelné `filters` a volitelné `user_id`. Chybějící subject používá explicitní CLI `--user-id`. Skupiny se načítají z DB při každém requestu, dataset je nemůže přidělovat. Case ID jsou krátké technické identifikátory; soukromé otázky nepiš do názvů case ID. Identické query/filter/user kombinace a duplicitní ID jsou odmítnuté.

Report má fingerprint datasetu, query cache a korpusu, profil/index, kompletní coverage, ANN verzi, retrieval konfiguraci a runtime OS/Python. Texty ani vektory do něj nevkládá. Kontrola před/po zachytí běžné změny revizí/metadat/ACL/indexu; stopni ingestaci a změny nastavení po dobu měření. Report nezaručuje detekci libovolného externího SQL zásahu či změny a následného vrácení mezi snapshoty.

Recall@30 je počet shodných ANN/exact chunk ID dělený počtem exact výsledků do 30; při méně než K dostupných chunky se nepoužívá pevný jmenovatel 30. Prázdné exact+ANN mají `null`, ne bonusový recall 100 %. ANN kandidát proti prázdné referenci je chyba. Výsledky se člení podle skutečné selektivity filtrů a ACL (empty, ≤1 %, ≤10 %, broad). Shody skóre na hranici K se hodnotí striktně podle exact ID; duplicity embeddingů proto vyhodnoť také při lidském review.

P95 používá nearest rank a obsahuje čekání požadavků ve stejné příchozí dávce na jednom event loop. Scope CLI zahrnuje DB session, načtení identity/skupin, aktuální konfiguraci včetně případného Blob I/O pro každý request, preflight, vektorovou/keyword větev, fusion a expansion; nezahrnuje modely ani HTTP/JWT. Změna retrieval konfigurace během běhu vede k chybě. Běží současný synchronní SQL kód, nikoli tři uměle paralelní backendy. Chybná dávka ukončí zátěžovou fázi a zablokuje brány; po timeoutu nevzniká fallback/retry.

## Neaktivní indexy a další modely

Do `prepare` i `run` lze přidat `--index <katalogové UUID>`. Benchmark pak může vyhodnotit úplný neaktivní index bez přepnutí běžné aplikace; profil provideru/cache musí přesně odpovídat. Nevytváří tabulky a nedoplňuje dokumentové embeddingy. Profil/index připrav explicitní migrací/backfillem podle slice 3 a případně `--create-ann` podle slice 4.

Budoucí modely měř postupně s vlastní cache nad stejným datasetem a společným `chunk_corpus_hash`. Jediný běh nevolá všechny providery. Index recall proti exact je kvalita ANN algoritmu, nikoli relevance modelu; Recall@K/nDCG@K proti lidským document labels ani srovnávání cosine skóre různých modelů tento nástroj nedělá.

## Cloudová část slice 5 a aktivace

Postup je v [handoffu evaluace a aktivace](../../.agents/inbox/2026-10-14-search-evaluation-activation-handoff.md). Aktuální volba uživatele: nejprve funkčnost na EXISTUJÍCÍ Showcase DB, výkon později na potvrzeném JHU prostředí. Současný native pytest harness vyžaduje samostatnou prázdnou DB a nesmí se spustit nad Showcase beze změny; integrační zápisy/migrace/deployment čekají na konkrétní schválení. Pro pozdější benchmark je potřeba reprezentativní korpus a alespoň 100 různých otázek s neprázdnou referencí plus další empty/ACL/metadata případy. Běh nespouštěj nad produkcí bez vyhrazeného okna; kapacitu nástroj nemění.

### Showcase: ověřené přihlášení bez Key Vaultu

**Aktualizace funkčních testů 2026-10-14:** po schválení přesného rozsahu proběhl native exact test a následně úspěšný native ANN lifecycle test ve vlastním `ann_test_5d3dd2200872454b8f22d8287f8133af` schématu existující Showcase DB. Skutečný DiskANN v3/cosine/enabled, 1536dim, selective metadata/ACL/tenant, empty/fullK, změny revizí/reembedding a rollback/cascade prošly; exact pokryl i nejlepší výsledek za625 a oddělení profilů. Schéma bylo po každém běhu uklizeno, dbo counts zachovány (35docs/1385chunks/6users/5threads/10messages). Funkční opravy zahrnují DDL v autocommit, správné typy bindů a korelované ACL EXISTS. Starší scalar probe níže byl pouze první krok. Běžící Showcase backend/schema/migrace, skutečné runtime identity, reprezentativní recall a výkon zatím nejsou akceptované. Výkon až na zvlášť potvrzeném JHU cíli.

Dne 2026-10-14 se podařilo připojit přímo přes existující Microsoft Entra administrátorský účet přihlášený v Azure CLI. Není potřeba upravovat RBAC Key Vaultu ani resetovat SQL heslo. Jde o ověřenou cestu čtecího probe, nikoli potvrzení nasazení/identity běžící Container App.

Čtecí proces zachytí výstup `az account get-access-token --resource https://database.windows.net/ --query accessToken --output json` soukromě do paměti (např. `subprocess.run(..., capture_output=True)`); **nikdy token nevypisovat do terminálu ani souboru**. Token se kóduje UTF-16-LE s 4bajtovým little-endian prefixem délky a předává pyodbc přes `attrs_before[1256]`. Connection string obsahuje Driver17, potvrzený host/DB, `Encrypt=yes;TrustServerCertificate=no`, bez UID/PWD/Authentication/Trusted_Connection. Pro SELECT audit se použilo `attrs_before[101]=1`, transakce se ukončila rollbackem. Audit nepotřebuje chybějící lokální `azure.identity` a nenačítá app Settings/Key Vault. Token smí využít pouze již existující SQL oprávnění identity.

Prošlo přihlášení, compatibility 170, scalar VECTOR_DISTANCE (0/1), parametry 1536 rozměrů přes opravený NVARCHAR(MAX) mezicast a katalogové čtení. Showcase obsahuje 35 dokumentů/1385 chunků, dosud bez profilového/ACL katalogu a bez native vector indexu; původní FTS chunks je zapnuté. Dlouhý přímý JSON→VECTOR CAST původně selhal chybou 529/NTEXT; lokální oprava se vztahuje na native write, exact query i ANN deklaraci a není nasazená. Ověřeno šest opravených scalar/DECLARE SELECT případů (identické/kolmé vektory), nikoli skutečný native INSERT nebo VECTOR_SEARCH. Cílené místní regrese: 41 passed, 3 expected skips. Žádná změna Azure dat, schématu, kapacity, RBAC nebo deploymentu.

Na potvrzeném cloudovém test cíli, s odpovídající konfigurací procesu, cache, subjectem a případně explicitním neaktivním indexem:

```powershell
python benchmark_search.py run --dataset <PRIVATE_DATASET.json> --cache <QUERY_CACHE.json> --output <NEW_REPORT.json> --user-id <SUBJECT_UUID> --index <INDEX_UUID> --compare-ann --requests 200 --require-gates --expect-host <TEST_HOST> --expect-db <TEST_DB> --expect-tenant <TENANT>
```

`--compare-ann` vyžaduje skutečný native DiskANN ≥3; na lokálním JSON jej nesimuluje. Numerické brány kontrolují úplný stabilní korpus, mean recall@30 ≥95 %, ≥100 neprázdných různých otázek, nulové chyby a p95 ≤1000 ms při concurrency 1 i 3 s nejméně 200 requesty každé varianty. `--require-gates` při nesplnění vrátí exit 3 a ponechá report; bez něj je nevyhovující smoke stále úspěšně vytvořený report.

I při zelených číslech je výstup nejvýše `human_review_required`. Je nutné potvrdit native integraci, skutečné runtime/SKU/permissions, reprezentativnost selektivních ACL a cold start. Workstation benchmark vůči vzdálené Azure DB není měření Container App. Po lidském schválení se případně coverage-checked aktivuje nový logický index a přes Management config API přepne celý zachovaný config pouze v poli `vector_search_mode` na `ann`. Zpět na `exact` se vrátíš nad stejným profilem a tabulkou bez reembeddingu. Tool toto přepnutí neprovádí.

## Automatické regrese

Finální ověření 2026-10-14 po funkční Azure integraci a opravách: celá lokální pytest sada měla **217 passed, 10 skipped**, včetně **24 benchmark scénářů**. Compileall a diff check prošly; CLI help byl ověřen při původní implementaci. Skips jsou očekvané: dva opt-in modelové testy, native exact/ANN bez cloud opt-in v lokální sadě a šest MSSQL-only variant na SQLite. Native exact/ANN byly zvlášť skutečně spuštěné a úspěšné v Azure; lokální skips tento výsledek nenahrazují.

```powershell
$env:RUN_LOCAL_SQL_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_search_benchmark.py tests/test_ann_search.py tests/test_vector_store.py -q --tb=short
Remove-Item Env:RUN_LOCAL_SQL_TESTS -ErrorAction SilentlyContinue
```

Používají fake modely a izolovanou SQLite / dočasnou MSSQL DB. Podrobnosti popisuje [vysvětlení benchmark testů](../tests_explained/test_search_benchmark.md). Cloudové native testy nadále vyžadují samostatný explicitní opt-in; lokální zelená sada není důkazem Azure výkonu.
