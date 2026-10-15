# ADR-0028: Nativní keyword retrieval a řízená aktivace JHU ANN

- Status: accepted
- Date: 2026-10-15
- Owners: AI Search Core Team
- Supersedes: —
- Superseded by: —

## Context

JHU native exact vector trval0,4–0,8s, celý retrieval28–29s. Read-only profil potvrdil keyword26,5s přes LIKE/LOWER/LEN/REPLACE bez existujícího FTS. Uživatel výslovně požádal o společný slice keyword opravy, aktivace ANN a verze v0.1.4 včetně již schváleného Azure deploymentu. Nové zadání nahrazuje dřívější zákaz aktivace; neznamená splnění reprezentativního p95 benchmarku.

## Decision

- Azure SQL keyword používá CONTAINSTABLE, parametrizované literal Unicode výrazy spojené OR a jazyk/stoplist indexovaného sloupce. Syntax uživatele se neprovádí. Word matching a relevance rank se oproti starému substring LIKE mění.
- Tenant/docACL/chunkACL/freshness/metadata zůstávají před jediným finálním TOP K. Bez globálního top_n_by_rank před ACL. Hydratace kontroluje oprávnění znovu a nečte staré JSON embeddingy.
- ODBC může poslat NVARCHAR(MAX), který CONTAINSTABLE odmítá, stejně jako inline CAST. Použít deklarovanou NVARCHAR(4000) proměnnou ve stejném batch; validovat délku UTF-16 předem, nic nezkracovat. Textual predikáty zachovávají VARCHAR/NVARCHAR typy včetně DATALENGTH a korelovaných EXISTS.
- Lokální SQL2022/SQLite bez FTS zachovává referenční LIKE. Cloud při chybě/timeoutu vrací bezpečnou503/504 bez retry/scanu; keyword operace má limit10s.
- JHU má319cs/112en dokumentů; FTS změní English1033 na dostupnou Czech1029. Literal anglická slova musí fungovat, anglické stemming rozšiřování se neslibuje. Společné runtime SQL jazyk nehardcoduje. Zachovat katalog/PK/tracking/stoplist a snapshot.
- DiskANN nad existujícími9372nativními vektory bez reembeddingu/rechunkingu. Ověřit skutečnou verzi>=3, complete coverage a alespoň100různých dokumentově odvozených exact/ANN dotazů, recall@30>=95%. Takto odvozený soubor nenahrazuje ručně revidovanou reprezentativní sadu.
- Aktivace na výslovnou žádost je řízené provozní ověření. P95<=1s/200requestů/souběhy1a3/cold start zůstávají formálně neověřené do benchmarku; neoznačovat slice5 za plně akceptovaný. Neměnit SKU/CPU/RAM/identity/RBAC. Funkční problém řešit explicitním exact nad stejným profilem, nikoli automatickým fallbackem při timeoutu.
- Blob config uložit celý se zachováním efektivních parametrů, snapshotem a ETag/absence guardem. Ostatní tenanti nadále default exact.

## Options considered

Pouhé ANN ponechá lexical scan. Navýšení kapacity by maskovalo chybnou cestu. Globální lexical cap porušuje oprávněný topK. Zachování angličtiny neodpovídá většině korpusu. Tyto varianty nejsou zvoleny.

## Consequences and verification

Reálné JHU ověření odhalilo, že původní přímo joinované ACL vynucené ANN timeoutuje5/10s i přes funkční index. Dotaz proto nejdříve materializuje VŠECHNA oprávněná chunk ID + aktuální revize do SQL tabulkové proměnné s primárním klíčem, bez TOP/capu. DiskANN nad ní iterativně filtruje před finálním K a porovnává revizi. Stávající bezpečná hydratace oprávnění i revizi ověřuje znovu. Jediný filtrovaný read-only probe vynuceného ANN klesl na1010ms z počítače; nejde o runtime p95. FORCE_ANN_ONLY se zachovává, takže recall neměří potichu exact plán. Hint RECOMPILE nepomohl; varianta bez FORCE sice byla rychlá, ale mohla by měřit KNN místo ANN. Nejde o klientské procházení vektorů ani předvýběr omezeného počtu chunků.

Eligibility INSERT potřebuje NOCOUNT, aby ODBC vidělo následný SELECT. Celý parametrizovaný batch proto běží ve sp_executesql scope, který obnovuje SET options po návratu včetně chyb. Vnořené SQL tvoří výhradně compiler a validované identifikátory; uživatelské hodnoty zůstávají bind parametry. Lokální reálný T-SQL test ověřuje Unicode/injection, původní NOCOUNT ON/OFF a timeout bez znečištění dalšího požadavku. Žádné permanentní SQL tabulky/procedury, změna kapacity nebo timeout-triggered fallback.

Ověřit české/anglické dotazy, stopwords, whole-word rozdíl, prázdný vstup, injection, oba ACL/tenant/metadata před topK a bezpečné chyby. SQLite neprokazuje FTS: potřebný izolovaný Azure test a cleanup. Diagnostika doplní keyword/fusion/expansion časy. Skutečný deployment a výsledky zaznamenat v reportu; exact zůstává návratovou cestou.

## Follow-up

**Výsledek JHU v0.1.4:** native keyword je nasazený, runtime nadále exact. Materializace pomohla60User dotazům (mean recall99,11%), ale některé metadata kombinace Management dál timeoutují;100dotazový běh nebyl dokončen. Uživatel požádal o vysvětlení výkonu místo výběru adaptivní varianty. ANN aktivaci neoznačovat za dokončenou, dokud se nevyřeší strategie; nativní index samotný není prokázané zrychlení. Žádný adaptive/implicitní exact fallback není součástí aktuální implementace.

Jeden další slice: reprezentativní runtime benchmark JHU a optimalizace změřeného zbývajícího bottlenecku. Sekční metadata, PostgreSQL, OCR a Blob/file unifikace zůstávají odložené.
