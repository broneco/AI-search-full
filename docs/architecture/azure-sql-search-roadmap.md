# Schválený plán vyhledávání v Azure SQL — slices 1–5

Poslední aktualizace: 2026-10-15. Tento dokument uchovává plán schválený uživatelem v konverzaci, jeho hranice a podmínky dokončení. Aktuální souhrn vydání a ověřené výsledky jsou v [release notes v0.1.4](../releases/v0.1.4.md) a [JHU deployment reportu](../deployments/2026-10-15-jhu-search-rollout.md); tyto výsledky nahrazují starší průběžné poznámky níže. Po každém slice aktualizovat stav zde i v `.agents/memory/project-state.md`.

## Stav a způsob pokračování

| Slice | Stav | Obsah |
|---|---|---|
| 1 — Profily a provider injection | Implementováno, lokálně přijato a nasazeno na JHU. | Neměnný embeddingový profil, konfigurovatelný rozměr, factory, zapojení chatu, ingestace, taggeru a preview. |
| 2 — Správné filtry a oprávnění | Implementováno, lokálně ověřeno a nasazeno na JHU s relační ACL projekcí. | Ověřený tenant, serverové skupiny, společné SQL prefiltry a zabezpečené rozšíření kontextu. |
| 3 — Nativní úložiště a přesné hledání | Ověřeno na Showcase a nasazeno na JHU, coverage 9 372/9 372. | Katalog indexů, profilové vektorové tabulky, transakční zápisy a úplné přesné hledání. |
| 4 — DiskANN | Native lifecycle ověřen na Showcase; JHU v3 index vytvořen, runtime zůstává exact. Některé filtrované ANN dotazy timeoutují. | ANN v3+ nad stejným profilem/filtry, explicitní exact/ann, ODBC timeout, bezpečné chyby a diagnostika (ADR-0024, ADR-0028). |
| 5 — Evaluace a aktivace | Benchmark implementován; dílčích 60 User dotazů recall@30 99,11 %. Reprezentativní 100dotazová/p95 brána a aktivace ANN nejsou dokončené. | Reprodukovatelný CLI benchmark, kvalitativní/výkonnostní brány, explicitní neaktivní indexy a řízená aktivace (ADR-0025). |

Historie lokálního setupu: mezi slice 1 a 2 přibyly `dev.ps1`, `docker-compose.local.yml`, VS Code tasks a profily local/test (ADR-0020). Rancher stderr warning byl opraven a ověřen v PowerShell 5.1 i 7; korelace staršího timeoutu s VPN nebyla potvrzena. Uživatel postupně přijal lokální chování sliců 1–4. Aktuální stav je v tabulce výše; tyto lokální akceptace nejsou potvrzením Azure migrace/aktivace.

Implementovat vždy pouze jeden ucelený slice podle `.agents/rules/iteration-policy.md`. Každý má mít odpovídající testy a jejich vysvětlení, changelog, dokumentaci, aktuální paměť a případně ADR/handoff. Zkontrolovat `git status`; dosavadní implementace je necommitnutá a změny ve `frontend-user/next-env.d.ts` a `frontend-user/package-lock.json` byly přítomné již před lokálním setupem. Zachovat existující práci, ověřit aktuální stav souborů a nepředpokládat nasazení v Azure.

## Cíl a pevné hranice

### Aktualizace pořadí ověření na přání uživatele

Uživatel přijal lokální slicy 3 a 4 a vyžádal slice 5. Lokální část evaluace je nyní implementovaná (ADR-0025, `docs/development/search-slice-5-testing.md`); runtime i Docker zůstávají stejné. Další krok je dokončení cloudové části slice 5 přes `.agents/inbox/2026-10-14-search-evaluation-activation-handoff.md`, ne nový automatický rollout. Nativní exact/ANN stále není potvrzené a ANN se samo nezapíná.

Uživatel 2026-10-14 požádal o maximum lokálních testů a odložení Azure testovací databáze. Azure native integrační test proto nyní neblokuje další lokální vývoj slice 4; přesouvá se do souhrnného cloudového ověření exact + ANN ve slice 5, před cloudovou migrací/aktivací. Neprovedené ověření nadále musí zůstat explicitně označené, recall/latency ani Azure funkčnost se nepovažují za splněné.

