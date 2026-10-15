# ADR-0024: Explicitní DiskANN v3+ a politika selhání hledání

- Status: accepted (funkční native exact/ANN ověřeno na izolovaném Showcase schématu; aplikační rollout a výkon čekají)
- Date: 2026-10-14
- Owners: AI Search Core Team
- Supersedes: —
- Superseded by: —

## Context

Slice 3 ukládá vektory do profilových tabulek a poskytuje přesné hledání. ANN musí zachovat stejnou identitu profilu, tenant, obě úrovně ACL, metadata a revizi vstupu. Na Basic 5 DTU nelze při selhání ANN automaticky opakovat nákladný úplný scan. Uživatel schválil odložení Azure integrace do slice 5 a pokračování s lokálními testy.

## Decision

- Serverová search konfigurace má `vector_search_mode`: výchozí `exact`, explicitní `ann`. Není režim `auto`; chybějící, neznámý, starý, vypnutý nebo metrikou nekompatibilní ANN index vede k řízenému odmítnutí, nikoli k fallbacku. Operátor musí zvolit `exact` sám.
- Skutečná verze se načítá z `sys.vector_indexes.build_parameters` (`$.Version`) a ověřuje se sloupec `embedding`, metrika cosine, typ DiskANN a stav enabled. Vyžaduje se verze ≥3 kvůli iterative filtering a DML. Neznámá verze se neodhaduje.
- ANN používá `SELECT TOP (:top_k) WITH APPROXIMATE`, `VECTOR_SEARCH`, vektorovou SQL proměnnou a `ORDER BY vs.distance ASC`. Nepoužívá starý `TOP_N` ani dodatečný klíč řazení. `FORCE_ANN_ONLY` brání skrytému kNN scanu při změně/chybějícím indexu i rozhodnutí optimizeru přejít do přesného scanu.
- Sdílené eligibility výrazy z exact/keyword větví jsou parametrizovaně vloženy do stejného ANN SELECT před top K, včetně SQL EXISTS pro ACL a shody revize. Identifikátory jsou odvozené a ověřené katalogem, native tabulky explicitně ve schématu `dbo`. Texty, ACL ani modely se neduplikují.
- Ověření Azure odhalilo chybu samostatné kompilace ACL výrazu: EXISTS obsahoval vlastní documents/chunks FROM a nebyl vázaný na kandidáta. Kanonické predikáty se proto kompilují v kontextu vnějšího chunks JOIN documents SELECTu; výsledný WHERE zachovává korelaci. Rozbalené bind typy zůstávají zachované a textové parametry jsou explicitně VARCHAR(MAX)/NVARCHAR(MAX), aby pyodbc NVARCHAR transport nerozbil kontrolu DATALENGTH na VARCHAR tenantovi. MAX zabrání zkrácení filtrů.
- ANN nejprve vrátí nejvýše K ID/vzdáleností; text se načte druhým SQL dotazem s opětovným ověřením eligibility i revize. Tato obrana proti změnám mezi dotazy neslouží jako náhrada prefiltrů. Při souběžné změně dat může vrátit méně než K; nedělá další retrieval retry.
- Po preflight se pro tento požadavek ponechá ověřený profilový index. Embedding i retrieval používají tento profil/index, i pokud operátor mezitím přepne aktivní index; starý index zůstává dostupný pro návrat. Neopakují se katalogové lookupy po embeddingu. Profil, tenant, korpus a režim připraveného plánu se znovu porovnají před hledáním. Změna fyzického ANN indexu během požadavku může způsobit řízené selhání; provozní změny dělat v maintenance okně.
- `vector_query_timeout_seconds` (výchozí 10, celé číslo 1..120) nastavuje timeout nových ODBC statementů při preflight a vektorové větvi. Původní nastavení se obnoví při opuštění scope; SQLAlchemy může po timeoutu spojení uzavřít a vyřadit. Toto není celkový deadline retrievalu ani příslib p95: keyword/context SQL, připojení, modelová volání a Python výpočet mají vlastní chování.
- SQL timeout HYT00/HYT01 vrací HTTP 504, ostatní DBAPI selhání HTTP 503. `detail` zůstává string kvůli současnému frontendu, hlavička `X-Search-Error-Code` nese strojový kód. Odpověď ani log neobsahují SQL, query vector či driver secrets. Nespouští se náhradní model, index nebo scan.
- Metadata obsahují `vector_exact`/`hybrid_exact` nebo `vector_ann`/`hybrid_ann` a `search_diagnostics` (index/profile ID, storage, verze ANN, počet kandidátů, čas vektorové větve a celý retrieval). Logy neobsahují dotaz ani obsah dokumentů. Čas retrievalu neobsahuje embedding otázky a generování odpovědi; preflight před embeddingem není zahrnut, v benchmarku slice 5 jej měřit také samostatně.
- DDL je explicitní `migrate_search_vectors.py --index … --create-ann` se stávajícími potvrzeními cíle. Vyžaduje kompletní pokrytí a alespoň 100 aktuálních vektorů; používá MAXDOP 1 a automaticky nezapíná ANN. **Ověření Azure 2026-10-14 změnilo transakční předpoklad:** server odmítl CREATE VECTOR INDEX v uživatelské transakci chybou 574. Operace proto vyžaduje ukončenou caller transakci, provede preflight pouze ve vlastní read transakci, ukončí ji rollbackem a DDL spustí na odděleném AUTOCOMMIT připojení. Poté ověří skutečnou verzi/metriku/enabled. DDL už je při této kontrole trvalé; session rollback jej nevrátí. Neověřený/nekompatibilní index se automaticky nepřepne ani nesmaže: nechat exact a požadovat explicitní operátorský zásah. CLI ukončí své známé read-only zbytky transakce až po explicitně commitnutých předchozích krocích. Funkce odmítne libovolnou aktivní caller transakci bez commit/rollbacku jejích zápisů. Starý index se sám nemaže ani nepřebudovává. Runtime nevytváří indexy.

