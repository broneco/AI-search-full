# ADR-0034: Příprava a porovnání embeddingových indexů v administraci

Status: přijato; 2026-10-20.

## Rozhodnutí

Na výslovné upřesnění uživatele implementujeme administrační vertikální slice před obecnějším SQL registrem schvalování modelů: připravit Nomic nad stejnými dvěma lokálními PDF a vyhledat stejnou otázku přes Azure a přes Nomic přímo v UI.

Management `GET /api/search-indexes` vrací pouze přesný tenant, známé profily, pokrytí a výchozí index ingestace. `POST /api/search-indexes/prepare` je explicitní, pouze lokální SQL operace: vytvoří nebo doplní neaktivní index existujícím resumable backfillem. Zachová text, UUID, ACL, legacy JSON i vektory jiných modelů. Více indexů stejného profilu vyžaduje explicitní UUID; opakovaný požadavek nezakládá další kopii. Single-process gate omezuje souběh přípravy, neřeší distribuované cloudové joby. Dávky znovu ověřují současné Management oprávnění před čtením a po modelovém volání před zápisem.

Chat přijímá volitelné UUID `search_index_id`, zatím pouze pro Management. Backend ověří tenant/corpus/profil i aktuální úplné neprázdné pokrytí před vedlejšími zápisy a query embeddingem. Připne jeden provider a VectorSearchPlan k jediné tabulce; změna výchozího indexu během requestu tuto volbu nenahradí. Neexistuje fan-out ani fallback. Neznámý index/profil a incomplete index jsou řízené chyby. Keyword-only request explicitní index odmítne; hybrid čte jediný embeddingový index a sdílený autorizovaný textový korpus. Bez explicitního UUID je dosavadní chování stejné.

Odpověď a uložená generace obsahují skutečný index/embeddingový profil/model. UI vybírá mezi konkrétními UUID a ukazuje použitý embedding u odpovědi; invalidní volbu po refreshi nenahrazuje jinou. Neměníme DBActiveSearchIndex, globální settings ani embeddingový profil ingestace.

## Hranice a ověření

Jde o lokální administrativní porovnání, bez nových základních SQL tabulek a bez Azure zápisů. Cloudový DDL/backfill ani user-app exposure se tím nepovolují. Příprava přes HTTP může při selhání zachovat hotové dávky; další explicitní požadavek pokračuje. Pro admin experiment se pokrytí ověřuje SQL counts; cloudový výkon této nové cesty není změřený.

Regrese nad SQLite a skutečným lokálním SQL zachovávají oba prostory a corpus, ověřují opačné pořadí stejných dokumentů podle indexu, jeden provider/dotaz, dva indexy stejného profilu, změnu ingestion defaultu během embeddingu, ACL, chybné UUID/tenant/profil/coverage, timeout/resume a revokaci správce. Opt-in test používá skutečné Nomic embeddingy obou ukázkových PDF a izolovanou SQL DB s mock LLM. [Postup pro uživatele](../development/local-embeddings.md).
