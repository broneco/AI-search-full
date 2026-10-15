# ADR-0023: Profilový katalog, transakční embeddingy a přesné hledání

- Status: accepted (implementation; native Azure integration pending)
- Date: 2026-10-14
- Owners: AI Search Core Team

## Kontext

Původní vektorová větev načítala nejvýše 600 kandidátů a srovnávala JSON vektory v backendu bez databázově doloženého profilu. To neposkytovalo úplné hledání ani bezpečné oddělení modelů se stejným rozměrem. Slice 2 již poskytuje společné SQL prefiltry a ACL projekce.

## Rozhodnutí

- `embedding_profiles` ukládá immutable definici a SHA-256 identitu; `search_indexes` váže jeden tenantí korpus `tenant-chunks-v1` na profil a fyzickou tabulku. `active_search_indexes` má jeden záznam na SHA-256 přesného tenant ID; nedochází ke kolizím podle case/padding SQL stringů. Starší indexy zůstávají pro návrat.
- Každý index má `chunk_vectors_<serverové UUID>` s celočíselným identity clustered PK, unikátním UUID FK na chunk, `input_revision` a embeddingem. Název je ověřován proti index UUID, ne převzat od klienta. Texty/ACL jsou stále pouze v dokumentových a chunkových tabulkách.
- Azure používá skutečné `VECTOR(dimensions)` a explicitní CAST parametrizovaného JSON při zápisu; první profil používá 1536 float32. Tento slice podporuje float32 do 1998 rozměrů a odmítá větší profil bez zkracování. Float16 je další samostatné rozhodnutí, nikoli automatický fallback.
- Lokální SQL Server 2022 a SQLite používají oddělené profilové tabulky s JSON. Lokální reference streamuje všechny způsobilé vektory po 200 řádcích a drží pouze K vítězů. Azure nikdy nepřepne na tento backend při chybě nativního SQL.
- Runtime vektorové/hybridní hledání vyžaduje explicitní profil provideru shodný s aktivním indexem; chat nesoulad odmítne před modelovým voláním. Starý neprofilovaný helper je dostupný pouze izolovaným unit fixtures v APP_ENV=test, nikdy runtime API.
- Native exact je jeden parametrizovaný SELECT s VECTOR_DISTANCE('cosine'), aktuální revizí vstupu, tenant/doc/chunk ACL, metadata a freshness WHERE před finálním TOP K. Nepoužívá ANN ani limit kandidátů. Do backendu přecházejí pouze vítězné texty/skóre, nikoli všechny vektory.
- `write_chunks` je společný repository pro ingest endpoint, souborovou pipeline, rychlou reindexaci a lokální ukázky. Chunk + JSON + profilový embedding + ACL granty se zapisují v jedné transakci; parent dokument již není commitnutý před chunky. Náhrada dokumentu ponechá původní verzi do vytvoření nových embeddingů a SQL selhání obnoví původní document/chunk/vector stav.
- SHA-256 skutečného uloženého textu je revize vstupu. ORM změna obsahu jej přepočítá a ve stejné transakci odstraní vektory ze všech indexů. FK cascade řeší mazání včetně bulk delete. Metadata nebo ACL změna sama nepřepočítává embedding. Externí přímé SQL content zápisy nejsou podporovanou ingestující cestou: musejí také aktualizovat revizi a zneplatnit embeddingy; samotné přepsání textu mimo repository není bezpečné.
- Backfill explicitně buď vytvoří nové embeddingy současných chunků, nebo použije legacy vektor s operátorem doloženou per-chunk identitou profilu a odpovídající revizí. Aktuální konfigurace nestačí jako důkaz. Původní JSON backfill nepřepisuje a neextrahuje dokumenty znovu. Dávky po 32 komitují samostatně a opakovaný běh přeskočí aktuální revize; změna chunku během volání modelu odmítne dávku.
- Aktivace vyžaduje úplné pokrytí korpusu a zastavené zápisy. Azure provisioning/aktivace je explicitní lidský CLI krok, startup nevytváří cloudový katalog. Nový lokální korpus s jedním úplným indexem se aktivuje automaticky; neoznačená starší lokální data vyžadují explicitní backfill.

## Ověření a hranice

Dodatek 2026-10-14 podle preference uživatele: Azure test lze odložit do souhrnného exact/ANN ověření slice 5 a pokračovat lokálním vývojem slice 4. Cloudová migrace/aktivace a označení Azure akceptace stále vyžadují skutečný cloudový test. Jako nejbližší lokální mezikrok je plánovaný oddělený SQL Server 2025 Docker pro native exact; současný SQL 2022 volume se automaticky nemění. Tato lokální native fixture zatím není implementovaná.

SQLite a lokální MSSQL ověřují transakce, profily stejného/jiného rozměru, chyby dávky, prefiltry, úplné hledání přes 625 dřívějších slabších chunků, cascade a rollback náhrady dokumentu. SQL compilation test ověřuje skutečný native statement. Opt-in native test vyžaduje vyhrazenou prázdnou Azure DB, očekávaný host/název a ruční handoff; zde nebyl spuštěn.

Dokumentace Microsoftu potvrzuje [VECTOR](https://learn.microsoft.com/en-us/sql/t-sql/data-types/vector-data-type?view=sql-server-ver17) a [přesný VECTOR_DISTANCE](https://learn.microsoft.com/en-us/sql/t-sql/functions/vector-distance-transact-sql?view=sql-server-ver17). Není to důkaz výkonu Basic 5 DTU. Nativní end-to-end ověření je podmínka cloudové akceptace slice 3. Slice 4 a 5 nejsou zahájené.
