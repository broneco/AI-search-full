# ADR-0036: Nezávislá porovnání a popisy oddělené od modelové identity

- Status: accepted
- Date: 2026-10-21

## Kontext

Správce potřebuje na stejnou otázku porovnat různé modely, filtry a embeddingy a spravovat modely, popisy i oprávnění v jednom přehledu. Úprava lidského popisu nesmí zneplatnit připnuté modely ani existující vektory.

## Rozhodnutí

Porovnání je administrační klient nad dvěma standardními `/api/chat` požadavky. Každý nese jeden model a jeden index UUID (keyword bez indexu), vlastní filtry a vlastní serverové vlákno. Autorizace, citace a provenance zůstávají ve stávající cestě. Jeden požadavek nesmí hledat ve více indexech. Výsledek a selhání stran jsou nezávislé; žádný automatický fallback. HTTP časy souběžných volání jsou diagnostické, nikoli benchmark kvůli sdílené modelové kapacitě.

Discovery je explicitní modal, registrace/publication zůstávají oddělené od scanu. Perzistentní přehled spojuje nakonfigurované LLM/embedding profily, provozní limity a současné skupinové politiky. Čitelný popis CS/EN je samostatná SQL tabulka `model_descriptions`, klíčovaná hashem přesné tenantové identity a ID profilu. Má vlastní revizi, autora a čas; zápis porovnává revizi. Nepřepisuje immutable registry snapshot, provider, digest ani embeddingový fingerprint. Výchozí popis pochází z JSON profilu. Veřejný autorizovaný katalog vrací účely, provozní limity a aktuální popis bez připojení/secrets.

Cloud schéma se vytváří pouze guarded migrací. Skutečně chybějící tabulka dovolí čtení dosavadního katalogu, ale odmítne zápis. Chyby oprávnění se nezamění za chybějící tabulku. Lokální startup vytvoří novou tabulku.

Tři prompt editory jsou společně v poslední sekci; summary/classification PATCH-like PUT mění jen stávající instrukční pole konfigurace, bez kategorií, ACL a změny parametrů chunkování. Nezavádí se nový zdroj promptů ani automatický výběr modelů pomocí AI.

## Alternativy a důsledky

Jeden serverový fan-out endpoint by přidal orchestraci a komplikoval izolaci historie; dvě existující volání již splňují oprávnění a pinned indexy. Pokud obě varianty používají lokální službu při generování nebo query embeddingu, klient spouští A → B; služba má společný slot a jinak by jedno volání odmítla. Index API vystaví pouze veřejné local/cloud umístění. Neznámá starší metadata se považují konzervativně za lokální. Ostatní dvojice mohou běžet souběžně. Nejde o retry ani automatickou náhradu; HTTP čas nezahrnuje čekání varianty B. Přepis registry snapshotů kvůli popisu by směšoval metadata s identitou. Souborové popisy by nepřežily více cloudových replik; SQL dává sdílený aktuální stav s konflikty.

Porovnání zdvojnásobuje počet běžných modelových volání a ukládá dvě standardní konverzace. Po obnovení stránky začíná nové porovnání; historie je zachována na serveru. Výchozí ingestace a dosavadní dokumenty se nemění.
