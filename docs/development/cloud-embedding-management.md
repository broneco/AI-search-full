# Správa embeddingových indexů v administraci

Pracovní verze v0.1.9 umožňuje správu také nad Azure SQL. První cloudové zapnutí vyžaduje níže uvedenou aditivní migraci a explicitní povolení. Samotná přítomnost kódu funkci v dosavadní cloudové verzi neaktivuje.

„Lokální embedding“ označuje model běžící na JHU API. Cloudový backend k němu přistupuje přes vlastní VPN sidecar v Azure; notebook, jeho VPN ani lokální Docker nejsou potřeba pro provoz aplikace. SQL indexy zůstávají v Azure SQL, v nativních `VECTOR(dimensions)` tabulkách.

## Obsluha přes UI

1. V **Modely a vyhledávání → Dostupné modely a oprávnění → Modely dostupné na JHU API** načtěte inventář. Model se nestahuje na notebook ani do backendu.
2. U ověřeného embeddingového modelu vyberte **Přidat embeddingový index**. Aplikace případně zaregistruje jeho konkrétní digest a vytvoří prázdný index. Pokud již existuje jednoznačný index stejného profilu, zachová jej a použije jeho UUID. Reranker ani chatový model nelze takto přidat jako embedding.
3. V menu **Chunkování** je samostatný panel **Embeddingové indexy**. U konkrétního indexu vyberte **Doplnit embeddingy**. Stejný přehled zůstává dostupný v nastavení modelů. Výpočet používá současné chunky; neprovádí novou extrakci, změnu chunkování, shrnutí ani klasifikaci.
4. Sledujte stav a počet platných chunků. Výpočet běží na pozadí, nikoli v otevřeném HTTP požadavku. Zavření stránky jej nezastaví; po novém přihlášení se načte stav ze SQL.
5. **Zastavit po probíhajícím požadavku** ukončí další zápisy. Právě běžící volání modelu může ještě doběhnout, jeho zrušená dávka se neuloží. Již potvrzené dávky zůstanou zachované.
6. Po chybě nebo přerušení použijte **Doplnit embeddingy** znovu. Kontrolují se revize chunků a dopočítávají pouze chybějící nebo neplatné vektory. Po restartu backendu aplikace úlohu automaticky neopakuje: po vypršení rezervace se zobrazí **přerušena** a správce ji explicitně obnoví.
7. Připravený index vyberte u konkrétní otázky, případně v porovnání výsledků. Výběr nemění výchozí index ingestace. Povolení modelu uživatelům a jejich skupinová oprávnění nadále spravujete v přehledu modelů.

Nomic již v dosavadním JHU cloudu má samostatný kompletní index `c536b88c-8df6-4280-8063-ff8d2bb273a9` (9 372/9 372 při diagnostice 2. 11. 2026). Jeho přidání z inventáře nemá vytvářet duplicitní index. U nového modelu, například jiného schváleného embeddingového profilu, vznikne nová tabulka a samostatný výpočet.

## Co zůstává chráněné

- Správa vyžaduje aktuální serverové oprávnění **Management** a přístup k modelu. Oprávnění se kontroluje i před zápisem každé dávky; starý token nebo podvržená hlavička oprávnění nestačí.
- Úloha nesmí přepočítávat aktivní výchozí index ingestace. Tato konzole jej ani nepřepíná a indexy nemaže. Výchozí Azure index, texty, ACL a existující alternativní vektory zůstávají zachované.
- Každý index má neměnnou identitu modelu/digestu, rozměrů, normalizace a query/document instrukcí. Změněný model vyžaduje nový profil; vektory různých prostorů se nemíchají a vstupy se tiše nezkracují.
- Korpus během přípravy neměňte. Změna vstupu během modelového volání zabrání zápisu dané dávky. Cloudová úloha neopravuje potichu sdílené hashe chunků. Neúplné pokrytí nebo změněný počet chunků na konci nehlásí úspěšné dokončení.
- Běží nejvýše jedna správní úloha na přesný tenant, zajištěná SQL rezervací a identitou úlohy napříč procesy. Kontrolní heartbeat běží odděleně od volání modelu. Zastaralý pracovník nesmí potvrdit výsledky do nově převzaté úlohy.
- SQL uchovává poslední úlohu každého tenantu a její počty, stav, UUID a bezpečný kód chyby; neukládá do ní texty dokumentů, vektory ani přihlašovací údaje. Nejde o úplný historický audit všech úloh.

