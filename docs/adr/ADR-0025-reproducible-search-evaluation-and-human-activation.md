# ADR-0025: Reprodukovatelná evaluace retrievalu a ruční aktivace

- Status: accepted (lokální implementace; cloudové brány zůstávají neověřené)
- Date: 2026-10-14
- Owners: AI Search Core Team
- Supersedes: —
- Superseded by: —

## Context

Slice 4 poskytuje exact a DiskANN se stejným profilem a prefiltry. Před zapnutím ANN potřebujeme měřit kvalitu indexu i cenu celého retrievalu. Máme současně jen lokální SQL Server 2022; nativní Azure přesné/ANN integrační testy čekají na lidský handoff. Lokální smoke nemůže potvrdit výkon Basic 5 DTU / Container App 0,5 CPU a 1 GiB.

## Decision

- CLI `benchmark_search.py prepare` vytvoří cache query embeddingů přes existující provider factory/`embed_query`, odděleně od časování. Dotazy se neembedují dokumentovým režimem. Cache je svázána s celým datasetem a immutable profilem; při změně textu, filtrů, identity nebo modelového prostoru se odmítne. Profil se nesmí nahrazovat podle shodného rozměru. `run` nevolá žádný model a nemění DB/index/config.
- Dataset v1 obsahuje jedinečná case ID, otázku, filtry a volitelné UUID serverového uživatele. Identické kombinace otázka/filtry/uživatel se odmítají. Výchozí subject je povinný CLI `--user-id`. Dataset nesmí zadávat skupiny; každý request načte skutečné aktuální DBUser.groups pro přesný tenant podle stejné politiky jako API. Jde o nástroj operátora s DB oprávněním, nikoli o nový veřejný API endpoint.
- Bez `--index` se měří aktivní index. Explicitní katalogové UUID dovoluje měřit i neaktivní index před jeho nasazením, s kontrolou tenantu, korpusu, profilu a native storage v Azure. Nic se kvůli benchmarku automaticky neaktivuje. V jednom běhu je jediný profil; další modely se zpracují samostatně/sequentialně a potřebují vlastní cache.
- Recall@30 měří ID vektorových kandidátů ANN proti exact nad stejnými filtry a profilem, před fusion/boost/expansion. Jmenovatel je počet skutečně dostupných exact výsledků do 30. Dva prázdné výsledky mají recall `null`, nikoli 1; nevstupují do průměru ani minimálního počtu. ANN výsledek proti prázdné exact referenci je chyba. Tie hranice se hodnotí přísně podle deterministických exact ID, nikoli domyšlenou tolerancí.
- Report má průměr recall, nejméně 100 různých neprázdných otázek (normalizace casefold/strip), počet prázdných/chybných případů a členění podle skutečné selektivity vůči počtu tenantích chunků: empty, ≤1 %, ≤10 %, broad. Opakování workloadu pro load test nesmí doplnit chybějící kvalitativní otázky. Malý český dataset osmi otázek Aurora je smoke, ne aktivační eval.
- Load test měří novou session, serverovou identitu, načtení aktuální konfigurace pro každý request, preflight a celé `VectorRetriever.retrieve` včetně keyword/fusion/expansion. Parametry konfigurace musí zůstat stejné jako na začátku; jejich změna běh odmítne. Použije stejné cached vectors, odděleně exact a ann, 200 requestů pro concurrency 1 a 3. P95 je nearest-rank `ceil(.95*N)`, zahrnuje i časy chybných requestů; každá chyba ale zablokuje brány a zátěžová fáze skončí po aktuální dávce.
- Souběžné dávky běží na jednom event loop stejně jako současná async retrieval cesta. Čas příchozí dávky se zaznamená PŘED dispatch, takže synchronní SQL/Python blokující event loop neukryjí čekání ostatních requestů. Nezavádíme umělý thread pool se třemi nezávislými backendy. Jde o měření uvnitř procesu, nikoli důkaz latence HTTP služby či Azure runtime. CLI zahrnuje také per-request načtení konfigurace včetně případného Blob I/O; HTTP/JWT jsou mimo metriku. Modul dovoluje explicitní frozen-config unit/reference běhy bez loaderu, ale pak `config_load_included=false` zablokuje aktivační brány.
- První retrieval a warmup jsou oddělené od load distribuce. Preflight/snapshot už použily DB, proto report výslovně uvádí `cold_start_measured: false`. První požadavek není vydáván za cold start aplikace, SQL buffer cache ani infrastruktury; skutečný start musí samostatně doplnit cílová integrace.
- Před/po běhu se streamovaně porovná úplné pokrytí a hash dokumentových/chunkových revizí a metadat, vector row ID/revizí, ACL grantů a serverových skupin, včetně ANN metadat. `chunk_corpus_hash` odděluje společný korpus od fyzických vector row ID. Texty a celé embeddingy se kvůli fingerprintu nepřenášejí. Repo zápisy při změně embeddingu mění vector row ID; přímé externí SQL přepisující vektory/revize je mimo tento kontrakt. Před/po hash není ochrana proti libovolné souběžné změně a navrácení; během validovaného běhu je nutné zastavit writery, konfiguraci i DDL.
- Report obsahuje target bez credentials, profil/dataset/cache fingerprint, použitou retrieval konfiguraci, OS/Python, jednotlivé časy/počty a bezpečné chybové kódy. Neobsahuje texty otázek/dokumentů, raw vektory, skupiny, credentials ani tenantí prompt nastavení. Cache a soukromý dataset patří do ignorované `.local/benchmarks/`; report/cache se nikdy nepřepisují. `.local` a lokální/testovací env soubory se vylučují také z Docker image.
- Numerické brány: native DiskANN ≥3, stabilní úplný korpus, ≥100 neprázdných různých otázek, mean recall@30 ≥95 %, žádné chyby, ≥200 ANN requestů pro obě concurrency a p95 ≤1000 ms. Výsledek je nejvýše `human_review_required`; cloud acceptance zůstává pending do ověření reálného native SQL, runtime/permissions/Cold startu a reprezentativnosti workloadu. `--require-gates` vrací exit 3 při nesplnění, ale uchová report. Nástroj nikdy nezapíná ANN ani nemění kapacitu.

## Options considered

Měření celého chatu by směšovalo modelové latence s retrievalem. Simulované ANN na lokální JSON tabulce by neprokazovalo skutečný index. Měření každého requestu až po získání CPU by skrývalo frontu při concurrency 3. Všechny tři varianty byly odmítnuty. Samostatný veřejný benchmark endpoint není pro první operátorský eval potřebný.

## Consequences

Lokálně lze ověřit cache, správnost metrik, permission/transaction kontrakty a skutečnou exact referenci. V Azure je nutná samostatná prázdná integrační DB a pak reprezentativní benchmark korpus. Windows lokální p95 nad třemi chunky se nesmí prezentovat jako Azure výsledek. Budoucí relevance embeddingových modelů (označené dokumenty, Recall@K/nDCG@K) zůstává oddělená úloha; cosine skóre různých modelů se neporovnávají.

## Follow-ups

Dokončit cloudovou část slice 5 podle `.agents/inbox/2026-10-14-search-evaluation-activation-handoff.md`: native integrační testy, ≥100 reprezentativních otázek, benchmark ve skutečném runtime, cold start/HTTP kontrola a lidská aktivace se zachováním exact rollbacku. Dokud neprojde, výchozí režim zůstává exact a slice 5 není cloudově dokončený.
