# Porovnání výsledků a společná správa modelů

## Spuštění a porovnání

Spusť lokální prostředí pro zvolený tenant podle [README](../../README.md). Po aktualizaci restartuj backend; lokální startup vytvoří také tabulku `model_descriptions`. Přihlas se v administraci účtem ve skupině `Management`.

V **Porovnání výsledků** nastav varianty A/B. Každá má vlastní model, strategii hledání, aktuálnost, jazyk, zdrojovou složku a konkrétní embeddingový index UUID. Výběr modelu umí hledat v názvu, popisu a provozních parametrech. Nepřipravený index nelze použít; při keyword hledání se embedding neposílá.

Jednou společnou otázkou spusť dvě nezávislá volání `/api/chat`. Odpovědi mají vlastní citace, skutečně použitý model/index a dobu celého HTTP požadavku. Kliknutí na citaci otevře podklad a odkaz na autorizované PDF. Následující otázka pokračuje ve dvou oddělených serverových vláknech. **Nové porovnání** vyčistí obě historie a založí nové dvojice vláken při dalším odeslání; nastavení variant zachová. Serverové konverzace se tím nemažou.

Nastavení se během obou běžících požadavků nemění. Chyba jedné strany nezahodí druhou odpověď, nevyvolá opakování ani fallback. Pokud obě varianty používají JHU službu (LLM nebo embedding), spouštějí se postupně A → B kvůli společnému kapacitnímu slotu. Jinak mohou běžet souběžně. API indexů vrací veřejné `embedding_location`; neznámá starší metadata vedou ke konzervativnímu postupnému spuštění, nikdy k odhadu podle názvu. Čas varianty měří její HTTP volání bez čekání ve frontě. Po změně oprávnění se katalog obnoví a je nutné ručně zvolit dostupný profil/index. Přepnutí tabu zachová rozpracované porovnání; obnovení stránky začne nové porovnání. Sdílená kapacita a zátěž znamenají, že tyto časy nejsou benchmark latence modelu.

## Modely, popisy a oprávnění

V **Modely a vyhledávání → Dostupné modely a oprávnění** je stálý přehled všech nakonfigurovaných LLM i embeddingových profilů. Nevyžaduje dostupnou JHU VPN ani živý scan. Zobrazuje účely, nakonfigurované limity (vstup, výstup, čas, kontext/rozměry), zveřejnění, skupiny a popis CS/EN. Dostupné připojení není důkazem, že služba právě odpovídá.

**Obnovit z API** otevře samostatný dialog s aktuálním inventářem a tlačítky pro přidání jednotlivých nebo všech kompatibilních modelů. Po zavření zůstává přehled aplikace. Přidání modelu ani úprava popisu nevytváří vektory; embeddingový index se nadále připravuje explicitně.

**Popis modelu** vysvětluje doporučené použití. Obě jazykové verze lze upravit a uložit; prázdná hodnota je dovolená. Popis je veřejná katalogová informace pro oprávněné uživatele, proto sem nepatří hesla ani interní dokumenty. Ukládá se s vlastní revizí do tenantově oddělené tabulky `model_descriptions`; nezmění provider, digest, preprocessing ani identitu vektorového prostoru. Veřejný katalog `/api/models` vrací aktuální popis a provozní parametry. Automatický výběr modelu pomocí AI tato verze nezavádí.

Publikace a oprávnění mají vlastní explicitní ukládání. Neuložené úpravy zůstanou při přidání modelů v dialogu; ruční opětovné načtení přehledu nabídne jejich zahození. Zastaralá revize vrátí konflikt, změna jiného správce se tiše nepřepíše.

## Nastavení maximální délky výstupu

V **Modely a vyhledávání → Dostupné modely a oprávnění → Konfigurace aplikace** má každý LLM pole **Maximální délka výstupu (tokeny)** a vlastní **Uložit limit**. Oprávnění má `Management`. Stejný modelový profil používá tento strop pro nově zahájené chaty, shrnutí i klasifikaci; běžící operace používá již vybraný snapshot. Model nemusí rozpočet vyčerpat.