Doporučený nejbližší technický mezikrok je oddělený SQL Server 2025 Developer Docker pro skutečné lokální VECTOR/VECTOR_DISTANCE testy. Microsoft poskytuje [SQL Server 2025 image](https://learn.microsoft.com/en-us/sql/linux/install-upgrade/quickstart-install-docker?view=sql-server-ver17) a [podporu native VECTOR](https://learn.microsoft.com/en-us/sql/t-sql/data-types/vector-data-type?view=sql-server-ver17). Jde zatím o plán: aktuální compose stále používá SQL Server 2022 a native fixture stále vyžaduje Azure. Nový kontejner má mít vlastní port/volume a vytvořené dočasné test DB; nesmí automaticky upgradovat současný volume s uživatelskými daty. Lokální SQL 2025 neprokazuje verzi DiskANN ≥3 ani výkon či oprávnění skutečné Azure Basic 5 DTU.

Lokální reference má pokrytí 3/3; slice 5 skutečný exact benchmark provedl 200 requestů pro concurrency 1 i 3 bez chyby, včetně per-request načtení konfigurace (p95 62/151 ms na místním Windows/Dockeru). Report záměrně ponechal ANN aktivaci blokovanou: workload má jen osm otázek, storage je local_json a ANN se neměřilo. Tyto lokální výsledky nenahrazují native Azure bránu ani výkon velkého korpusu.

- Odstranit arbitrární limit Azure kandidátů (dosavadní hranice 600) a porovnávat dotaz se všemi způsobilými chunky, případně použít ANN ověřené proti této přesné referenci.
- Tenant, ACL i metadata aplikovat PŘED top K v obou větvích hledání. Neřešit to pouze dodatečným filtrováním výsledků. Starší obecné schéma pipeline v `.agents/rules/retrieval-and-ai-policy.md` tento uživatelem schválený požadavek nenahrazuje.
- Zachovat Azure SQL Basic 5 DTU a Container App 0,5 CPU / 1 GiB. Kapacitu automaticky nezvyšovat; výkon na konkrétní databázi zatím není ověřen.
- PostgreSQL opravy (`UniversalVector.cosine_distance`, obecný JSON `has_key`), ukládání `section_title`, sjednocení Blob/lokální konfigurace a OCR zůstávají výslovně odloženy.
- Nyní se nevytváří lokální modelový adaptér ani automatické porovnávání modelů. Budoucí lokální model má být samostatná síťová služba; nasazení do malého backendového kontejneru potřebuje vlastní kapacitní ověření.

## Architektura, kterou mají další slices zachovat

`EmbeddingProfile` identifikuje model a revizi, rozměry, normalizaci a verzované zpracování vstupu, včetně rozdílných prefixů/instrukcí pro dotazy a dokumenty. Jakákoli změna těchto vlastností znamená nový profil. Endpoint a credentials určují vazbu na provider, nikoli embeddingový prostor. Modely se stejnou délkou vektoru nejsou automaticky kompatibilní. Dotaz musí používat přesně profil vybraného indexu; nesoulad profilu nebo rozměru selže před hledáním, bez náhradního modelu.

Každý logický index odkazuje na jeden profil a korpus. V Azure SQL má vlastní fyzickou tabulku `VECTOR(dimensions)` a později vlastní DiskANN index. Celočíselný clustered primární klíč a unikátní UUID odkaz na chunk; fyzické názvy vybírá serverový katalog, nikdy vstup uživatele. Text, dokumenty a ACL se mezi modely neduplikují. Výchozí provoz má jeden aktivní index na tenant. Další indexy vznikají explicitním dávkovým úkolem nad existujícími chunky, bez nové extrakce/chunkování a bez automatického volání všech modelů při běžném dotazu.

První profil plánuje 1536 rozměrů a float32. Schválený návrh počítá s limity Azure SQL 1998 rozměrů pro float32 a 3996 pro float16; aktuální dostupnost a limity ověřit proti Microsoft dokumentaci a testovací databázi při implementaci. Vektory automaticky nezkracovat; float16 je samostatná volba vyžadující evaluaci. Zdroj návrhu: [Microsoft VECTOR](https://learn.microsoft.com/en-us/sql/t-sql/data-types/vector-data-type?view=sql-server-ver17).

Providery se vybírají přes společnou factory, samostatně pro embeddingy, odpovědní LLM a ingestující LLM. Zachovat `embed_query` / `embed_documents`. Změna odpovědního LLM nevyžaduje reembedding; změna chunků při AI obohacení zneplatňuje jejich embeddingy. ADR-0019 popisuje implementovaný slice 1; historické DB embeddingy dosud nemají prokázanou profilovou provenance.

## Slice 2 — Správné filtry a oprávnění

1. Odvodit tenant z ověřené identity a oprávnění ze serverově ověřených skupin. Nevěřit klientskému výběru skupin jako zdroji oprávnění.
2. Zavést společné parametrizované SQL predikáty pro tenant, dokumentové/chunkové ACL a metadata ve vektorové i keyword větvi, aplikované před top K.
3. Uložit ACL do indexovaných relačních struktur a zabezpečit rozšíření kontextu na sousední chunky stejnými oprávněními.
4. Ověřit izolaci tenantů, obě úrovně ACL, selektivní metadata, prázdný výsledek, méně než K dostupných chunků a zakázané sousedy.

Dokončeno až při prokázání správného pořadí filtrů a top K v obou větvích a bezpečného context expansion. Arbitrární omezení vektorových kandidátů odstraní až slice 3; nezaměňovat tento mezistav za hotovou úplnou retrieval cestu.

## Slice 3 — Nativní úložiště a přesné hledání

1. Zavést katalog profilových indexů a první fyzickou vektorovou tabulku odpovídající profilu a jeho rozměru.
2. Společným repository zápisem ukládat chunk, embedding, profil a revizi vstupu v jedné transakci. Zapojit všechny aktuální ingestující/reindexující cesty včetně bulk insertů; nepoužít kopírovací trigger pro neoznačené vektory.
3. Mazání chunku kaskádově odstraní embeddingy. Změna jeho obsahu zneplatní vektory ve všech příslušných indexech; zastaralé vektory nesmějí být vyhledatelné.
4. Historické embeddingy převzít jen s doložitelným profilem. Aktuální konfigurace sama nestačí jako důkaz původu starých vektorů. Původní JSON embeddingy během první migrace zachovat.
5. Přesné `VECTOR_DISTANCE` provést nad všemi platnými způsobilými chunky v nativní tabulce, s filtry ze slice 2 a bez arbitrárního limitu kandidátů.
6. Ověřit úplné pokrytí platných embeddingů, pořadí výsledků, inserty, aktualizace, reindexace, mazání a rollback transakce. Otestovat nejlepší výsledek za starou hranicí 600.

Nativní SQL a synchronizaci ověřit v samostatné Azure SQL testovací databázi přes lidský handoff. SQLite ani současný lokální SQL Server 2022 tuto cestu neprokazují. V případě neznámého původu vektorů připravit explicitní reembedding/backfill; profil nehádáme.

## Slice 4 — DiskANN

1. Ověřit dostupnost požadované Azure SQL funkce a vytvořit DiskANN index verze alespoň 3.
2. Použít `VECTOR_SEARCH` se stejným profilem a stejnými prefiltry; skutečnou sémantiku filtrovaného top K potvrdit Azure integračními testy.
3. Přidat explicitní režimy `exact` / `ann`, diagnostiku používaného profilu/indexu a řízené chyby.
4. Chybějící index řešit explicitním přesným režimem. Timeout ANN nesmí automaticky spustit další nákladný přesný scan.
5. Ověřit obě cesty nad stejnou nativní tabulkou. Návrat na exact zachová stejný profil a data.

Dokončeno až po ověření ANN i přesné cesty v Azure SQL a oprávnění/filtrů v obou režimech. Přítomnost funkce nebo indexu nepředpokládat jen podle dokumentace či lokálního SQL Serveru.

## Slice 5 — Evaluace a aktivace

1. Připravit reprodukovatelný dataset a benchmark s přesnou referencí. Zahrnout selektivní metadata/ACL, prázdné výsledky, méně než K chunky a nejlepší výsledek za původním limitem.
2. Před aktivací ANN požadovat průměrné recall@30 ≥ 95 % proti exact na alespoň 100 dotazech. Report rozdělit podle selektivity filtrů.
3. Požadovat p95 celého retrievalu ≤ 1 sekunda při souběhu 1 i 3 hledání; nezahrnovat embedding otázky a generování odpovědi. Nejméně 200 požadavků pro každý souběh, studený start měřit zvlášť.
4. Benchmarky dalších modelů spouštět postupně kvůli Basic 5 DTU. Další profil znamená úložiště a práci při indexaci.
5. Aktivovat nový index až po ověření pokrytí aktuálního korpusu; zachovat předchozí index pro návrat. Připravit Azure handoff s migrací, konfigurací, validačními kroky a návratem do exact. Migraci a aktivaci provádí člověk.

Recall ANN měří kvalitu indexu vůči exact. Budoucí porovnání kvality embeddingových modelů používá stejné chunky, otázky a filtry a označené správné dokumenty pro Recall@K a nDCG@K; cosine skóre různých modelů vzájemně neporovnávat. Automatická evaluace modelů nyní není součástí implementace.

## Povinné regresní scénáře a prostředí

- Dva různé profily se stejným rozměrem a profil s jiným rozměrem: záměna musí selhat před hledáním.
- Lokální profil: SQL Server 2022 Developer pro běžné schéma, CRUD a úplnou streamovanou JSON cosine referenci bez capu kandidátů; modelové volání stále vyžaduje Azure OpenAI konfiguraci. Benchmark run používá připravenou query cache bez modelových volání.
- Test profil: izolované rychlé SQLite/unit testy a mocked providery, bez cloudových secrets. Nenahrazuje Azure integrační testy.
- Azure testovací databáze: nativní VECTOR, indexy, synchronizace, transakce, prefiltry a performance. Oddělit od produkčních dat a nasazení podle `.agents/rules/azure-deployment-handshake.md`.
- Splněná automatická kontrola nebo statická dokumentace není důkaz výkonu na Azure SQL Basic 5 DTU.


## Implementovaný slice 2 — provozní návaznost

ADR-0021 a `.agents/inbox/2026-10-14-search-acl-migration-handoff.md` doplňují skutečné chování: přesný tenant bez aliasů, aktuální DB skupiny, User registrace a demo účty pouze v local/test (cloud registrace vyžaduje Management), soukromý cloudový signing key, relační ACL a zabezpečené PDF/historie. Historické assistant odpovědi bez evidence se redigují. Lokální runtime vytváří a backfilluje granty; Azure vyžaduje lidský audit/migraci před nasazením. JSON embeddingy ani vektorový cap se v slice 2 nemění.
