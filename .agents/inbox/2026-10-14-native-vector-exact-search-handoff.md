# Azure Deployment Handoff: Slice 3 — native VECTOR a přesné hledání

- Status: waiting-for-human
- Created: 2026-10-14
- Related task: schválený search roadmap, slice 3
- Related ADR: `docs/adr/ADR-0023-profile-index-catalog-and-exact-vector-storage.md`
- Related branch/PR: současný pracovní strom, bez nového commitu nebo deploymentu

## Proč handoff existuje

**Aktualizace 2026-10-14:** actual native exact test již prošel na existujícím Showcase přes Entra CLI ve schváleném izolovaném schématu; raw VECTOR zápisy/1536CAST, pořadí za625, profily, ACL/metadata/tenant, update/rollback/cascade byly vykonány. Schéma bylo uklizeno a původní dbo počty zachovány. Následně prošel i ANN v3 lifecycle. Tento handoff zůstává čekající kvůli migraci/backfillu a smoke běžné cloudové aplikace, nikoli kvůli chybějícímu syntetickému native důkazu. Starší empty-only cesta níže je pouze alternativa; aktuální procedure/výsledek viz slice5 handoff. Další zásahy potřebují nové konkrétní schválení.

Lokální SQL Server 2022 nepodporuje VECTOR/VECTOR_DISTANCE. Místní JSON reference, transakční testy a SQL compilation neposkytují důkaz nativního Azure chování. Podle `.agents/rules/azure-deployment-handshake.md` vytváří Azure zdroje a provádí migraci člověk; agent neprovisionoval ani nemigroval Azure. Slice 3 je implementovaný a lokálně ověřený, cloudová akceptace čeká na skutečný native test.

## Cíl

Na oddělené Azure testovací DB prokázat native float32 VECTOR, transakční synchronizaci, aktuální revize a všechny prefiltry před přesným TOP K. Poté na samostatném staging korpusu vytvořit a aktivovat jeden úplný profilový index. DiskANN se zde nevytváří.

## Zdroje a oprávnění

| Zdroj | Akce | Nastavení | Poznámka |
| --- | --- | --- | --- |
| Azure SQL testovací databáze na zvoleném serveru | člověk vytvoří/zvolí prázdnou DB, např. ai_search_vector_test | název obsahuje test; žádná produkční data | integrační fixture požaduje prázdné dbo schéma a po testu odstraní své tabulky |
| Oddělená staging SQL DB/korpus | člověk připraví až po syntetickém native testu | compatibility ≥130 pro OPENJSON; potřebné slice 2 ACL a Unicode migrace | neplést se syntetickou DB, která má být prázdná |
| SQL migrační identita | DDL/SELECT/INSERT/UPDATE/DELETE | standardní dbo schéma, CREATE TABLE/REFERENCES a tvorba PK/unique/FK | runtime potřebuje DML a SELECT nad katalogem i konkrétními vector tabulkami, nemusí tvořit tabulky |
| Existující Azure embedding deployment | pouze potvrdit model/revizi/rozměr/prefixy | první profil 1536 float32 | cílový profil musí odpovídat skutečnému modelu; nepřebírat historické vektory podle dnešní konfigurace |

