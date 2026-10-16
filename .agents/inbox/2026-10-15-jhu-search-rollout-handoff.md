# Azure Deployment Handoff: JHU search rollout

- Status: functional-rollout-completed (uživatel explicitně schválil a agent provedl; performance/ANN acceptance pending)
- Created: 2026-10-15
- Related task: nasazení search sliců 1–5 na existující JHU
- Related ADR: `docs/adr/ADR-0026-reviewed-existing-app-releases.md`
- Related branch/PR: pracovní strom, bez nového commitu/PR

## Aktuální doplnění: JWT a hesla (lokálně dokončeno)

**LATEST v0.1.4:** backend rev8/image prod-v014-20261015-145009 a obě SWA nasazeny; actual API/auth/chat/PDF a live HTML/CORS/integrita prošly. Full local298passed/13skips, native keyword10passed. FTS1029/9372+DiskANNv3/coverage9372 připraveny. Běžný režim zůstává exact: ANN některé metadata kombinace timeoutují,100-query eval nedokončený (60User mean recall99,11%). User požádal o vysvětlení pomalosti místo výběru adaptivní strategie; žádná aktivace/adaptive routing implementována. Dva runtime smokes nyní retrieval3,927/2,117s vs28–29s, keyword1,123/0,365s, expansion1,608/1,163s. Neníp95. Nejnovější stav a omezení `docs/deployments/2026-10-15-jhu-search-rollout.md`; dřívější průběžné poznámky níže superseded. Žádná role/kapacita/credentials/datareset. Před dalším ANN rozhodnutím neaktivovat časově nevyhovující cestu.

**Novější výslovné zadání v0.1.4:** uživatel schválil v jediném slicu nativní keyword opravu, aktivaci ANN a zvýšení verze. Operátor `scratch/jhu_ann_release.py` má oddělený checkpoint `.local/deployments/jhu-ann-20261015/state.json` a DPAPI snapshoty `v014-*` v původním artifact adresáři. Předchozí zákaz ANN je tímto nahrazen; nic neslibuje reprezentativní p95/cold-start akceptaci. Lokální297passed/12skips a skutečný izolovaný Azure keyword10passed; native indexy a runtime nasazení právě probíhají. Dosavadní baseline rev7 zůstává kompatibilní návratovou verzí, CPU/RAM/SKU/RBAC/credentials/corpus se nemění. Výsledný stav musí být ověřen podle deployment reportu, nikoli dovozován z této průběžné poznámky.

**Aktuální výsledek má přednost před historickým plánem níže:** celý JHU funkční rollout proběhl, revize0000007, index9372/9372, backend+oběSWA a skutečné auth/chat/PDF/legacy smoke prošly. Finální počty431/9372/7/29/54 zachované, původní hashe0změn, žádná role/kapacita měněna. Kompletní záznam a rollback v `docs/deployments/2026-10-15-jhu-search-rollout.md`. Výkon je otevřený: vektor435–805ms, celý diagnostický retrieval28–29s ve2smoke; není p95 acceptance. ANN vypnuté. Starší věty „neschváleno/neprovedeno“ níže popisují historii před uživatelovým výslovným povolením provést deployment kroky.

Podpora JWT z existujícího KV a přechodu hesel je nyní implementována podle ADR-0027; aktuální přesný postup je v `2026-10-15-jhu-jwt-password-migration-handoff.md`. Nové hashe jsou Argon2id a nezávisí na JWT. Staré hashe mohou při úspěšném loginu přejít bez změny uživatelského hesla, pokud operátor dodá samostatný doložený legacy klíč. Hromadný reset není povinný; neprokázané/nevhodné účty vyžadují zvláštní postup. Nové secrets, runtime konfigurace ani JHU credentialy se zatím nezměnily. Rollback image musí podporovat Argon2, samotný původní image už nestačí po prvním upgrade. Celá lokální sada nyní **281 passed /10 expected skips**,132,33s; cloudové migrace/secrets/runtime smoke stále čekají.

