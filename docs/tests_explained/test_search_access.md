# Testy bezpečného hledání — slice 2

## Jednoduše

Testy zajišťují, že silné zakázané výsledky nespotřebují místo oprávněným výsledkům, uživatel nezíská oprávnění pouhou hlavičkou ani registrací a sousední text či historie neprozradí chráněný obsah. Stejné případy se spouštějí na SQLite i skutečném lokálním SQL Serveru.

## Technicky

`tests/test_search_access.py` má vlastní engine/schema a nezávislou API session dependency. SQLite používá zapnuté FK. MSSQL varianta je opt-in `RUN_LOCAL_SQL_TESTS=1`, čte ignorovaný `.env.local`, kontroluje loopback a vytváří unikátní testovací databázi; nevstupuje do `ai_search_local` ani Azure. Tuto testovací DB po dokončení odstraní. Provider volání jsou v API scénářích mocked.

Scénáře pokrývají doc/chunk ACL před vector/keyword top K, cizí tenant a dev alias i rozdílný case/trailing space, metadata skalár/list/Unicode/boolean, SQL injection vstupy, přes 300 nepřístupných kandidátů, freshness/language, všechny varianty expansion, metadata prázdný výsledek, malformed ACL, chybný chunk tenant, ORM i Core bulk projekci, rollback, backfill a FK cascade. API případy ověřují ignorování X-User-* a zastaralých tokenových groups, nesprávný tenant/token/expiraci, soukromý cloudový signing key, bezpečnou registraci, 422 filtr a nepřístupné náhledy. Historie ověřuje i transitivní evidenci odpovědi bez nových výsledků a její redakci při revokaci skupiny.

`docs/development/search-slice-2-testing.md` obsahuje přesné příkazy a ruční akceptaci. Lokální MSSQL testy dokazují funkčnost SQL predikátů, ne Azure SQL Basic výkon, nativní vektory či DiskANN.

Souborové regrese ověřují také odmítnutí HTTP čtení mimo data/ a Blob container jiného tenantu. Finální celá sada s lokální MSSQL variantou 2026-10-14: 125 passed, 2 skipped (vědomě vypnuté skutečné Azure modelové calls).

## Lokální ukázky a ručně nalezená regrese

Hybridní test nyní spouští skutečný SQL keyword rank přes `_apply_filters` až do score addition. Na MSSQL ověřuje vstupní Decimal, převod na float, očekávané skóre/pořadí a JSON serializaci, včetně nulového ranku. Tím zachytí ručně hlášené `float * Decimal`, které testy samostatných větví nepokrývaly.

Seeder testy používají stejné izolované databáze a fake provider s dvourozměrným vektorem; modelová API nevolají. Ověřují dvě PDF, dokumentový režim, češtinu v SQL, veřejné granty, zachování uživatelského dokumentu, opakovaný start bez embeddingů, opravu chybějícího PDF, obnovu smazaného dokumentu, změnu profilu stejného rozměru, rollback po druhém insertu a odmítnutí neúplných/chybných vektorů. Další testy pokrývají chybějící credentials, nesoulad profilu a zakázaný cloudový cíl. SQL Server DDL regrese převede starý VARCHAR obsah, zachová existující řádky a ověří nové české zápisy; na SQLite je tato konkrétní migrace skipped.

Po tomto doplnění celá sada s `RUN_LOCAL_SQL_TESTS=1`: **138 passed, 3 skipped**. Dvě skip jsou opt-in Azure modelové testy a třetí je Unicode MSSQL DDL při SQLite běhu. Samostatný smoke mimo pytest ověřil skutečné Azure embeddingy v ai_search_local, opakovaný seed bez nových embeddingů, odpověď chatu HTTP 200 se správnou hranicí 40 kreditů a obě autentizované PDF HTTP 200. Neprokazuje obecnou kvalitu retrievalu ani výkon Azure Basic.

Slice 3 doplnil explicitně vytvořený profilový index pro úspěšné chatové security testy a fake provider s odpovídajícími dvěma rozměry. DB fixture při svém resetu odstraňuje také vlastní dynamické profilové tabulky, aby jejich FK neblokovaly drop chunk schématu. Demo rollback test nyní simuluje selhání společného vector repository a idempotence vyžaduje i platný profilový vector záznam, nejen starý JSON. Význam tenant/ACL kontrol zůstává stejný.

## Modelové profily

Chatové regrese používají bound modelového providera a syntetické připojení, aby skutečně ověřovaly ACL bez síťového LLM volání.

Embeddingová slice ověřuje, že změna demo profilu vytvoří další vektory nad stejnými chunk UUID a zachová původní legacy provenance. Rollback simuluje selhání druhého zápisu vektorů; obě původní sady zůstanou konzistentní. Restart po aktivaci Nomic nevyžaduje přepsání demo dokumentů.
