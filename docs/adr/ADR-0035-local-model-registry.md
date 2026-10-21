# ADR-0035: Tenantový registr lokálních modelů a zveřejněných embeddingových indexů

- Status: accepted
- Date: 2026-10-20

## Kontext

Discovery dosud pouze zobrazovalo metadata. Aplikace umožňovala jediný ověřený lokální LLM a Nomic. Uživatel chce zkoušet všechny kompatibilní modely tenantové služby a určit, které uvidí běžní uživatelé.

## Rozhodnutí

Správce explicitně přidá jednotlivé nebo všechny kompatibilní modely. Backend znovu načte metadata služby a ověří název, digest, účel, kontext a embeddingové rozměry; klient neurčuje připojení ani profil. Discovery samo nezapisuje. Registr `tenant_model_registry` ukládá veřejný snapshot profilu, hash přesné tenantové identity, ID modelu, samostatnou viditelnost pro uživatele, revizi, autora a čas. Publikace používá porovnání revize. Nové profily jsou dostupné pouze pro administrační testování, dokud je správce nezveřejní.

JSON katalogy zachovávají výchozí modely. Registr je doplní bez přepisování souborů nebo implicitní změny výchozího modelu. Bez nové tabulky fungují původní katalogy; registrace požaduje migraci. Chyba existujícího registru se neignoruje. Lokální inicializace vytvoří tabulku při restartu, cloud používá výhradně guarded migraci.

Zveřejnění neobchází `model_access_policies` ani dokumentová/chunková ACL. Současné serverové skupiny se ověřují při použití. Embeddingové profily lze také omezit skupinovou maticí. Nezveřejněné experimentální indexy nelze podvrhnout přímým requestem.

LLM profil je připnutý na digest; adaptér jej ověří před generováním i po něm. Zachovává Basic `/api/generate`, používá pouze `response`, kontroluje model a nevystavuje `thinking`. Pro nové profily nastaví explicitní omezený kontext/výstup; konzervativní UTF-8 rozpočet odmítne příliš dlouhý prompt před voláním. Timeout, změna modelu nebo dosažení limitu nevyvolá další generování ani cloudový fallback. Starý explicitně ověřený Qwen z JSON zůstává kompatibilní.

Embeddingové modely potřebují verzovaný recept vstupu v `local_model_recipes.json`. Nomic zachovává původní fingerprint a prefixy; MXBAI používá query instrukci výrobce, dokumenty bez prefixu a vlastní 1024rozměrný prostor. Neznámé recepty/rozměry a rerankery se odmítnou. Přidání profilu nevytváří vektory. Správce následně explicitně připraví index nad existujícími chunky. Uživatelský katalog vystaví jen povolené, neprázdné a úplné indexy, bez počtů dokumentů. Dotaz nese konkrétní UUID, vytvoří jediný query embedding a čte jednu tabulku. Nemění výchozí ingestaci.

## Zvažované alternativy

- Dopisovat všechny názvy do JHU JSON: neřeší změny inventáře ani per-tenant schválení za běhu.
- Zpřístupnit vše hned po discovery: zaměňuje metadata za schválení a umožní nechtěné drahé volání.
- Uložit stav v lokálním overlay: nefunguje spolehlivě pro více replik a restart kontejneru.

## Důsledky a hranice

Neprovádí se automatické stahování ani benchmark všech LLM, zvláště velkých 120B modelů. Metadata a validovaný adaptér nejsou důkazem kvality nebo dostupné RAM. Velké modely mohou vrátit řízený timeout. Změněný digest znamená nový profil; staré indexy se nepřepočítávají ani nepřesměrují automaticky. Modelová služba nadále sdílí jeden slot na proces backendu.

## Ověření a další krok

Regrese: `tests/test_local_model_registry.py`, existující modelové/embeddingové/indexové testy a frontendové buildy. Následuje ruční porovnání vybraného lokálního LLM a obou embeddingových indexů na stejných českých otázkách; plošné generování a cloudové nasazení jsou samostatné operace.

Při prvním připnutí již nakonfigurovaného lokálního chatového modelu se zachová jeho ID a dosavadní viditelnost, aby nevznikla druhá položka a nezměnilo se výchozí chování. Změněný digest dostane nové ID. U embeddingů se identita odvozuje i od celého receptu vstupu, nejen od jména či digestu modelu.