## Proč tento handoff existuje

Uživatel přepnul Azure CLI na JHU a povolil pokračovat v auditu a lokální přípravě. Před cloudovými změnami chce schválit konkrétní zásah. Starší pravidlo o nedostupném Azure nahrazuje toto přímé povolení číst přes CLI; nejde o souhlas s migrací, buildem, deployem, rotací hesel ani změnou kapacity. Tento dokument zpřesňuje předchozí search handoffy pro skutečné JHU. Název prostředí `prod` není souhlas s jeho změnou; nepoužívat jej jako disposable Showcase schéma.

## Ověřený inventář — pouze čtení 2026-10-15

| Prostředek | Skutečný stav | Zamýšlený zásah po schválení |
|---|---|---|
| Azure directory | `c35f5da4-9a03-44e6-8bf9-92833634f6a7` | žádná změna |
| Subscription | `24e4a9a6-bab0-43f7-ba20-3b774704fade` / Microsoft Azure Enterprise | explicitní kontrola před každým zápisem |
| Resource group | `ju-ai-search-rg-prod` | použít existující |
| SQL server / DB | `ju-ai-search-sql-prod.database.windows.net` / `ju-ai-search-sqldb-prod` | cílené schema/tenant/ACL/profilové migrace |
| SQL | Standard **10 DTU**, Online, Swedish Central, compatibility 170, Czech_CI_AS, FTS zapnuto | kapacitu neměnit; není to původní Basic5DTU cíl |
| Container App | `ju-ai-search-ca-prod`, Swedish Central, 0,5 CPU / 1 GiB, min1/max3, Single revision | image update existujícího kontejneru; runtime nastavení samostatně |
| Předchozí image / revision | `juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod:prod-v-20261008-143422` / `ju-ai-search-ca-prod--0000005` | zachovat pro případný rollback |
| Registry / environment | `juaisearchcrprod` / `ju-ai-search-cae2-prod` | build jedinečného tagu, bez `latest`, žádná obnova prostředků |
| Managed identity | `ccacbf26-dcd6-4f7b-af7b-e3e769137de8` | neměnit identitu/RBAC |
| Key Vault | `ju-ai-search-kv-prod` | nyní bez čtení secrets či změny rolí; zachovat existující konfiguraci |
| Foundry | `ju-ai-search-aif-prod`, North Europe | modely neměnit |
| Model deploymenty | `text-embedding-3-large` model version `1`; `gpt-5.4-mini` version `2026-03-17` | návrh obou chat režimů na existující mini vyžaduje review |
| Frontendy | `ju-ai-search-swa-user-prod`, `ju-ai-search-swa-admin-prod` | matching release po kontrole endpointů a schválení |

Audit SQL se připojil přes existující inline SQL credential backendu, pouze v paměti, TLS s ověřením certifikátu. Bez Key Vaultu a bez tisku credentialu, tokenu, textu dokumentů, emailů nebo heslových hashů. Proběhly jen SELECTy, žádné DDL/DML/testovací objekty/modelová volání/zátěž.

| Tabulka | Tenant | Řádky |
|---|---|---:|
| documents | `ju` | 431 |
| chunks | `ju` | 9372 |
| users | `ju` | 3 |
| users | `ju-prod` | 4 |
| chat_threads | `ju-prod` | 29 |
| chat_messages | `ju-prod` | 54 |

Chunk/document tenant mismatch = 0. Běžící backend má přesný `TENANT_ID=ju-prod`. V dbo existuje pouze těchto pět tabulek; katalog profilů/indexů a relační ACL projekce chybí. `documents.title`, `chat_threads.title`, `chunks.content`, `chat_messages.content` jsou všechny VARCHAR (tituly 512, obsahy MAX). Definice/závislosti FTS ještě nebyly zachyceny. JHU DEV nebylo vybráno ani ověřeno; tento audit neprokazuje jeho existenci/neexistenci.

## Konfigurace a skutečné blokery