Neměnit automaticky Basic 5 DTU ani Container App 0,5 CPU / 1 GiB. Člověk potvrdí kapacitu vlastní testovací DB. Microsoft dokumentace uvádí [VECTOR dostupnost a limity](https://learn.microsoft.com/en-us/sql/t-sql/data-types/vector-data-type?view=sql-server-ver17) a [VECTOR_DISTANCE exact semantics](https://learn.microsoft.com/en-us/sql/t-sql/functions/vector-distance-transact-sql?view=sql-server-ver17); dostupnost/funkčnost na zvoleném cíli ověřit přímo:

```sql
SELECT DB_NAME() AS database_name, compatibility_level
FROM sys.databases WHERE name = DB_NAME();
DECLARE @a VECTOR(2) = '[1,0]';
DECLARE @b VECTOR(2) = '[0,1]';
SELECT VECTOR_DISTANCE('cosine', @a, @b) AS distance;
```

## Konfigurace a secrets

Používají se existující `AZURE_SQL_HOST/PORT/DB/USER/PASSWORD/DRIVER`, `DATABASE_BACKEND=azure_sql`, přesný TENANT_ID a existující embeddingové modelové/profile proměnné. Žádné tenant env ani Azure nastavení agent neměnil. Heslo SQL a Azure OpenAI key patří do Key Vault/ignorovaného lokálního souboru; sem ani do Git je nekopírovat. Test harness vyžaduje samostatný ignorovaný `.env.native-test` se SQL credentials, `RUN_NATIVE_SQL_TESTS=1` a přesné `NATIVE_SQL_EXPECT_HOST/DB`. Neexportovat lokální AZURE_SQL proměnné do tohoto terminálu.

## Validace člověkem — prázdná syntetická DB

Postup je v `docs/development/search-slice-3-testing.md`. Spustit:

```powershell
$env:RUN_NATIVE_SQL_TESTS = "1"
$env:NATIVE_SQL_EXPECT_HOST = "<potvrzený host>"
$env:NATIVE_SQL_EXPECT_DB = "<potvrzená prázdná test DB>"
.venv\Scripts\python.exe -m pytest tests/test_vector_store.py -k native_vector_end_to_end -q --tb=short
```

Fixture před zápisem odmítne jiný host/DB nebo neprázdné dbo schéma. Vytvoří pouze testovací app tabulky a serverově pojmenované native tabulky, po dokončení je odstraní; samotnou DB nemaže. Test obsahuje přes 625 slabších chunků, doc i chunk ACL, cizí tenant, metadata, prázdný/méně než K výsledek, odmítnutí jiné identity profilu/rozměru, změnu textu, update embeddingu, rollback a cascade delete. Nepotřebuje modelové API. Pokud server odmítne VECTOR, FLOAT32 CAST, FK nebo query, vrátit přesnou redigovanou diagnostiku; neaktivovat JSON fallback v Azure.

## Migrace staging korpusu — až po úspěšném native testu

1. Dokončit slice 2 handoff včetně Unicode dodatku, serverových skupin a soukromého JWT_SECRET. Připravit zálohu/snapshot a zastavit všechny ingestující/reindexující i přímé SQL zápisy. Ověřit přesné doc/chunk tenanty.
2. Potvrdit skutečný binding embedding deploymentu a deklarovaný modelový profil. Současná konfigurace nedokazuje model původních embeddingů. Standardní cesta znovu vytvoří embeddingy současných chunků bez extrakce a zachová staré JSON vektory. Dávky spouštět postupně.
3. V terminálu s konfigurací vybraného staging cíle spustit read-only audit: `.venv\Scripts\python.exe migrate_search_vectors.py`.
4. Člověk provede explicitní provisioning/backfill/aktivaci se skutečnými ne-secret hodnotami:

```powershell
.venv\Scripts\python.exe migrate_search_vectors.py --create --reembed --activate `
  --expect-host <HOST> --expect-db <DB> --expect-tenant <EXACT_TENANT>
```

CLI vytvoří katalog a jednu native profilovou tabulku s integer identity clustered PK, unikátním chunk UUID FK CASCADE a VECTOR(1536). Backfill komituje po dávkách 32. Po chybě pokračovat s `--index <vrácené UUID>` místo nového `--create`; stejné aktuální revize se přeskočí. Aktivace odmítne neúplné pokrytí. `--proven-legacy` nepoužívat bez nezávisle doložené per-chunk provenance a správné revize.
5. Zkontrolovat native datový typ/sloupce přes sys.columns, úplnost pokrytí a správné pořadí, oprávnění runtime identity a odpovědi API s PDF citacemi. Přímé SQL content update obcházející repository nesmí běžet: musí rovněž měnit content_hash a invalidovat embeddingy. Při nasazení nového backendu bez aktivního kompatibilního katalogu chat vrátí 503, nikoli starý omezený scan.
6. Teprve po staging akceptaci domluvit samostatný produkční rollout. Při nejasném původu dat nebo výkonnostní regresi nepřepínat produkci. Slicy 4–5 se tímto handoffem neaktivují.

## Návrat

Předchozí index zachovat. Návrat na jeho UUID přes CLI `--index <PREVIOUS_UUID> --activate --expect-*` vyžaduje úplné pokrytí aktuálního korpusu a odpovídající konfiguraci provideru; když je starý profil neúplný, nejprve explicitně doplnit embeddingy jeho modelem. Pouhá změna answer LLM nevyžaduje reembedding.

Staré JSON embeddingy zůstávají pro audit/návrat image, nejsou automatickým fallbackem nové Azure retrieval cesty. Návrat starého image může znovu zavést cap/profilové slabiny; omezit jej na izolované testování nebo operátorsky řízený návrat. Nový runtime při SQL chybě neskenuje podruhé korpus jinou metodou.

## Hodnoty vrácené člověkem

```yaml
resource_group:
sql_host:
empty_native_test_database:
staging_database:
exact_tenant_id:
compatibility_level:
native_probe_passed:
native_pytest_passed:
native_vector_dimensions:
index_id:
embedding_profile_id:
coverage_current:
coverage_total:
runtime_permissions_verified:
api_and_citations_verified:
notes: # jen redigované chyby, žádné secrets
```

## Zbývající hranice

Aktualizace pořadí 2026-10-14: uživatel požádal odložit Azure a maximalizovat lokální testy. Tento handoff zůstává čekající, ale neblokuje lokální implementaci slice 4. Azure exact/ANN testy se provedou souhrnně ve slice 5 před cloudovou migrací/aktivací. Lokální native exact na odděleném SQL Server 2025 Docker je plánovaný mezikrok, nikoli hotové nebo provedené ověření.

Výkon na Basic 5 DTU není změřený. Native SQL fixture nepokrývá poskytovatele reálných modelů ani zátěž; runtime correctness/filtry a transakce musí být potvrzené před cloudovou aktivací exact/ANN. Kvalitativní/performance brány zůstávají v slice 5.
