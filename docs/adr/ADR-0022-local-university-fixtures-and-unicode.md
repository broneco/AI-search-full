# ADR-0022: Automatické lokální ukázky a Unicode text v SQL Serveru

- Status: accepted
- Date: 2026-10-14
- Owners: AI Search Core Team

## Kontext

Lokální aplikace potřebuje opakovatelné podklady pro ruční hledání a otevření citací. Uživatel požádal o dva krátké české dokumenty o vysoké škole. Nativní SQL test zároveň prokázal ztrátu českých znaků při ukládání chunků do původního TEXT/VARCHAR sloupce. Ručně hlášený pád hybridního score addition vznikal násobením float a SQL Decimal.

## Rozhodnutí

- Dva jednostránkové PDF o fiktivní Vysoké škole Aurora jsou verzované v `fixtures/local-university/`. Běžný extractor vytvoří jednu stránku/chunk na dokument; testovací seeder nepoužívá AI tagování, Blob upload ani měnitelná nastavení chunkování.
- Po inicializaci lokální DB startup doplní chybějící nebo změněné ukázky. Automatika je omezena na APP_ENV=local, DATABASE_BACKEND=sqlserver, loopback a ai_search_local; cloud a pytest startup se nepoužívají.
- Stabilní UUID odlišují tenant a fixture. PDF checksum, obsah chunku a immutable embedding_profile_id určují potřebu obnovy. I změna profilu se stejným rozměrem vygeneruje nové dokumentové embeddingy přes provider factory.
- Síťové volání proběhne mimo SQL transakci. Zápis obou dokumentů, chunků, vektorů a ACL grantů je transakční; ostatní dokumenty zůstávají zachované. PDF kopie v data/local-demo mají názvy podle checksumu, takže SQL rollback nepřepíše dříve platný zdroj. Chybějící PDF lze obnovit bez modelového volání.
- Chybějící modelové credentials znamenají explicitní warning a čekání na restart po doplnění .env.local, nikoli náhodné embeddingy. Selhání modelu/zápisu se loguje a lokální API může dále běžet; chybná dávka nic částečně neindexuje.
- SQL Server mapping používá NVARCHAR pro názvy dokumentů/konverzací a NVARCHAR(MAX) pro chunky/zprávy. Lokální startup opraví pouze tyto čtyři existující sloupce; přitom případný full-text index nad chunky odstraní a stávající inicializační krok jej zkusí obnovit. Cloudové ALTER se automaticky neprovádí a vyžaduje handoff.
- Keyword rank se převádí na float na výstupu databáze před fusion a serializací.

## Důsledky

První lokální start volá embeddingový model pro dva texty. Další start s platnými daty model nevolá. Testy ověřují SQLite a izolovaný SQL Server, idempotenci, Unicode, záměnu profilu, rollback, document mode a cloudovou ochranu. PDF byly vizuálně ověřeny po renderu.

Převod starého VARCHAR textu na Unicode neobnoví již ztracené znaky; takové dokumenty je nutné znovu nahrát z originálu. Ukázky se při ručním smazání na příštím startu znovu doplní. Tato lokální pomocná ingestace nepředstavuje nativní vector storage ani plnou profilovou izolaci legacy korpusu ze slice 3.

## Další krok

Dokončit ruční akceptaci slice 2; plán sliců 3–5 zůstává v `docs/architecture/azure-sql-search-roadmap.md`.
