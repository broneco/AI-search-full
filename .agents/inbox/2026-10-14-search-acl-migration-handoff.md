# Azure handoff: Slice 2 — ACL grant tabulky a ověřená identita

- Status: waiting-for-human
- Created: 2026-10-14
- Related ADR: `docs/adr/ADR-0021-authoritative-search-identity-and-relational-acl.md`
- Scope: připravené k ověření v oddělené Azure SQL testovací databázi; žádná Azure změna nebyla provedena agentem.

## Účel a pořadí

Lokální SQL Server testy nenahrazují ověření Azure SQL oprávnění a aktuálního tier. Před nasazením slice 2 je nutný audit přesných tenantů, zřízení ACL tabulek a jejich naplnění. SQL Basic 5 DTU a Container App 0,5 CPU / 1 GiB neměnit automaticky. Nepouštět migraci na produkci jako první ověření.

1. Člověk zvolí oddělenou Azure SQL testovací DB a dodá její ne-secret host, database, přesný TENANT_ID a resource group. Zvolí identitu s právem vytvořit tabulky/indexy/FK a zapisovat grant tabulky. DB compatibility level musí být ≥130. Pro runtime jsou potřeba SELECT/INSERT/UPDATE/DELETE na nových grant tabulkách pro odpovídající aplikační identitu.
2. Připravit bezpečná testovací data v documents/chunks/users; nevkládat secrets do Git souborů. Ověřit user/document/chunk tenant ID. Oproti starému kódu se nepoužívají automatické aliasy base/dev/prod ani email fallback. Dokumenty s legacy aliasem mohou přestat být viditelné; jejich opravu musí operátor opřít o ověřený původ. Skript odmítne rozdílný tenant chunku a rodiče a sám hodnoty nepřepíše.
3. Zastavit ingestaci a všechny ACL/zápisové úlohy pro cílovou DB na dobu migrace. Uchovat snapshot/backup a předchozí image. Source JSON ACL a embeddings se nemění.
4. Pro dev/prod musí existovat soukromý `JWT_SECRET`, nastavený bezpečnou konfigurací Container App/secretem. Hodnotu sem nepsat. Výchozí veřejně známý klíč je povolen pouze pro local/test. Pokud se klíč mění, tokeny se zneplatní; současné password_hash závisí na JWT_SECRET, proto se musí bezpečně obnovit také hashe/reset hesel existujících uživatelů. Bez této přípravy budou loginy nefunkční. V cloudu se automaticky nevytvářejí demo účty a registrace vyžaduje Management. Prověřit existující účty vzniklé historickým demo seedingem nebo veřejnou registrací, jejich členství v organizaci a serverové groups; známá demo hesla bezpečně resetovat nebo testovací účty deaktivovat podle firemních pravidel. Žádné existující cloudové účty agent nemaže. Správce musí mít po změně platný účet; jeho skupiny přidělí serverový operátor.
5. V lokálním terminálu s vybranou necommitovanou tenantí konfigurací spustit audit. `APP_ENV`/`TENANT_ID` nastavit před importem aplikace. Nikdy nenahradit `.env.local` cloudovou SQL adresou.

```powershell
# Nastav APP_ENV a TENANT_ID pro skutečný vybraný testovací cíl.
.venv\Scripts\python.exe migrate_search_acl.py
```

6. Zkontrolovat vypsaný host/database/tenant, počty dokumentů podle tenantů a nulový počet chunk/document tenant nesouladů. Teprve potom člověk spustí apply s přesnými ne-secret hodnotami:

```powershell
.venv\Scripts\python.exe migrate_search_acl.py --apply --expect-host <HOST> --expect-db <DATABASE> --expect-tenant <TENANT_ID>
```

DDL vytváří pouze `document_acl_grants`, `chunk_acl_grants`, jejich PK/indexy/FK. Backfill běží v jedné transakci a čte po dávkách bez paralelního čtení a zápisu přes otevřený ODBC kurzor. Je idempotentní; grant projekci explicitně obnovuje. ACL chybějící/{} či [] je legacy veřejný User grant, Public se mapuje na User, malformed ACL nemá granty.

7. Nasadit odpovídající verzi backendu i obou frontendů do testovacího prostředí. Ověřit platný bearer token, odmítnutí cizího tenantu a X-User-* spoofingu, aktuální DB skupiny po jejich změně, obě ACL před top K a zakázané sousedy. PDF/preview celého dokumentu se nesmí otevřít při přístupu jen k části chunků. Staré assistant odpovědi se z bezpečnostních důvodů redigují; nový chat má zachovat citace a transitivní ACL provenance.
8. Teprve po tomto potvrzení domluvit produkční rollout. Operátor vrátí stav kontroly a ne-secret názvy, počty a výsledky, ne klíče/connection stringy/tokeny. Tenant env soubory zde nebyly upraveny a stávající key parity se nemění.