1. **Tenant:** lokální tenant adresář je `jhu`, ale aplikace používá `ju-prod` a korpus `ju`. Adresářový alias neopravňuje sjednotit DB identity automaticky. Návrh po ověření původu: dokumenty i jejich chunky převést `ju` → `ju-prod`, se zachováním UUID a obsahu. Předem spočítat přesné BIN2 + DATALENGTH hodnoty, ověřit závislosti a transakční rollback. Sedm uživatelů neslučovat automaticky: nejprve prověřit kolize identity, skupiny, původ a Management přístup. Staré `ju` účty nesmí získat nový přístup pouze aliasem.
2. **JWT/login:** Container App nemá explicitní `JWT_SECRET`; lokální JHU env má známý default, který nový cloudový backend odmítne. Staré hashe závisí na původním klíči. Lokálně už existuje oddělený legacy verifier + Argon2 přechod, takže reset není nutný při doloženém původním klíči. Je třeba připravit dostupného Management správce, nové JWT KV secret name/version, samostatný legacy klíč a kompatibilní rollback image podle nového JWT handoffu. Není ověřeno, jaký klíč skutečně načetl starý image a jaký vytvořil každý historický účet. Nevracet cloud na známý default; hodnoty secrets sem nepsat.
3. **Runtime bez env v image:** aktuální aplikace nemá explicitní endpoint/modely/profil a OpenAI credential. Po odstranění env souborů z image se musí dodat bezpečně za běhu. Zachovat existující SQL/storage credential a KV konfiguraci; nic automaticky nepřepisovat prázdným env. Pokud chybí funkční modelový credential, lze jej samostatně schváleně dodat jako Container App secret/secretRef, bez KV úprav. Existující nastavení KV samo nedokazuje úspěšný přístup runtime.
4. **Model:** lokální thinking konfigurace `gpt-5.4` nemá odpovídající deployment ve zjištěném seznamu. Návrh použít existující `gpt-5.4-mini` pro oba režimy, nebo nejprve samostatně schválit jiný model. Nevybírat náhradní embeddingový model.
5. **Data/schema:** před novým backendem dokončit Unicode, ACL a profilové úložiště; pouhé spuštění `init_db` či image update je nenahrazuje. Historické JSON embeddingy nemají prokázaný profil: zachovat, pro nový index standardně reembedovat stávající texty bez nové extrakce/chunkování. To bude skutečné volání embeddingového modelu a náklad vyžadující schválení.

## Potřebná nastavení (hodnoty bez secrets)

| Klíč | Hodnota / zdroj |
|---|---|
| APP_ENV / TENANT_ID / DATABASE_BACKEND | `prod` / návrh zachovat `ju-prod` / `azure_sql` |
| AZURE_SQL_HOST / AZURE_SQL_DB / AZURE_SQL_USER / AZURE_SQL_DRIVER | existující ověřené runtime hodnoty; účet `sqladmin`, ODBC Driver 18 |
| AZURE_OPENAI_ENDPOINT | `https://ju-ai-search-aif-prod.openai.azure.com/` (lokální konfigurace; runtime ještě nepotvrzeno) |
| AZURE_OPENAI_FLASH_DEPLOYMENT / AZURE_OPENAI_THINKING_DEPLOYMENT | návrh oba `gpt-5.4-mini` |
| EMBEDDING_PROVIDER / LLM_PROVIDER | `azure_openai` / `azure_openai` |
| AZURE_OPENAI_EMBEDDING_DEPLOYMENT / MODEL / MODEL_REVISION / DIMENSIONS | `text-embedding-3-large` / `text-embedding-3-large` / `1` / `1536` |
| AZURE_OPENAI_EMBEDDING_QUERY_PREFIX / DOCUMENT_PREFIX | oba explicitně prázdné; profil musí odpovídat backfillu |
| AZURE_BLOB_CONTAINER_ORIGINALS | zachovat existující `ju-originals-prod`; ověřit dostupnost originálů |
| JWT_SECRET | nový soukromý KV zdroj podle JWT handoffu nebo runtime secretRef; nikdy hodnota do repa |
| AZURE_OPENAI_API_KEY | funkční credential přes existující KV, nebo samostatně schválený secretRef |

