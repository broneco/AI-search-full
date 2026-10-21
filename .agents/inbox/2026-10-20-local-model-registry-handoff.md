# JHU: registr lokálních modelů — cloudový handoff

Zdrojová implementace je lokální; tento dokument neopravňuje ke cloudovým zápisům. Cílový datový tenant je přesné `ju-prod`; konfigurační alias je `jhu`. Existující host/DB, subscription a resource group musí operátor ověřit před Apply. Žádné secrets ani RBAC se nemění.

## Samostatné operace

1. Ověřit síť z Container App k JHU službě. VPN notebooku tuto cestu nezajišťuje. Použít stávající Basic credentials z prostředí/KV; nevypisovat je.
2. Spustit `migrate_model_registry.py` nejprve bez přepínačů. Po schválení cíle použít `--apply --expect-host <ověřený-host> --expect-db <ověřená-DB> --expect-tenant ju-prod`. Vznikne pouze `dbo.tenant_model_registry`: PK tenant_key/model_id, tenant_id, kind, profile_json, user_visible, revision, updated_by, updated_at. Staré model_access_policies a vektorové tabulky se nemění.
3. Samostatně vydat backend a obě konzole. Registry JSON/PDF a recepty musí být v image/wheelu; secrets se nekopírují do zdrojů.
4. Management načte inventář, explicitně přidá modely pro testování a ověří zvolené malé syntetické dotazy. Nespouštět automaticky generace všech modelů. Zveřejnit checkboxem jen ověřené varianty; nadále respektovat modelovou a dokumentovou ACL.
5. Cloudový embeddingový index vyžaduje zvlášť schválené vytvoření profilové tabulky/backfill. UI cloudové přípravy zůstává zakázané. Aktivace ingestion defaultu není součástí uživatelské volby indexu ani tohoto handoffu.

## Akceptace a návrat

Ověřit restart persistence a CAS konflikt, izolaci přesného tenantu, skrytí nezveřejněných profilů, odmítnutí podvrženého model_id/search_index_id a jediný zvolený index. Zachovat dosavadní Azure model/index. Při problému odškrtnout publikaci daného profilu nebo zvolit původní Azure index; nespouští se automatický fallback. Tabulku/vektory neodstraňovat — starší soubory ignorují registr, novější zachovávají jeho audit/revize. Změny infrastruktury, škálování, přepis secrets a plošný reembedding nejsou autorizované.
