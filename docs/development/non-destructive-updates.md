# Aktualizace se zachováním dat a nastavení

Implementovaný krok je trvalé cloudové nastavení. Každé existující prostředí potřebuje při prvním převodu samostatnou migraci a zachycení současných hodnot; samotné vydání zdrojů tento převod neprovádí. Architektonické rozhodnutí: ADR-0042 v hlavním vývojovém repozitáři.

JHU převod a skutečný restart byly dokončeny2026-10-29: [provedený rollout a důkazy](../deployments/2026-10-29-durable-settings-rollout.md).

## Co současný release uchovává

| Stav | Úložiště | Chování při běžné výměně image |
|---|---|---|
| Účty, heslové hashe, skupiny | SQL `users` | Existující řádky se nemažou ani znovu neseedují v cloudu. |
| Konverzace a zprávy | SQL `chat_threads`, `chat_messages` | Zůstávají ve stejné databázi pod stejným tenantem. |
| Dokumenty, chunky, vektory a aktivní index | SQL, profilové tabulky | Běžný image release neprovádí refresh/backfill ani změnu indexu. |
| Originály dokumentů | Blob Storage; u lokálních zdrojů disk | Cloudové originály musí existovat v trvalém Blob úložišti. Soubor pouze uvnitř kontejneru není trvalý. |
| RAG prompty CS/EN | Nově SQL `tenant_settings`, `prompts.json` | Uložená hodnota má přednost před souborem nové image. |
| Chunkování, vyhledávání a prompt shrnutí | Nově SQL `tenant_settings`, `search_config.json` | Stejný zdroj pro API, retrieval i synchronní ingestaci. |
| Kategorie, pravidla a prompt klasifikace | Nově SQL `tenant_settings`, `classification_config.json` | Uložené hodnoty zůstávají mimo image. |
| Modelové registrace, přístupy, popisy a limity | Stávající SQL modelové tabulky | Touto změnou se nemění. |

`deploy_backend.ps1` aktualizuje image existující jediné aplikační komponenty; JHU se sidecarem používá samostatný `deploy_jhu_sidecar.py`. `deploy_all.ps1` je blokovaný. `init_db()` používá vytváření chybějících tabulek, nikoli drop/reset dat. `reset_users_db.py`, mazací utility a full-refresh nejsou součást běžného release. Změna databázového cíle, přesného `TENANT_ID` nebo podpisového/legacy klíče může způsobit nedostupnost původních dat či přihlášení bez smazání řádků; release je musí zachovat.

Předchozí cloudové souborové zápisy promptů byly efemérní. Search/classification měly také legacy Blob kopie pod `config/…`, ale synchronní ingestace/retrieval četly soubory. Nový cloudový runtime používá jediný SQL zdroj. Legacy Blob konfigurace se do něj **neimportují automaticky** a nadále se nezapisují; Blob originály dokumentů se nemění.

## Pravidla nového úložiště

- Platí v `APP_ENV=dev/prod`, pro uvedené tři dokumenty. `local/test` zachovává ignorované souborové overlaye; nepřepisuje veřejné výchozí soubory.
- Klíč obsahuje SHA-256 přesného `tenant_id` a název dokumentu. `ju-prod`, `ju-dev`, `jhu` i varianty velikosti písmen jsou oddělené. Alias `ju → jhu` se používá pouze pro souborové výchozí hodnoty.
- Pokud tabulka existuje a pro tenant/dokument není řádek, použije se dosavadní výchozí soubor. Start ani nový release do tabulky nic nekopíruje.
- Nedostupná nebo chybějící tabulka a neplatná uložená data ukončí načtení/zápis chybou; neaktivují skrytý návrat k jiným nastavením. Konfigurační API vrátí bezpečný `503/tenant_settings_unavailable`. Zápis potvrdí úspěch až po SQL commitu.
- Každý dokument je uložen atomicky. Interní revision brání souběžnému zápisu nad již načteným SQL řádkem; existující API zatím nepředává klientskou revizi a dva editory mohou stále uložit celé nastavení v pořadí posledního úspěšného zápisu. Nejde o historii verzí nastavení.
- Cloudový startup tuto tabulku nevytváří; je nutná samostatná aditivní migrace. Změna schématu, reembedding, aktivace indexu, provisioning a release zůstávají oddělené operace.