## První aktivace v cloudu

1. Zachyťte výchozí stav a ověřte přesný SQL host, databázi a tenant. Migrace má nejprve read-only plán:

```bash
python migrate_index_jobs.py
```

2. Po schválení konkrétního cíle proveďte pouze aditivní vytvoření tabulky:

```bash
python migrate_index_jobs.py --apply \
  --expect-host ju-ai-search-sql-prod.database.windows.net \
  --expect-db ju-ai-search-sqldb-prod \
  --expect-tenant ju-prod
```

Migrace nezakládá indexy, nespouští reembedding a nemění existující řádky. Cloudový startup tuto tabulku automaticky nevytváří. Potřebný CLI musí být v nové backendové image. Pro starší image lze lokálně v izolovaném `APP_ENV=test` vygenerovat zkontrolovatelný payload příkazem `python migrate_index_jobs.py --console-script --expect-host <host> --expect-db <db> --expect-tenant <tenant>`. Generátor pouze vypíše kód; jeho následné spuštění v cílovém kontejneru už provádí schválenou DDL operaci. Payload vzniká z kanonického ORM schématu a nevyžaduje novou ORM třídu ve staré image.

3. Zkontrolujte oprávnění existující SQL identity k explicitnímu vytvoření nativní tabulky indexu. Funkce nevytváří novou identitu ani jí automaticky nepřiděluje role.
4. Použijte [guarded sidecar deployment](jhu-sidecar-azure.md), přidejte `--enable-index-preparation` a potvrďte dokončení migrací. Tím se do backendu explicitně nastaví `INDEX_PREPARATION_ENABLED=true`; jiné běžné releasy zachovají jeho předchozí hodnotu. Výchozí nastavení je vypnuté.
5. Nasaďte ověřený backend, helper a administraci, proveďte test nativního vytvoření/doplnění a zkontrolujte zachování původních dat. Do té doby je cloudová akceptace této verze otevřená.

`POST /api/search-indexes/jobs` přijímá `action=create|backfill`, registrovaný `embedding_profile` a pro backfill konkrétní `index_id`; vrací HTTP 202. `GET /api/search-indexes/jobs/current` načítá stav a `POST /api/search-indexes/jobs/{job_id}/cancel` žádá zastavení. Starý synchronní `/prepare` zůstává pouze lokální kompatibilitou.

Při vrácení staré image lze novou tabulku ponechat; nic se nemaže. Nový [ověřovací nástroj](deployment-preservation-test.md) ji umí načíst i se starším ORM. Pro striktní test výměny image pořizujte checkpoint až po samostatně schválené aditivní migraci a bez současně běžící indexovací úlohy.

## Okno průběhu

Po spuštění indexové úlohy se otevře přehled: celkové pokrytí chunků, počet hotových souborů, aktuální krok (kontrola, embedding, ukládání), stav každého souboru a hledání podle názvu. Soubor může čekat na více dávek; Hotovo znamená úplné současné pokrytí v tomto indexu, včetně vektorů zachovaných z předchozího běhu. Zavření okna úlohu neruší. V horní liště administrace nebo u úlohy jej lze znovu otevřít.

Stejné okno zobrazuje také průběh nové segmentace dokumentů: načtení, rozdělení textu, výpočet a ukládání, včetně jednotlivých neúspěšných souborů. Tento starší reindexační průběh je procesový a nepřežije restart backendu; trvalé SQL úlohy a resume patří k přípravě embeddingových indexů. Přepočet chunků vyžaduje dostupné přesné původní zdroje; dopočet alternativního indexu pracuje se stávajícími SQL chunky.
