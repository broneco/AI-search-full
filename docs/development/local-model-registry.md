# Výběr dalších lokálních modelů

## Lokální spuštění a ovládání

1. Spusť databázi a aktualizovaný backend pro JHU. S [managed připojením](jhu-managed-local.md) použij `.\dev.ps1 -Action backend -Tenant jhu -JhuManaged` bez ruční systémové VPN; legacy direct režim zůstává `.\dev.ps1 -Action backend -Tenant jhu` s JHU VPN. Startup pouze v lokální SQL vytvoří tabulku registru. Obnov obě konzole a přihlas se odpovídajícím účtem.
2. V administraci pod `Management` otevři **Modely a vyhledávání → Dostupné modely a oprávnění → Obnovit z API**. V dialogu vyhledej model názvem; po zavření zůstane společný přehled konfigurace, oprávnění a upravitelných CS/EN popisů. [Porovnání výsledků a tři prompty](admin-comparison.md) jsou ve stejné administraci.
3. Použij **Přidat pro testování**, případně **Přidat všechny kompatibilní modely pro testování**. Tím se uloží tenantový snapshot profilu. Modely se nestahují a žádné generování se automaticky nespustí. Přidané chatové modely se objeví ve výběru odpovědí, shrnutí a klasifikace; výchozí Azure model se nemění.
4. Checkbox **Zobrazit v uživatelské aplikaci** povolí nově přidaný model také běžným uživatelům. Platí současně skupinová oprávnění modelu. Změny přežijí restart; souběžná zastaralá změna vrátí konflikt a vyžaduje obnovu přehledu. Přidání modelu není nezávislé potvrzení jeho kvality — nejprve jej vyzkoušej v administraci.
5. U embeddingu pokračuj v **Embeddingové modely a indexy → Embeddingové indexy — příprava a porovnání**. Vyber Nomic nebo MXBAI a klikni **Připravit / doplnit index**. Znovu se použijí stejné chunky a ACL, původní vektory zůstanou. Nevzniká nová kopie dokumentů.
6. Po úplném pokrytí zvol konkrétní index a přejdi k vyhledávání. Uživatelská konzole nabídne zveřejněné a skupinově povolené připravené indexy; lze použít **Obnovit indexy**. Po zveřejnění nových chatových modelů obnov uživatelskou stránku. Při odebraném přístupu backend dotaz odmítne a UI vyžádá novou volbu; nic se znovu neodešle jinému modelu.

Jeden dotaz znamená jeden vybraný LLM a jeden konkrétní embeddingový index UUID. Výchozí index pro další ingestaci se tím nezmění. U odpovědi i uložené historie je skutečný model a index. Vektorové tabulky se při přidání samotného chatového modelu nemění.

## Kompatibilita a limity

Chatová část přijímá modely s completion schopností a známým kontextem. Rerankery, neověřená metadata a specialisté bez textového completion se nenabízejí. Názvy z klienta se vždy ověří proti aktuálnímu serverovému inventáři a digestu. Připojení/credentials zůstávají v existujícím prostředí/Key Vaultu.

Připravené embeddingové recepty jsou Nomic (768, query/document prefixy) a MXBAI (1024, instrukce pouze pro query). Pro budoucí jiný embedding doplň správný verzovaný recept do tenantového `local_model_recipes.json`; samotné metadata neřeknou potřebný preprocessing. SQL float32 podporuje v této implementaci nejvýše 1998 rozměrů. Vektory se nezkracují. [MXBAI instrukce výrobce](https://ollama.com/library/mxbai-embed-large).

MXBAI má krátký kontext 512 tokenů. Dlouhý existující chunk může služba odmítnout: `truncate:false` brání tichému oříznutí. Částečný index pak zůstává nepřipravený a lze jej dokončit po odpovídající úpravě korpusu; aplikace automaticky nepřechunkuje ani nezmění ostatní indexy. Neznamená to, že každý embeddingový model zpracuje libovolné nynější chunky.

Nové LLM profily mají timeout 180 s a explicitní kontext nejvýše 8192 tokenů. UTF-8 rozpočet je konzervativní, nikoli přesný tokenizer; příliš dlouhý kontext je řízená chyba před HTTP voláním. Uprav retrieval/historii místo tichého truncation. [Generování Ollama](https://docs.ollama.com/api/generate), [embeddingy a truncation](https://docs.ollama.com/api/embed).

Nejsou automaticky ověřovány generace všech 13 chatových kandidátů. Při chybě či změně mutable tagu se model nenahrazuje jiným. Nový digest vytvoří nový profil/index. Velké modely mohou překročit dostupnou kapacitu služby; jejich přidání nic nevypovídá o rychlosti.

## API a provoz

- `GET /api/models/discovery`: read-only metadata a současné schválení.
- `POST /api/models/registry`: Management, seznam `{name,digest}`, opětovné ověření služby, atomické přidání kompatibilních profilů.
- `GET /api/models/registry`: Management, aktuální tenantová schválení.
- `PUT /api/models/registry/{id}`: Management, `{revision,user_visible}` s kontrolou revize.
- `GET /api/models`: JSON základ plus povolené registrované chatové profily pro daný účel.
- `GET /api/search-indexes/available`: přihlášený uživatel, pouze povolené a úplné indexy. Kontrola dostupnosti předchází výpočtu pokrytí skrytých indexů.

Příprava vektorů z UI zůstává lokální. Azure cloud vyžaduje oddělenou migraci tabulky registru, síťové ověření JHU a release backendu/obou konzolí. `migrate_model_registry.py` bez přepínačů pouze vypíše cíl. Zápis vyžaduje `--apply --expect-host <ověřený-host> --expect-db <ověřená-DB> --expect-tenant <přesný-tenant>` a samostatné schválení. Starý backend/katalog může fungovat bez registru; registrace musí chybějící tabulku explicitně ohlásit. Nikdy nevytvářej schéma v cloudovém startupu.

Lokální testy: `tests/test_local_model_registry.py`; současné scénáře [modelů](model-selection.md) a [indexů](local-embeddings.md) zůstávají platné. Metadata ani lokální SQL výsledky nenahrazují Azure native/performance akceptaci.

Při prvním připnutí již nakonfigurovaného lokálního chatového modelu se zachová jeho ID a dosavadní viditelnost, aby nevznikla druhá položka a nezměnilo se výchozí chování. Změněný digest dostane nové ID. U embeddingů se identita odvozuje i od celého receptu vstupu, nejen od jména či digestu modelu.
