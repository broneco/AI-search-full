# Vysvětlení `test_search_benchmark.py`

## Netechnicky

Testy ověřují, že benchmark neopakuje modelová volání během měření, nepřiděluje si oprávnění z testovacího souboru a nedá zelenou aktivační bránu malému či chybnému vzorku. Dále kontrolují, že lokální testy zachovají původní dokumenty/index a že neaktivní experiment lze změřit bez jeho zapnutí.

## Technické scénáře

- Regrese souběžných dávek používá skutečné async yield a řízené hodiny místo nespolehlivého 1ms sleep na Windows. Kontroluje přesné latence10/20/30 ms pro každou dávku, maximum tří současných požadavků a ukončení fáze po první chybné dávce. Produkční měření nadále používá skutečný perf_counter.
- CLI/cache roundtrip izoluje výběr svého syntetického dvourozměrného profilu od runtime tenant katalogu. Stejný test tak běží i v čisté JHU projekci bez `tenants/default`; skutečný výběr experimentálního prostoru má samostatnou regresi.

- Recall@30 má jmenovatel podle dostupné exact reference do K; nula oproti nule je null, ANN proti prázdné referenci chyba. Nearest-rank p95 zahrnuje pomalé chybné requesty, nikoli jen úspěchy.
- Dataset odmítá duplicitní case IDs, identické query/filter/user kombinace, klientské ACL skupiny a neplatné metadata. Cache kontroluje dataset/profile fingerprint, plnou definici profilu, revizi/rozměr a nenulové vektory. Stejně dlouhý jiný model/revize není kompatibilní.
- Provider používá query režim jednou pro každou různou otázku; dokumentový režim ani generování odpovědi se nevolá. Provider chyba je bezpečně zabalená bez privátního detailu.
- Quality agregace nevydává empty reference za úspěšný recall. Sto kopií stejné otázky nesplní minimální počet různých dotazů. Report obsahuje skutečné selektivity a průměry odděleně.
- Gate policy zablokuje <100 otázek, recall pod 95 %, <200 requestů pro požadovanou concurrency, p95 nad 1000 ms, starý/local index, nestabilní korpus nebo jedinou chybu. Ani ideální čísla nikdy nezpůsobí cloud acceptance či automatickou aktivaci; CI `--require-gates` vrací 3.
- Load orchestrace nabídne nejvýše tři requesty zároveň a skončí po chybné dávce. Deterministické hodiny dokazují, že synchronní blocking přidá dalším requestům latenci 100/200/300 ms, místo aby se čekání ztratilo.
- SQLite i skutečný lokální MSSQL ověřují snapshot změny metadata/ACL a invalidaci obsahu, cizí tenant subject, skutečný exact/hybrid retrieval, read-only stabilitu, redakci výsledků a odmítnutí ANN na local_json.
- Připravený CLI roundtrip používá fake provider jen při tvorbě cache; běh přečte cache ze souboru a provider dále nevolá. Existující report se nepřepisuje a očekávaný target se kontroluje před přístupem k datasetu/DB/provideru.
- Neaktivní index jiného profilu se vyhodnotí explicitně; předchozí aktivní index zůstane zachovaný a nesoulad profilu se odmítne.
- CLI při každém měřeném requestu načítá konfiguraci včetně možného Blob I/O. Test na SQLite/MSSQL dokazuje volání loaderu a odmítnutí změny retrieval parametrů; module-only běh bez loaderu nemůže splnit aktivační brány.
- Simulovaná native orchestrace testuje celou větev 100 query referencí, 200 requestů na režim/concurrency, selective a empty výsledky a následný drift. Tyto umělé výsledky slouží pouze unit testům; nejsou exportovaným skutečným ANN měřením.
- Docker exclusions chrání `.local` reporty/cache a lokální/testovací env soubory. Report nemá otázky, dokumentový obsah, raw vektory ani custom prompty.

## Co testy neprokazují

Neprokazují nativní Azure VECTOR/DiskANN funkčnost, runtime oprávnění, recall reálného korpusu nebo p95 Basic 5 DTU / Container App. SQL Server 2022 integrační varianta používá přesnou JSON referenci; native testy a skutečný workload musí dodat lidský handoff. `fixtures/local-university/search-smoke.json` má osm otázek a záměrně nemůže splnit ANN quality bránu.

Příkazy a interpretace jsou v [návodu slice 5](../development/search-slice-5-testing.md).

CLI načte embeddingový prostor z vybraného nebo aktivního indexu. Příprava cache tak umí neaktivní Nomic experiment; samotné měření používá cache a nevolá embeddingovou službu.

CLI factory dostává vlastní SQL session také při volbě registrovaného experimentálního embeddingového profilu; query cache stále patří jedinému explicitnímu indexu/profilu.