## Validace a návrat

Sada `tests/test_search_access.py` obsahuje oddělené SQLite a lokální SQL Server scénáře; její RUN_LOCAL_SQL_TESTS fixture záměrně povoluje pouze localhost a není určena k připojení na Azure. Pro Azure zopakovat API/SQL scénáře z `docs/development/search-slice-2-testing.md` nad bezpečnými testovacími daty a potvrdit chování v odpovídajícím tenant/tier.

Návrat image ponechá grant tabulky jako nepoužívané; source JSON je původní. Starý backend znovu zavádí známé slabiny identit/ACL, proto tento fallback použít jen pro izolované testování nebo se současným vypnutím veřejného přístupu. Bez soukromého signing klíče nepovolovat cloudovou autentizaci. Obnovení původních password_hash/tokenů je samostatná operátorská práce při případné rotaci JWT_SECRET.

## Dodatek 2026-10-14: Unicode před cloudovým nasazením

Lokální MSSQL test prokázal ztrátu českých znaků v původním VARCHAR/TEXT. Nové mappingy předpokládají Unicode u čtyř polí: `documents.title` a `chat_threads.title` jako NVARCHAR(512), `chunks.content` a `chat_messages.content` jako NVARCHAR(MAX). Startup tyto existující sloupce opravuje **pouze lokálně**; `migrate_search_acl.py` jejich typy nemění.

Člověk musí před cloudovým rolloutem provést a ověřit samostatný převod nejprve na oddělené Azure testovací DB:

1. Potvrdit skutečný host/DB, zálohu a zastavení zápisů. Zkontrolovat typy sloupců přes sys.columns a existující indexy/závislosti. Pokud sloupce už mají vhodný NVARCHAR typ/délku, nepřevádět je znovu.
2. Při potřebném převodu `chunks.content` zachytit původní definici full-text indexu, katalog, key index, jazyky, stoplist a další nastavení. Pokud index existuje, nejprve jej odebrat a po převodu obnovit podle zachycené definice. [DROP FULLTEXT INDEX](https://learn.microsoft.com/en-us/sql/t-sql/statements/drop-fulltext-index-transact-sql?view=sql-server-ver17) vyžaduje ALTER oprávnění; [CREATE FULLTEXT INDEX](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-fulltext-index-transact-sql?view=sql-server-ver17) spouštět mimo uživatelskou transakci. Automatický lokální helper neslouží jako cloudový migrační skript.
3. Pro existující standardní dbo schéma je cílové DDL následující; operátor je provede po vyřešení závislostí a po potvrzení konkrétního testovacího cíle:

```sql
ALTER TABLE dbo.documents ALTER COLUMN title NVARCHAR(512) NOT NULL;
ALTER TABLE dbo.chunks ALTER COLUMN content NVARCHAR(MAX) NOT NULL;
ALTER TABLE dbo.chat_threads ALTER COLUMN title NVARCHAR(512) NOT NULL;
ALTER TABLE dbo.chat_messages ALTER COLUMN content NVARCHAR(MAX) NOT NULL;
```

4. Ověřit uchování existujících řádků, nový zápis a přečtení `Studijní oddělení: řádné žádosti, čtenáři, příště.`, hybridní chat, uloženou historii a stav/populaci obnoveného full-text indexu. Převod nezrekonstruuje dříve ztracené znaky; původně poškozené dokumenty vyžadují nové načtení z originálu a nové embeddingy s doloženým profilem.
5. Teprve po testovacím potvrzení domluvit produkční rollout a údržbové okno; tento slice neposkytuje měření nákladů DDL nad cloudovým korpusem. Návrat starého image ponechá Unicode sloupce; nezmenšovat je zpět na VARCHAR, protože by znovu poškodil text.

Do odpovědi přidej pouze ne-secret `unicode_columns_verified` a `fulltext_restore_verified`. Ukázky Aurora se do Azure neseedují.

## Odpověď člověka (ACL)

```yaml
resource_group:
sql_host:
sql_database:
tenant_id:
compatibility_level:
chunk_tenant_mismatch_count:
document_acl_grant_count:
chunk_acl_grant_count:
private_jwt_secret_configured: # ano/ne, nikdy hodnota
server_groups_validated:
api_acceptance_passed:
```
