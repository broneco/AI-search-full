# Vysvětlení testů `test_ann_search.py`

## Pro netechnického čtenáře

Testy kontrolují, že rychlé přibližné hledání nelze zapnout bez správného indexu, že dodržuje přístupová práva a že při problému nespouští automaticky další drahé hledání. Běžné lokální testy používají testovací modely, nemažou vaše dokumenty a nepotřebují cloud. Lokální ODBC test opravdu ukončí příliš dlouhý SQL příkaz a ověří, že další dotaz funguje.

## Technické scénáře

**v0.1.4:** native ANN nyní materializuje celý způsobilý set ID/revizí v SQL před VECTOR_SEARCH; nic neomezuje před ACL. Testy konstrukce ověřují jediný TOP až po eligibility INSERT, vynucený skutečný ANN a porovnání aktuálních revizí. Parametrizovaný sp_executesql scope potlačí mezilehlé rowcounts a obnoví původní SET options; skutečný lokální T-SQL test ověřuje NOCOUNT ON/OFF, Unicode/injection vstup i timeout a funkční další dotaz. Původní textové predikáty se samostatně vykonají na lokálním SQL pro oba ACL/tenancy; změna wrapperu tyto sémantické testy neobchází. Native lifecycle test dál kontroluje update/rollback/cascade.

- Dlouhý query JSON (>4000 znaků pro 1536 rozměrů) se při inicializaci `@query_vector` nejprve převádí na NVARCHAR(MAX), aby ODBC NTEXT binding neselhal chybou 529. Obě dimenzní SQL regrese ověřují parametrizaci i tento mezikrok. Dne 2026-10-14 prošla na skutečném Showcase SQL přes Entra/ODBC17 samotná produkční deklarace proměnné pro identické/kolmé 1536rozměrné vektory (0/1); VECTOR_SEARCH se při tomto čtecím probe neprováděl a žádný index nevznikl. Nejde o native ANN akceptaci.

- ANN statement je parametrizovaný pro 2 i 1536 rozměrů, používá jediný `TOP … WITH APPROXIMATE`, SQL vector proměnnou, žádný `TOP_N`, `FORCE_ANN_ONLY` a pouze distance ASC. Sdílené tenant/doc ACL/chunk ACL/freshness/metadata výrazy jsou ve stejném WHERE před top K. Zdrojové `v.chunk_id`/`input_revision` a výsledkové `vs.distance` respektují Azure alias scope; korumpovaný identifikátor se odmítne.
- Regrese ANSI/Unicode bindů zachovává původní typy compileru včetně rozbalených ACL IN parametrů a explicitně přetypuje textové placeholdery na VARCHAR(MAX)/NVARCHAR(MAX). Samotný String bind v textual SQL nestačí: ODBC může dodat NVARCHAR a DATALENGTH pak u tenant VARCHAR vrací 10 místo 5. Skutečná lokální MSSQL kontrola používá přímo expression z ANN statementu a vyžaduje (5,5). MAX zamezuje tichému zkrácení dlouhých filtrů; metadata a skupiny zůstávají Unicode.
- Skutečný katalogový status je filtrován podle sloupce embedding a přečte verzi/typ/metriku/disabled. Ambiguity, unknown či <3 verze, nesprávná metrika a vypnutý index se odmítají.
- Přesná lokální reference funguje bez ANN metadata; ANN bez indexu nevolá exact. Profil stejného rozměru s jinou revizí se odmítá. Request plán eliminuje opakované katalogové průchody a odmítá tenant/mode mismatch.
- DDL nevznikne s neúplným pokrytím nebo <100 vektory. Vytváří se přes oddělené AUTOCOMMIT připojení (skutečné Azure jinak hlásí chybu574), MAXDOP1, a po DDL se ověří version>=3/metrika/enabled. Mock kontroluje autocommit, skutečný lokální test prokazuje odmítnutí již flushnuté neukončené caller transakce bez jejího commitnutí. DDL samotné nelze session rollbackem vrátit; při neúspěšném ověření se index nesmaže ani neaktivuje automaticky.
- ODBC timeout scope vrátí původní hodnotu na živém pooled connection při výjimce. Skutečná MSSQL regrese použije WAITFOR 3 s a timeout 1 s; pokud SQLAlchemy spojení invaliduje, ověří nový funkční connection s původním timeoutem. SQLite toto ověření přeskočí.
- DBAPI HYT00 vede k 504/search_timeout, jiná SQL chyba k 503/search_unavailable; žádný exact retry, žádné provider/SQL/secret detaily v chybě. API zachovává string detail pro frontend a strojový kód v hlavičce.
- ANN dispatch používá simulované winners a skutečnou SQLite/MSSQL hydrataci: nepovolený dokument ani nová verze textu/reembedding se starou ANN vzdáleností se nikdy nevrátí, empty výsledek je stabilní a cosine skóre / diagnostika odpovídají režimu. API preflight selže před vytvořením threadu/embeddingem/LLM, success metadata označují exact/ann a SQL timeout nesmí volat LLM. CLI mutace odmítne nesprávný očekávaný cíl před DB přístupem.
- Schema default je exact, auto fallback a neplatný timeout jsou odmítnuty.

## Reálný native ANN test

**Výsledek 2026-10-14:** skutečný `test_native_ann_filters_and_transactional_lifecycle` na Showcase prošel (1 passed, 36 deselected). Cosine DiskANN version3/enabled, 1536dim, exact reference1 vs ANN1 pro selektivní filtr, empty/fullK, oba ACL/tenant, změna revize/reembedding, rollback a cascade. Výstup potvrdil úplný cleanup a nezměněné dbo counts 35docs/1385chunks/6users/5threads/10messages. Předchozí neúspěšné běhy odhalily a opravily DDL574, typy bindů a korelaci ACL; nebyla snížena testovací kritéria. Native exact scénář prošel v předchozích bězích. Nebyl měřen reprezentativní recall/výkon ani nasazena aplikace.

Alternativní izolovaná cesta používá explicitně schválenou existující test DB přes Entra CLI a nové `ann_test_<uuidhex>` schéma. Produkční raw SQL se v testovacím listeneru mění pouze v kvalifikaci tabulek/katalogového objektu; výrazy prefiltrů a algoritmus se zachovají. Žádné app dbo migrace, modelová volání ani activation běžné aplikace. Test vypíše skutečnou verzi/metriku/enabled stav DiskANN a po úklidu agregované dbo counts; podrobnosti viz `test_native_sql_harness.md`.

`test_native_ann_filters_and_transactional_lifecycle` vyžaduje oba opt-in příznaky RUN_NATIVE_SQL_TESTS a RUN_NATIVE_ANN_TESTS. Používá stejný potvrzený EMPTY Azure DB fixture jako `test_vector_store.py`: žádný model endpoint, žádná aplikační databáze. Vytvoří ≥100 diverzních 1536rozměrových vektorů, verzi ≥3, ověří selective/empty/full K, tenant/doc ACL/chunk ACL, invalidaci textu, update/rollback/cascade. Fixture uklidí pouze vlastní tabulky. Test nebyl při implementaci spuštěn a je přesunut do cloudové brány slice 5; samotný benchmark recall/p95 není jeho součástí.

Příkazy jsou v [návodu slice 4](../development/search-slice-4-testing.md). SQL Server 2022 nepodporuje native ANN; zelený lokální výsledek nesmí být označen jako cloudová akceptace.
