# Testy profilového vektorového repository

## Dávkový backfill při JHU rollout (2026-10-15)

Nové regrese vyžadují nejvýše čtyři SELECTy nad chunky pro jednu dávku místo scalar get pro každý chunk a ověřují, že první čtení/recheck nestahuje legacy JSON při novém embeddingu. Po modelovém volání se vstupy načtou jedním SELECTem (na MSSQL UPDLOCK/HOLDLOCK) a zapíší v jedné transakci. Změna textu během modelového volání zastaví batch bez vložených vektorů. Provenance/profil a původní JSON se zachovávají. Oba případy proběhly na SQLite i lokálním SQL Serveru.

## Jednoduše

Testy ověřují, že hledání nepřehlédne nejlepší výsledek za starou hranicí 600, nepoužije embedding jiného modelu a po chybě při nahrazení dokumentu nezůstane databáze napůl aktualizovaná. Smazání chunku odstraní embeddingy; změna textu vyřadí embeddingy všech modelů a rollback je obnoví.

## Technicky

**Výsledek native exact 2026-10-14:** scénář `native_vector_end_to_end` skutečně prošel na existujícím Showcase přes Entra CLI v izolovaném schématu. Nativní zápisy/CAST, pořadí za625, metadata/tenant/docACL/chunkACL, profily, 1536dim, revize/update/rollback/cascade byly vykonané Azure SQL. Fixture odstranila své schéma a dbo počty zůstaly stejné. Předchozí věty o neprovedeném native testu níže popisují historický stav implementace; cloudový aplikační rollout a výkon tím nadále nejsou potvrzené.

Fixture nově podporuje i explicitně schválené existující Azure test DB přes `NATIVE_SQL_ISOLATED_SCHEMA` + `NATIVE_SQL_ALLOW_EXISTING=1` a přesný očekávaný host/DB. V tomto režimu používá Entra CLI a vlastní nové schéma; původní empty-only cesta zůstává beze změny. Podrobnosti a ochranné testy jsou v `test_native_sql_harness.md`. Kontrola počtů dbo tabulek a odstranění schématu běží i po neúspěšném native testu.

Regrese dlouhých JSON parametrů pokrývá native exact SQL pro 2/1536 rozměrů a native INSERT transport. Vektor s 1536 rozměry má >4000 znaků; musí zůstat celý parametrizovaný a projít `CAST(... AS NVARCHAR(MAX))` před `CAST(... AS VECTOR(...))`. ODBC17 jinak posílá NTEXT, jehož přímý převod SQL odmítá chybou 529. Mock INSERT test kontroluje výsledný SQL příkaz a nepoškozená data, nikoli skutečný cloudový zápis.

2026-10-14 byla tato chyba reprodukována čtecím SQLAlchemy/ODBC17 dotazem na Showcase a opravený společný native write/exact převod byl skutečně ověřen SELECTy pro 1536 rozměrů, identické i kolmé vektory (vzdálenosti 0/1). Přihlášení použilo existující Entra administrátorskou Azure CLI relaci bez Key Vaultu. Neprovádělo INSERT ani native fixture; cloudový zápis a životnost embeddingů tak zůstávají samostatně neověřené. Cílené vector-store + ANN testy s lokální SQL opt-in po opravě: **41 passed, 3 skipped** (native exact/ANN a SQLite varianta MSSQL-only timeoutu).

`tests/test_vector_store.py` přebírá izolované SQLite/MSSQL fixtures z `test_search_access.py`. Profilový repository vytváří vlastní tabulky s FK na UUID chunku a testovací fixture je před resetem svého schématu odstraňuje podle striktního serverového prefixu/UUID formátu. Vyhledávání místní reference streamuje všechny způsobilé vektory; nejlepší z 626 chunků musí být první z top 30. Tenant, dokumentové ACL, metadata, prázdný výsledek a méně než K výsledků se ověřují na skutečných SQL predikátech.

Další scénáře pokrývají dva modely stejného rozměru, třetí profil jiného rozměru, SHA-256 revizi textu, invalidaci všech indexů, FK cascade, rollback, odmítnutí chybných vektorů, neúplné pokrytí před aktivací a neměnnost katalogu/profilu. Backfill neoznačených historických embeddingů selže; explicitní fake-provider reembedding zachová původní JSON a opakovaný běh model nevolá. Pipeline test vyvolá chybu až po všech nových vector zápisech a kontroluje obnovení původního dokumentu, chunku a embeddingu.

SQL compilation test používá mssql dialect a kontroluje jediný finální TOP K, VECTOR_DISTANCE/CAST, parametrizované metadata, doc/chunk granty a revizi; nemůže dokázat provedení tohoto SQL na serveru. `RUN_NATIVE_SQL_TESTS=1` odemyká samostatnou fixture s `.env.native-test`, přesným očekávaným hostem/DB a požadavkem na prázdnou test DB. Test skutečných nativních typů/funkcí bez tohoto prostředí záměrně skipuje. Není to performance benchmark.

Příkazy jsou v `docs/development/search-slice-3-testing.md`; podmínky cloudového ověření v příslušném Azure handoffu. Nativní test byl v tomto pracovním běhu připraven, nikoli proveden.

Celá lokální sada se SQL Server opt-in prošla: 149 passed, 4 skipped. Po posledních guard/test doplněních prošla cílená sada vector-store/access/rechunk: 86 passed, 2 skipped. Skutečný lokální index měl pokrytí 3/3 a reálný modelový chat i dvě PDF citace HTTP 200; po startu se ukázky znovu neindexovaly. Native opt-in harness zahrnuje i 1536rozměrný zápis/dotaz do samostatného experimentálního profilu a odmítnutí jeho neúplné aktivace.

## Modelové profily

Náhradní splitter ve rollback regresi explicitně deklaruje vypnuté shrnutí; selhání po vector write nadále ověřuje původní transakční návrat.

Admin backfill nyní přijímá volitelný autorizační callback před dávkou a po modelovém volání. Dosavadní CLI běží beze změny bez callbacku; regresní revokaci/zachování vektorů ověřuje test_admin_indexes.