Zkrácené názvy MODEL/REVISION/DIMENSIONS/PREFIX v tabulce mají vždy celý prefix `AZURE_OPENAI_EMBEDDING_`. Výchozí retrieval musí zůstat `exact`; skutečnou Blob konfiguraci je třeba ověřit, lokální JSON není důkaz jejího stavu.

## Postup pro samostatně schvalované nasazení

1. Dokončit čtecí audit: přesné tenant aliasy, účet/role/kolize, runtime JWT původ bez zveřejnění, FTS definice a závislosti, SQL permissions, stav backup/PITR a Blob search konfigurace. Potvrdit maintenance okno a zastavit ostatní deploye/ingestaci/zápisy. Vybrat ověřitelný obnovovací bod; samotné konstatování existence Azure backupu nestačí.
2. Připravit konkrétní migrační soubor a ověřit jej lokálně; předložit přesné DDL/DML a předpokládané počty. **Tento handoff zatím není hotovým schváleným SQL migračním skriptem.** Žádný automatický full refresh. Řízeně převést identity korpusu a Unicode podle slice2 handoffu, zachytit/obnovit FTS (DDL může vyžadovat vlastní autocommit), bez mazání dokumentů a bez převodu zpět na VARCHAR.
3. V prostředí s explicitním `APP_ENV=prod`, `TENANT_ID=ju-prod`, potvrzeným SQL host/DB a privátně dodanými credentials spustit nejprve read-only audit `migrate_search_acl.py`. Po schválení použít `--apply --expect-host ju-ai-search-sql-prod.database.windows.net --expect-db ju-ai-search-sqldb-prod --expect-tenant ju-prod`. Skript vytváří ACL grant tabulky a rebuild; nedělá Unicode ani alias opravy. Na tomto JHU zatím NESPŮŠTĚNO.
4. Po samostatném schválení vytvořit katalog/index a embeddingy pomocí `migrate_search_vectors.py --create --reembed` se stejnými třemi `--expect-*`. Zachovat JSON, zapsat vrácené index/profile ID, ověřit úplné aktuální coverage. Aktivaci udělat až po kontrole, samostatně `--index <vrácené UUID> --activate` s těmito guards. Při aktivaci počítat znovu skutečný počet chunků, audit9372 není neměnný předpoklad. Bez `--proven-legacy`, bez ANN DDL v této fázi.
5. Samostatně připravit runtime nastavení/secretRefs, soukromý JWT/login migraci a nový frontend. Žádné nové KV role, identity, databáze ani kapacita implicitně. Pro cloudový stav bez aktuálního image aplikace nespoléhat na startup seeding. Zachovat staré hodnoty bezpečně mimo repozitář a nevypisovat je.
6. Spustit read-only release plán níže. Vyřešit všechny blokery. Následný `-Apply` vyžaduje konkrétní souhlas s buildem a image update; potvrzující přepínače neslouží jako náhrada tohoto souhlasu.
7. Po matching frontend release otestovat nový login/Management správu, hybrid chat v češtině, správný dokument/citaci/PDF a uloženou historii; odmítnout jiný tenant, falšované skupiny a nepovolené chunky/sousedy. Ověřit nové dokumentové embeddingy a zachované UUID/počty. Health200 samo není akceptace.
8. Teprve další slice: reprezentativní JHU recall/performance podle slice5. ANN nezapínat před ≥100 dotazy, recall@30≥95 %, p95 celého retrievalu≤1s při souběhu1 a3 a≥200 requestech pro každý. Report označit skutečným Standard10DTU tierem; Basic5DTU brána zůstává neověřená.

### Bezpečný plán z VS Code

