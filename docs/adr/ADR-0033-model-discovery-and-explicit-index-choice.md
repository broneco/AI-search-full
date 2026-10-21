# ADR-0033: Discovery modelů oddělené od schválení a výběru indexu

Status: přijato pro discovery; navazující zápisy/selectory dle roadmap. Datum: 2026-10-20.

## Rozhodnutí

Management může číst živý tenantový JHU inventář přes stávající Basic/VPN připojení. Čteme tags/show, vracíme whitelist metadat a rozlišujeme embedding/chat kandidát/reranker/unsupported/unverified. Metadata nemění aplikační katalog, oprávnění ani SQL index. Reranker s deklarovaným completion není chatový model; LLM embedding_length není embeddingová služba. Neprovádíme model pulls, generování všech modelů ani per-query scraping.

Schválení profilů a dostupnost uživatelům budou samostatná tenantová SQL data s revizí, nikoli automatický import všeho nebo mutable kontejnerový JSON. Aktuální discovery slice nic nezapisuje. Existující oprávnění a výchozí modely zůstávají funkční.

Uživatel schválil volbu embeddingového indexu pro jednotlivý dotaz: request musí jednoznačně odkazovat na existující UUID. Jeden request používá jeden ověřený profil a jednu fyzickou vektorovou tabulku. Zakazujeme fan-out, union modelů a fallback z explicitně zvoleného indexu. Uživatelský výběr nemění výchozí index ingestace. Výběr se zapojí až nad připravenými schválenými indexy.

## Následky

Aktuální UI ukazuje inventář a konfigurační vazby; nové checkboxy povolování a selectory přijdou v navazujících slices. Přítomnost modelu na serveru neprokazuje jeho kvalitu pro češtinu ani RAG kompatibilitu. Metadata scan má omezený souběh a timeout; jednotlivý neověřený model neskrývá ostatní.

[Roadmap a skutečný inventář](../development/model-discovery.md).
