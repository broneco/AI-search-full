# Testy přechodu hesel a oddělení od JWT

## Jednoduše

Testy ověřují, že uživatel může ponechat původní heslo, pokud operátor dodá doložený původní klíč. Úspěšný login uloží nový Argon2 hash, který už nezávisí na JWT. Chybný login, chybějící signing key nebo chyba databáze nesmí změnit heslo ani vydat token. Žádný test nepracuje s JHU/Azure.

## Technicky

`tests/test_password_migration.py` používá sdílené `access_engine/access_db/api_client` fixtures z `test_search_access`: SQLite s FK a opt-in unikátní lokální MSSQL test DB. Původní aplikace ani `ai_search_local` se nepřepisuje. Pure crypto testy ověřují per-hash random salt, Unicode, formát/délku, chybné heslo, explicitní legacy secret a odmítnutí pass-the-hash. Parser odmítá neplatný formát a extrémní parametry před native verifikací.

API testy mají odlišný nový JWT a legacy klíč. Dva uživatelé mají stejný email v jiných tenantech: upgrade se týká pouze aktuálního. Po odebrání legacy klíče a další rotaci JWT funguje moderní hash beze změny, starý token neplatí. Podpis legacy klíčem není přijímán. Testujeme wrong password/no key/wrong key/absent JWT, DB commit error s opravdovým rollbackem SQL UPDATE a nulový compare-and-set rowcount při konkurenční změně. Poslední scénář simuluje výsledek race guardu, ne skutečné souběžné požadavky. Registrace ukládá Argon2 a neuděluje požadované Management.

```powershell
$env:RUN_LOCAL_SQL_TESTS='1'
.venv\Scripts\python.exe -m pytest tests/test_password_migration.py -q --tb=short
```

Native SQL Server test zde není Azure acceptance; cloud KV čtení, skutečné legacy provenance, správa účtů a rollback zůstávají v JHU JWT handoffu. Náklady Argon2 při Azure souběhu nebyly měřeny; async routy využívají threadpool.