## Options considered

Automatický fallback a starý oversampling/TOP_N byly odmítnuty: první může násobit zátěž po chybě, druhý nesplňuje filtry před top K. Optimizerem volený exact scan v ANN režimu byl odmítnut kvůli předvídatelnosti a poctivé diagnostice; operátor může explicitně zvolit přesnou cestu, pokud selektivní filtry vyhodnotí lépe.

## Consequences

Lokální SQL Server 2022 dál používá přesnou JSON referenci. Testy kompilace a řízení ANN nepředstírají skutečný DiskANN; nativní Azure test je připravený a defaultně přeskočený. SQL Server 2025 Docker zůstává samostatný navržený mezikrok, nebyl instalován. Výkonový i recall kompromis `FORCE_ANN_ONLY`, plány složitých ACL/JSON prefiltrů a DML chování musí ověřit slice 5.

## Sources

- [Microsoft VECTOR_SEARCH — syntax, aliases, filters and FORCE_ANN_ONLY](https://learn.microsoft.com/en-us/sql/t-sql/functions/vector-search-transact-sql?view=sql-server-ver17)
- [Microsoft CREATE VECTOR INDEX — Version, minimum 100 rows and DML](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-vector-index-transact-sql?view=sql-server-ver17)
- [Microsoft sys.vector_indexes](https://learn.microsoft.com/en-us/sql/relational-databases/system-catalog-views/sys-vector-indexes-transact-sql?view=sql-server-ver17)
- [pyodbc connection query timeout](https://github.com/mkleehammer/pyodbc/wiki/Connection#timeout)

## Follow-ups

2026-10-14 prošel skutečný native exact scénář a následně native ANN lifecycle scénář na existujícím Showcase SQL přes Entra CLI v izolovaném schématu. Ověřeno cosine DiskANN v3 enabled, 1536dim, metadata selective/empty/fullK, tenant/docACL/chunkACL a update/rollback/cascade; exact navíc nejlepší za625, profily a native zápisy. Testovací schéma bylo odstraněno a původní dbo počty zůstaly 35docs/1385chunks/6users/5threads/10messages. Produkční kvalifikace dbo je při tomto testu pouze přesměrovaná do vlastního schématu; běžná aplikace ani její identity/migrace tím nejsou ověřené. Žádný deployment/aktivace nebo reprezentativní recall/performance výsledek se tím nepotvrzuje; výkon uživatel odložil na JHU.

Funkční Azure testy nyní mohou používat schválené existující testovací DB s novým izolovaným `ann_test_<uuidhex>` schématem přes test-only schema_translate_map a úzkou kvalifikaci produkčního raw SQL. To nemění produkční dbo strategii; původní empty-only fixture zůstává alternativou. Testovací schema cleanup byl lokálně ověřen i při výjimce/existujícím cizím schématu. Cloudový deployment/aktivace a měření výkonu zůstávají samostatné kroky; uživatel volí funkčnost Showcase, výkon později JHU.

Zbývá schválený aplikační rollout/API smoke/runtime permissions a query plans, reprezentativní recall@30 ≥95 % na nejméně 100 dotazech a p95 retrievalu ≤1 s při souběhu 1/3 (200 požadavků na variantu), cold start zvlášť. Výkon až na později potvrzeném JHU cíli. Syntetický native exact/ANN test je splněný, širší kvalita/výkonová aktivace nikoli; kapacitu nenavyšovat automaticky.
