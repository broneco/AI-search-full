# Izolované native SQL integrační testy

## Jednoduše

Skutečné Azure testy mohou běžet v existující Showcase databázi, aniž by přepisovaly její dokumenty a uživatele. Pro každý běh vytvoří vlastní unikátně pojmenované schéma, v něm testovací tabulky a syntetická data. Po testu své objekty odstraní. Přihlášení používá již existující Microsoft Entra účet přes Azure CLI, bez Key Vaultu a modelových API.

## Technicky

`tests/native_sql_harness.py` vyžaduje název `ann_test_<32 lowercase hex>`. Schéma musí být nové; CREATE na existujícím názvu selže a cleanup se pak nesmí spustit. SQLAlchemy schema_translate_map přesměruje ORM i FK/DDL z None/dbo do test schématu. Testovací before_cursor_execute listener úzce překládá schema-qualified vector identifikátory, ANN JOINy a grant subquery tabulky v produkčním textovém SQL. Parametry metadata/ACL se nepřepisují; pouze sys.vector_indexes OBJECT_ID parametr dostane skutečné test schéma. Produkční algoritmus/filtry se nemění.

`azure_cli_engine` získává nový SQL token pro připojení přes capture_output; token je pouze v paměti, balený UTF16-LE/ODBC1256. TLS zůstává Encrypt=yes/TrustServerCertificate=no, Driver18 nebo dostupný17, bez UID/PWD. Engine hide_parameters omezuje chybový výpis. Helper je pouze v tests, nepoužívá ho runtime aplikace.

`test_native_sql_harness.py` kontroluje odmítnutí dbo/injekce/chybného prefixu před připojením, zachování bind hodnot, scoped překlad raw SQL i FK/DDL a skutečnou lokální MSSQL izolaci/úklid po výjimce. Další MSSQL test prokazuje, že cizí existující schéma nebude převzato ani smazáno. SQLite varianty schema DDL záměrně přeskočí.

Rozšířená `native_db` fixture ponechává původní empty-only cestu. Nová cesta vyžaduje RUN_NATIVE_SQL_TESTS=1, explicitní NATIVE_SQL_EXPECT_HOST/DB, NATIVE_SQL_ISOLATED_SCHEMA a NATIVE_SQL_ALLOW_EXISTING=1. ANN navíc vyžaduje RUN_NATIVE_ANN_TESTS=1. Runtime nastavení backendu/tenantu se mění jen v procesu pytest. Fixture po úspěšném testu porovná pouze seznam a agregované počty dbo tabulek před/po; nejde o záruku neměnnosti všech hodnot při souběžném externím provozu. Testy samy zapisují jen do vlastního schématu. Cleanup nejdřív odstraní rozpoznané vector tabulky, pak vlastní ORM tabulky a schéma; neznámé objekty znamenají zastavení cleanup pro ruční review. Base.metadata.drop_all se smí použít pouze na přeloženém enginu, nikdy nad aplikačním dbo.

Před Azure zápisy je nutné uživatelské schválení konkrétního cíle a rozsahu. Izolovaná funkční integrace neznamená migration/deployment aplikace ani recall/performance akceptaci. Postup a skutečný stav viz slice 5 handoff.

Dne 2026-10-14 byl tento přesný Showcase rozsah schválen při spuštění nástroje. Skutečný native exact test i následný native ANN test prošly; každý běh (včetně předchozích selhání) ověřil odstranění vlastního schématu a stejné původní dbo counts. Poslední cílená lokální sada po opravách: 55 passed / 7 expected skips. Entra/KV/RBAC/cloud runtime se neměnily.

Fulltext rozšíření v0.1.4: izolovaný listener překládá také CONTAINSTABLE zdroj a jeho vnější chunks/documents i korelované granty. ORM hydratace dál používá schema_translate_map; hodnoty parametrů se nepřepisují.

ANN v0.1.4 překládá i FROM chunks/INNER JOIN documents uvnitř parametrizovaného sp_executesql batch pro úplnou eligibility tabulkovou proměnnou. Parametry zůstávají na vnějším batch a nemění se; @eligible je jen lokální proměnná bez trvalého objektu a bez samostatného cleanup.
