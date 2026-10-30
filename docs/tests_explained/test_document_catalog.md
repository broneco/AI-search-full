# Přehled dokumentů a dostupnost při pomalém SQL

Testy v [test_document_catalog.py](../../tests/test_document_catalog.py) ověřují:

- Dvě dávková čtení místo jednoho COUNT dotazu pro každý dokument; cena v počtu SQL požadavků neroste s počtem dokumentů.
- Přesné tenanty včetně velikosti písmen a koncových mezer, dokumentové i chunkové ACL a nulové počty u prázdných dokumentů. Cizí tenantové chunky nesmějí zvyšovat počty.
- Zablokovaný dokumentový přehled, retrieval a cloudové konfigurace nezablokují souběžnou HTTP health odpověď. Test používá synchronizační události, nikoli očekávání rychlosti počítače.
- SQL chyba vrací bezpečnou JSON odpověď 503 bez textu SQL, parametrů a údajů ovladače.

SQLite běží vždy. `RUN_LOCAL_SQL_TESTS=1` přidává izolovanou lokální SQL Server databázi vytvořenou a odstraněnou pouze touto fixture. Nejde o test změny produkčních dat, Azure native VECTOR ani benchmark p95.

```powershell
$env:RUN_LOCAL_SQL_TESTS='1'
.venv/Scripts/python.exe -m pytest tests/test_document_catalog.py -q
```