Limit se ukládá pro přesný tenant do `model_runtime_settings` s vlastní revizí. **Použít výchozí** vrátí hodnotu z původního JSON/registrovaného profilu; revize pokračuje. Obnova API, změna popisu a restart limit nepřepíšou. Po uložení se aktualizují parametry ve výběrech modelů. Zastaralá souběžná změna vrátí HTTP 409.

UI ukazuje povolený rozsah. Aplikační limit je 128–32768, ale lokální profil musí v ověřeném kontextu ponechat rozpočet pro vstup a rezervu. Kontext 8192 dovolí nejvýše 6912 pro výstup; výstup 4096 sníží konzervativní vstupní limit na nejvýše 3840 znaků (navíc se hlídá UTF-8 rozpočet). Podklady se neoříznou. U legacy lokálního profilu bez ověřeného kontextu nelze zvýšit výstup nad původní limit, dokud se model nepřipne přes ověřený inventář. Služba/deployment může mít přísnější limity než aplikace.

Změna se netýká embeddingů, indexů ani uloženého korpusu. DB-less metadata utility používají souborové hodnoty; běžné API/CLI modelové operace s DB session respektují uložené nastavení.

## Tři prompty na jednom místě

Poslední sekce obsahuje systémovou šablonu odpovědí CS/EN, **prompt pro shrnutí** a **prompt pro klasifikaci**. První šablona používá `{context_str}`; jazykové koncepty se uchovávají odděleně. Zbývající dvě pole jsou doplňující instrukce, které aplikace vloží do základních promptů; výstupní schéma a validace klasifikace zůstávají řízené aplikací.

Shrnutí nadále používá `search_config.summary_custom_prompt` a zapíná se volbou AI shrnutí při chunkování. Klasifikace používá `classification_config.analysis_rules`. `PUT /api/prompts/tasks/summary|classification` načte aktuální konfiguraci a změní pouze dané pole, bez migrace kategorií/ACL nebo reindexace. Uložené dokumenty se samy nepřepracují. Dosavadní Blob/lokální konfigurace zůstává stejná; tato změna neřeší dříve odložené sjednocení zdrojů konfigurace.

## API a cloudová migrace

- `GET /api/models/management`: `Management`, společný přehled bez síťového discovery a secrets.
- `PUT /api/models/descriptions/{id}`: `Management`, `{revision, description:{cs,en}}`, nejvýše 4000 znaků pro jazyk, konflikt HTTP 409.
- `PUT /api/models/runtime/{id}`: `Management`, `{revision,max_output_tokens}`, celé číslo v povoleném rozsahu nebo `null` pro reset; samostatná revize a HTTP 409 při konfliktu.
- `PUT /api/prompts/tasks/{purpose}`: `Management`, `{prompt_text}`, nejvýše 16000 znaků; prázdné pole vrátí základní instrukce.

Azure startup novou tabulku nevytváří. `migrate_model_metadata.py` bez přepínačů pouze vypíše cíl. Pouze schválené `--apply --expect-host <host> --expect-db <db> --expect-tenant <přesný-tenant>` vytvoří tabulku, idempotentně a bez změny existujících indexů/dat. Bez tabulky fungují dosavadní katalogové popisy; zápis popisů vrací explicitní požadavek migrace. Chyba oprávnění existující tabulky se neignoruje.

Runtime limity mají vlastní tabulku: lokálně stačí restart aktualizovaného backendu, cloud používá samostatný `migrate_model_limits.py` se stejnými guardy. Bez tabulky se čtou původní limity a zápis vyžaduje migraci. Žádný cloudový startup DDL ani automatické nasazení.

Regrese: `tests/test_admin_models.py`, současné modelové/indexové testy, produkční build administrace a prohlížečový průchod se syntetickým API. Skutečnou kvalitu modelů ověř na stejné sadě českých otázek a PDF.
