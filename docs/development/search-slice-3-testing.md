# Slice 3: profilový index a úplné přesné hledání

## Lokální spuštění

Spusť Docker a `./dev.ps1 -Action start-db`, poté `./dev.ps1 -Action backend` a frontend. Nový lokální korpus s ukázkami Aurora se s úplným profilem aktivuje automaticky. V aktuálním pracovním setupu byl index již vytvořen a ověřen s pokrytím **3/3 chunků**; další start hlásil 0 nově indexovaných ukázek. Vlastní dokument zůstal zachován.

V novém chatu vyzkoušej otázky z [lokálního návodu](local-setup.md), otevři PDF citaci a obnov stránku po restartu. Hledání používá celý způsobilý aktivní profil, ne prvních 600 vektorů. Lokální SQL Server 2022 používá JSON referenci; neověřuje native VECTOR ani výkon Azure.

## Jednorázový přechod starších lokálních dat

Pokud backend hlásí chybějící index nebo neúplné pokrytí, zastav backend a všechny ingestující úlohy. Následující příkazy míří jen na lokální SQL; `.env.local` nikdy nepřepiš Azure adresou:

```powershell
$env:APP_ENV = "local"
.venv\Scripts\python.exe migrate_search_vectors.py
```

Audit nic nevytváří. Pokud neexistuje index, vytvoř jej a přepočítej embeddingy existujících chunků bez nové extrakce:

```powershell
.venv\Scripts\python.exe migrate_search_vectors.py --create --reembed --activate `
  --expect-host 127.0.0.1 --expect-db ai_search_local --expect-tenant dolphin
```

Pro existující index použij jeho UUID z auditu místo `--create`:

```powershell
.venv\Scripts\python.exe migrate_search_vectors.py --index <INDEX_UUID> --reembed --activate `
  --expect-host 127.0.0.1 --expect-db ai_search_local --expect-tenant dolphin
```

Očekávaný host/DB/tenant musí odpovídat skutečné konfiguraci; uprav pouze tenant, pokud máš jiný lokální tenant. Úloha volá nakonfigurovaný embeddingový model a zachovává původní JSON. Backfill komituje po dávkách, takže je možné pokračovat po selhání; aktivace s neúplným pokrytím odmítne přepnutí. `--proven-legacy` je pouze pro operátorem ověřenou provenance v každém chunku; konfigurace ani samotná délka vektoru nejsou důkaz. Standardně použij `--reembed`.

Pokud změníš model, rozměr, revizi nebo prefixy, vytvoř nový index. Starý profil i index jsou neměnné. Runtime odmítne záměnu profilu i při stejném rozměru. V běžném dotazu se nevolají všechny modely a nic se automaticky nezkracuje.

## Automatické testy

```powershell
$env:RUN_LOCAL_SQL_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests/test_vector_store.py tests/test_search_access.py tests/test_rechunk.py -q --tb=short
Remove-Item Env:RUN_LOCAL_SQL_TESTS
```

Testy používají izolovanou SQLite a novou dočasnou SQL Server DB, nikdy nemažou ai_search_local. Modely jsou fake; reindexační regrese nyní nevolá Azure. Nativní test zůstává skipped bez dalšího explicitního nastavení.

## Native Azure integrační brána

**Aktualizace 2026-10-14:** na přání uživatele se Azure test nyní odkládá do souhrnného cloudového ověření ve slice 5, před migrací/aktivací v Azure. Následující příkazy jsou připravený budoucí postup, nikoli povinný krok pro pokračování v lokálním vývoji. Aktuální fixture stále míří do Azure; lokální nativní varianta pro oddělený SQL Server 2025 Docker je doporučený další mezikrok, zatím není implementovaná. Dosavadní SQL Server 2022/JSON testy zůstávají funkční.

Postup a bezpečnostní hranice jsou v [handoffu slice 3](../../.agents/inbox/2026-10-14-native-vector-exact-search-handoff.md). Pro test vytvoř samostatnou **prázdnou** Azure SQL DB; nesmí obsahovat produkční ani ruční testovací dokumenty. Fixture v ní vytvoří a následně odstraní pouze své schema tabulky a profilové vector tabulky, celou Azure DB nemaže.

V ignorovaném `.env.native-test` nastav existující `AZURE_SQL_HOST`, `AZURE_SQL_DB`, `AZURE_SQL_USER`, `AZURE_SQL_PASSWORD`, `AZURE_SQL_DRIVER` a případně port. Nic z toho necommituj. V novém terminálu bez exportovaných lokálních AZURE_SQL proměnných:

```powershell
$env:RUN_NATIVE_SQL_TESTS = "1"
$env:NATIVE_SQL_EXPECT_HOST = "<potvrzený testovací SQL host>"
$env:NATIVE_SQL_EXPECT_DB = "<potvrzená prázdná DB s test v názvu>"
.venv\Scripts\python.exe -m pytest tests/test_vector_store.py -k native_vector_end_to_end -q --tb=short
```

Test nepoužívá Azure model ani deployment. Ověřuje skutečný VECTOR write/CAST, přesné pořadí nad všemi chunky, metadata a tenant/doc ACL před top K, záměnu profilů, revizi vstupu, update/rollback a cascade delete. Samostatné lokální regrese pokrývají i chunk ACL, všechny expansion režimy a reindexaci. Azure výsledek musí vrátit člověk před cloudovou akceptací; výkonový benchmark Basic 5 DTU patří až do slice 5.
