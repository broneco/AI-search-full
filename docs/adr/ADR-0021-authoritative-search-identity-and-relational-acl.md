# ADR-0021: Ověřená identita a relační ACL před výběrem výsledků

- Status: accepted
- Date: 2026-10-14
- Owners: AI Search Core Team
- Related plan: `docs/architecture/azure-sql-search-roadmap.md`, slice 2

## Kontext

Chat dříve mohl vybrat uživatele podle hlavičky či automaticky podle prvního účtu a přijímal skupiny dodané klientem. Azure vektorová větev omezovala kandidáty před kontrolou ACL a metadat. Sousední chunky i některé náhledy byly čtené bez oprávnění. Veřejná registrace dovolovala přidělit Management. Tyto mezery brání bezpečnému prefilter hledání.

## Rozhodnutí

- Podepsaný a neexpirovaný token musí uvádět přesný serverový tenant a existující ID uživatele v tomto tenantovi. Oprávnění načítáme z aktuálních DB skupin, ne z tokenových claimů, rolového přepínače, email fallbacku nebo X-User-* hlaviček. Odstraněno automatické přihlášení prvního uživatele.
- Registrace vytváří pouze User. V local/test je otevřená pro zkoušení; v dev/prod ji provádí ověřený Management účet. Cloudový startup již nevytváří demo účty se známými hesly; stávající účty vyžadují operátorský audit. Správcovské účty a skupiny se přidělují serverově. Login je scoped na přesný tenant. Vestavěný veřejně známý JWT_SECRET je akceptován pouze v local/test; pro cloud musí správce nastavit soukromý klíč. Stávající autentizační formát a hashování hesel se v tomto slice nemění.
- Dokumentové a chunkové ACL mají oddělené relační grant tabulky s PK (owner UUID, group), indexem (group, owner UUID) a FK CASCADE. Členství skupin používá v SQL Serveru binární collation, takže HR a hr nejsou zaměnitelné.
- Session before_flush aktualizuje ORM granty ve stejné transakci jako zdrojové ACL. `insert_chunks` ukládá Core bulk chunky a granty atomicky a přebírá tenant z rodičovského dokumentu. Existující bulk změny ACL byly převedeny na ORM aktualizace. Přímé SQL změny ACL/bulk inserty mimo tuto vrstvu nejsou podporovaná zápisová cesta a vyžadují explicitní obnovu projekce.
- Kompatibilita: chybějící ACL, prázdný objekt a prázdné allowed_groups byly v dosavadním Python kódu neomezené; projekce je převádí na grant User. Public je alias User. Malformovaný ACL nemá granty a běžný uživatel k němu nemá přístup. Management může přeskočit ACL pouze uvnitř vlastního přesného tenant scope.
- Společné parametrizované predikáty filtrují dokumentový i chunkový tenant, obě ACL, freshness a metadata před omezením kandidátů/top K. Metadata podporují skaláry a přesné pole skalárů na dokumentu nebo chunku; neznámá metadata nejsou dynamické názvy SQL sloupců. SQL Server používá OPENJSON, SQLite json_each. Keyword větev řadí a omezuje výsledky v SQL, aby neposílala celý korpus do Pythonu.
- Siblings/page/section rozšíření používá stejné predikáty a uchovává všechna ID přispívajících chunků. PDF a re-chunk preview čtou celý dokument, proto vyžadují přístup ke všem jeho chunkům. `/chunks` vrací pouze povolené chunky. Správcovské mutace jsou chráněny Management a scope aktuálního tenant ID.
- Historie nových odpovědí uchovává JSON envelope `access_policy`, `citations` a `access_refs`. Reference zahrnují i sousedy a transitivní evidenci předchozích tahů použitých pro generování. Před předáním historie modelu a před zobrazením odpovědí ověřujeme aktuální oprávnění k všem referencím v dávkách. Staré odpovědi bez doložitelné provenance se nevkládají do modelu a UI vrací redigovaný placeholder. Uživatelské vlastní zprávy zůstávají dostupné vlastníku konverzace.
- Frontendy posílají session bearer token. PDF se načte autentizovaným fetch a vykreslí přes lokální blob URL; token se nevkládá do URL ani PDF odkazu.
- Lokální HTTP čtení a potvrzená ingestace jsou omezené na kanonický adresář data/; útěk přes absolutní cestu, .. nebo symlink je odmítnut. Upload názvy jsou sanitizované. Blob náhled používá pouze nastavený tenantí originals container a cache je oddělená tenantem, prostředím a zdrojem/checksumem.

## Možnosti

Čisté postfilter řešení je nedostatečné, protože zakázané výsledky spotřebují top K a sousedé mohou uniknout. JSON ACL přes OPENJSON je proveditelné, ale relační indexované granty zjednodušují společný prefilter a jeho budoucí využití pro exact/ANN. Zachování klientských skupin by znehodnotilo obě řešení.

## Důsledky a ověření

Local/test inicializace vytváří grant tabulky a obnoví projekci. Azure startup je automaticky nevytváří: před nasazením vyžaduje audit a ruční migraci `migrate_search_acl.py` podle `.agents/inbox/2026-10-14-search-acl-migration-handoff.md`. Staré aliasové tenant hodnoty se nepřiřazují automaticky; operátor musí doložit vztah dokumentů, chunků a uživatelů k přesnému tenant ID.

Nová sada se ověřuje na SQLite a oddělené lokální SQL Server databázi. Azure tier, oprávnění a compatibility level se potvrzují samostatně handoffem. OPENJSON vyžaduje compatibility level nejméně 130 ([Microsoft](https://learn.microsoft.com/en-us/sql/t-sql/functions/openjson-transact-sql?view=sql-server-ver17)). Nativní vektory, úplné pokrytí a ANN jsou další slices; dosavadní arbitrární vektorový cap zatím zůstává.