## První převod existujícího prostředí

Před prvním release zastav úpravy nastavení a vytvoř soukromý checkpoint. Exportuj současné CS/EN prompty z běžící aplikace a aktuální search/classification konfigurace z API a legacy Blob kopií. Porovnej je také se synchronně používanými soubory; případný rozpor musí operátor vyřešit výběrem skutečně požadovaných hodnot. Neodvozuj je pouze z nového checkoutu. Jestli původní image již zanikla, může být stará vlastní souborová hodnota bez zálohy neobnovitelná.

Do jednoho soukromého adresáře ulož **všechny tři** zkontrolované JSON soubory: `prompts.json`, `search_config.json`, `classification_config.json`. CLI ověřuje strukturu před DDL/zápisem; plán vypíše pouze cílový host, DB, přesný tenant a hashe dokumentů, nikoli obsah promptů. Plán neotevírá databázové spojení. Použij existující schválený cloudový runtime/env a přístup k SQL; credentials nedávej do argumentů ani dokumentace.

```powershell
python migrate_tenant_settings.py --import-dir "<soukromy-overeny-export>"
python migrate_tenant_settings.py --import-dir "<soukromy-overeny-export>" --apply --expect-host "<overeny-host>" --expect-db "<overena-DB>" --expect-tenant "<presny-tenant>"
```

Výchozí spuštění je plán. Apply vytvoří pouze chybějící `tenant_settings` a importuje pouze dosud neexistující řádky. Opakování vrací `preserved` a nepřepíše novější správní změny. Import všech řádků používá jednu transakci; chyba importu ji vrátí zpět. Samotná existence tabulky po selhání DDL závisí na databázi, data ostatních tabulek se nemění. Bez `--import-dir` se vytvoří jen prázdná tabulka — hodí se pro novou instalaci, nenahrazuje zachycení nastavení již používaného prostředí.

Migraci proveď před nasazením nového backendu. Starý backend SQL overrides nečte; nezapínej paralelně starý a nový editor nastavení. Po dobu přechodu zachovej původní JSON/Blob checkpointy a předchozí image. Běžný rollback na starý kód ponechá tabulku i data v SQL, ale starý kód nové nastavení neuvidí. Před návratem exportuj poslední SQL hodnoty a explicitně obnov souborové/Blob konfigurace pro starou verzi; neodstraňuj databázi ani novou tabulku.

## Akceptace a následující krok

Opakovatelný [test zachování dat při nasazení](deployment-preservation-test.md) používá `verify_deployment.py`: striktní read-only SQL/vektorové otisky před/po, volitelně skutečné Blob byte streamy a samostatný provozní checklist. Umí běžet i ve staré image přes veřejný konzolový bundle; snapshoty musí zůstat mimo efemérní kontejner.

Před/po release porovnej cílovou DB, přesný tenant, počty a vybraná UUID účtů/konverzací/dokumentů/chunků, aktivní index a hashe nastavení. Proveď skutečný login existujícího účtu, otevření staré konverzace/PDF, uložení nastavení a ještě jednu výměnu/restart revize. Po restartu ověř stejné hodnoty ve správním API i synchronním loadu ingestace. Během porovnávání omez zápisy nebo zohledni legitimní provozní změny. Před mazacími zásahy je potřeba samostatný ověřený plán obnovy.

Lokální regrese používají skutečnou dočasnou SQLite databázi, odpojení spojení, novou sadu image defaults a opakovaný startup. Samy neprokazují Azure SQL/ACA runtime ani obnovu produkční zálohy; konkrétní rollout potřebuje vlastní cloudovou akceptaci uvedenou výše. Po dokončeném převodu je jediný doporučený další slice izolovaný test obnovy zálohy, se samostatně zkontrolovaným plánem zdrojů a bez zásahu do živé databáze.