```powershell
.\deploy_backend.ps1 -Client jhu -Environment prod `
  -ExpectedSubscriptionId 24e4a9a6-bab0-43f7-ba20-3b774704fade `
  -ExpectedAzureTenantId c35f5da4-9a03-44e6-8bf9-92833634f6a7
```

Bez `-Apply` jen čte a vypíše ne-secret plán včetně blockerů. `-Apply` navíc vyžaduje přesný `-ExpectedCurrentImage`, `-MigrationConfirmed`, `-JwtMigrationConfirmed` a žádný runtime blocker. Používá jen existující app, nezmění tenant/env/secrets/SQL/CPU/ingress/identity a nespouští ingestaci. SecretRef existence není důkaz platnosti jeho hodnoty; funkční kontrola je povinnost samostatného kroku. Kontrola změny aplikace po buildu není atomický zámek: současné deploymenty je nutné zastavit. `deploy_all.ps1` je záměrně blokovaný, aby plán backendu nespustil legacy frontend deploy.

## Rollback

- Uchovat původní image/tag/revision, provozní konfiguraci a potvrzený DB obnovovací bod. Snapshot obsahující secrets držet mimo Git a výstupy AI.
- Samotný image rollback lze provést po schválení `az containerapp update` s předchozím image a stejným container name; nesmaže nové tabulky a **nevrací** data, JWT/hash ani konfiguraci. Předchozí image má starší auth/ACL slabiny: při nouzovém návratu omezit veřejný přístup samostatně schváleným zásahem.
- Nové grant/catalog/index tabulky a Unicode sloupce ponechat, nemažou se kvůli rollbacku. Profilové indexy zachovat. Pro návrat z ANN použít stejnoprofilový exact, bez dalšího embeddingového modelu.
- Tenant sjednocení může ovlivnit starý backend: před nasazením připravit přesnou zpětnou datovou migraci podle zachovaných UUID nebo obnovu z potvrzeného bodu. Nevracet slepě všechny nové řádky z `ju-prod` na `ju`.
- JWT/hash rollback se řeší společně se správou loginů; neobnovovat veřejně známý klíč. Převod textu nevracet na VARCHAR; ztracené znaky vyžadují zvláštní opravu z originálů, nyní bez full refresh.

## Co je skutečně ověřeno a co čeká

- Native exact/ANN funkční testy na izolovaném Showcase: passed; nejsou akceptací JHU migrace nebo runtime.
- JHU inventář/SELECT audit výše: passed, žádné cloudové změny.
- Lokální ověření: `pytest tests/test_backend_deployment.py tests/test_search_benchmark.py -k 'backend_deployment or excluded_from_docker'` — **31 passed, 23 deselected** (Windows PowerShell 5.1 a7, fake Azure CLI; 1 warning). Ověřeno plan/apply, subscription/directory/image/tenant/JWT/profile guards, broken secretRef, chyby CLI/buildu, zachování runtime a souběžná změna. Skutečný ACR build tím není ověřen.
- Nový release skript skutečně proběhl proti JHU v režimu **plan**, exit0, pouze account/containerapp/acr show. Zachoval `ju-prod`, vypsal správný image/revision a 12 očekávaných blockerů chybějících modelových/profilových runtime nastavení a JWT. Žádné build/update volání ani jiné zápisy.
- Otevřeno: všechny cloudové zápisy, migration SQL, účet/kolize/login plán, runtime credentials/API/PDF smoke, reprezentativní benchmark, ANN aktivace.

## Hodnoty a schválení od člověka (bez secrets)

### Upřesnění uživatele 2026-10-15

- **JHU Key Vault přístup backendu ověřen (read-only ARM/RBAC):** Container App má stále SystemAssigned principal `ccacbf26-dcd6-4f7b-af7b-e3e769137de8`; přímo na scope `ju-ai-search-kv-prod` existuje role **Key Vault Secrets User** (definition `4633458b-17de-408a-b874-0445c86b69e6`), bez podmínky. Vault má enableRbacAuthorization=true, publicNetworkAccess=Enabled a defaultAction=Allow. Žádná role/policy/network konfigurace nebyla změněna, hodnoty secrets se při této kontrole nečetly. Uživatelova vzpomínka na reader přístup byla potvrzena jako Secrets User, nikoli pouze obecný Reader. Plán nemusí vyžadovat nový grant backendu; lze využít existující KV přístup. Úspěšné čtení konkrétního secretu běžícím backendem ještě není runtime testem potvrzené. Současný app/core/config.py umí z KV načítat chybějící SQL/OpenAI/Storage/Postgres credentials, nikoli JWT_SECRET: pro JWT je nutné explicitně doplnit podporu/Key Vault secret reference, zachovat společný plán změny klíče a heslových hashů. Secret ani nový kód nebyly vytvořeny.

- **Omezená Azure oprávnění:** uživatel není plný Azure administrátor; uvádí možnost secrets v Key Vaultu vidět a vytvářet, nikoli udělovat přístup/role. Nepožadovat automaticky role assignment, změnu access policies ani správy identit. Přístup uživatele k secretu nedokazuje, že jej může číst managed identity backendu. Preferovat postup využívající stávající oprávnění; pro JWT zvážit Container App secret + env secretRef, pokud současná oprávnění dovolují aktualizaci aplikace, bez závislosti na novém KV grantu. Existující runtime KV přístup ověřit odděleně; nehádat jeho funkčnost. Vytváření secretů a jejich přiřazení aplikaci nadále provádět pouze v dohodnutém rozsahu, hodnoty nikdy do chatu/Gitu.

- Bod1: uživatel dovolil změnu identity korpusu `ju` → `ju-prod`. Platí pro ověřené dokumenty a jejich chunky; není to svolení automaticky slučovat uživatelské účty. Provedení čeká na konkrétní otestovanou migraci, rollback a pořadí s matching backendem; tato již udělená autorizace se nemá znovu vyžadovat pro stejný rozsah.
- Bod4: schváleno použití existujícího `gpt-5.4-mini` pro oba chat režimy. Nevytvářet nový model deployment; embedding zůstává samostatně `text-embedding-3-large`.
- Bod2: uživatel žádá vysvětlení JWT/hesel. Dosud se žádné heslo, signing key, hash ani cloudová konfigurace neměnily. Rotace JWT a reset účtů nejsou tímto schválené.
- Bod3: uživatel nabízí vytvoření potřebných secrets; připravit pouze názvy a bezpečný postup, bez žádosti o hodnoty v chatu. Nejde o souhlas agenta vytvářet secrets nebo měnit KV role.
- Bod5: uživatel žádá vysvětlení schema/embedding migrace; reembedding/modelové náklady, širší DDL a deployment dosud nejsou schválené.
- Existující lokální `.env` soubory zachovat; změněno je pouze jejich vyloučení z Docker image/build contextu. Obsah tenant env se v této přípravě neměnil. Aktuální požadavek je vysvětlení, proto zatím žádné nové Azure zápisy.

```yaml
target_confirmed: # JHU prod výše, nebo jiný explicitní cíl
maintenance_window:
tenant_corpus_migration_ju_to_ju_prod_approved: true # autorizováno, dosud neprovedeno; pouze docs/chunks
users_and_manager_login_strategy:
private_jwt_and_password_migration_strategy:
thinking_mini_deployment_approved: true # existující gpt-5.4-mini pro oba chat režimy
backup_restore_point_confirmed:
schema_backfill_runtime_and_deployment_scope_approved:
```
## Poznámka k úklidu repozitáře

Privátní JHU operátory byly po vydání v0.1.4 přesunuty ze `scratch/` do `.local/operations/`; historické cesty níže nejsou aktuálním spouštěcím místem. Snapshoty/checkpointy a data zůstávají zachované. Aktuální postup spuštění a běžného release je v kořenovém README; detaily úklidu v `docs/development/repository-cleanup.md`. Tento přesun neprovádí další migraci ani aktivaci ANN.
