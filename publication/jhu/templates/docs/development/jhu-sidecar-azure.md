# JHU modely přímo z Azure Container Apps

Funkční JHU rollout backendu, sidecaru a obou konzolí byl ověřen 2026-10-29. User vector/hybrid a Management keyword fungují; Management vector/hybrid má nevyřešený 10s SQL exact timeout. Nový rollout stále vyžaduje níže uvedené target/session/capacity guards.

Kód podporuje cloudové připojení bez VPN na notebooku: backend i userspace VPN helper běží ve stejné replice existující Container App. Cloudová aktivace a její živé ověření jsou samostatný krok; lokální úspěch není důkaz cloudové konektivity. Pro lokální vývoj dál používej [managed start](jhu-managed-local.md).

## Připojení a secrets

Backend: `JHU_CONNECTION_MODE=sidecar`, `APP_ENV=dev|prod`, přesný `TENANT_ID`, `JHU_SIDECAR_APP_NAME`, pevný `JHU_LLM_ENDPOINT`, `JHU_LLM_ALLOW_HTTP=true`, `JHU_KEY_VAULT_NAME` a reference na API username/password/gateway key. ACA poskytuje `CONTAINER_APP_NAME`, `CONTAINER_APP_REVISION`, `CONTAINER_APP_REPLICA_NAME`, `IDENTITY_ENDPOINT` a `IDENTITY_HEADER`; nenahrazuj je vlastními hodnotami při deploymentu.

Helper dostane stejný runtime kontext a reference na VPN username/password/profile/gateway key. API účet nepotřebuje. Obě části používají přímo systémovou managed identity, bez Azure CLI nebo env credentials. Stávající role identity musí dovolovat čtení vybraných secrets; tento rollout nevytváří RBAC. Interní gateway je pouze `127.0.0.1:18081`; TCP process probe je `18082`. Ingress zůstává backendový port 8000, bez dalších veřejných portů.

Potřebné názvy v existujícím Key Vaultu:

| Secret | Obsah | Čte |
|---|---|---|
| `ju-ai-search-vpn-username-prod` | VPN login | helper |
| `ju-ai-search-vpn-password-prod` | VPN heslo | helper |
| `ju-ai-search-vpn-client-config-prod` | Celý schválený původní Client.ovpn | helper |
| `ju-ai-search-jhu-api-username-prod` | Basic API login | backend |
| `ju-ai-search-jhu-api-password-prod` | Basic API heslo | backend |
| `ju-ai-search-jhu-gateway-key-prod` | Nových 32 náhodných bytes jako 64 malých hex znaků | oba |

Profil ani hesla nekopíruj do repa, image, shell historie nebo chatu. Původní externí `.ovpn` neměň; loader z něj odvodí omezenou runtime konfiguraci. Nový capability secret vytvoř bezpečným generátorem a SDK/portálem bez výpisu, nikdy jako veřejný příkladový klíč. Rotace vyžaduje koordinovaný restart helperu a backend refresh/restart; během rotace neodesílej modelové dotazy. Kontejnery mají společnou systémovou identitu, takže rozdělení čtených referencí není izolace RBAC mezi kontejnery.

## Reprodukovatelný read-only plán

Z kořene repa po `az login` použij správný účet. Následující příkaz **nic nemění**; chybějící image a secrets vypíše jako blokery:

```powershell
.venv\Scripts\python.exe deploy_jhu_sidecar.py `
  --subscription 24e4a9a6-bab0-43f7-ba20-3b774704fade `
  --azure-tenant c35f5da4-9a03-44e6-8bf9-92833634f6a7 `
  --resource-group ju-ai-search-rg-prod --app ju-ai-search-ca-prod `
  --tenant ju-prod --sql-host ju-ai-search-sql-prod.database.windows.net `
  --sql-database ju-ai-search-sqldb-prod --vault ju-ai-search-kv-prod `
  --target-endpoint http://160.217.182.41:11434 `
  --revision-suffix jhu-v017-cloudtest `
  --verified-model qwen3.8:latest --app-version v0.1.7
```

Před jiným nasazením změň explicitní verzi/revision suffix. Nástroj nečte `.env` a nemění je. Pro úplný plán přidej `--backend-image <acr/repository@sha256:digest>` a `--helper-image <acr/repository@sha256:digest>`. Obě image musí být v témže existujícím ACR. `--verified-model` je potvrzení konkrétního modelu z předchozího probe, ne jeho nové ověření. `--advanced-model-deployment` vyplň pouze pro skutečně existující ověřený GPT‑5.4 deployment; bez něj je pokročilý profil nenakonfigurovaný. Výchozí GPT-mini a embedding deployment se zachovávají.

Nástroj připraví backend se stávajícími resources a helper 0,25 CPU / 0,5 GiB. Na současném cíli to je celkem 0,75 CPU / 1,5 GiB; maxReplicas se omezí na 1 a WEB_CONCURRENCY na1. Vyžaduje to kapacitní souhlas. Přepínače `--backend-cpu`, `--backend-memory`, `--helper-cpu`, `--helper-memory` dovolují jiné explicitně posouzené rozdělení. Původní0,5CPU/1Gi nelze zároveň zachovat backendu a přidat helper bez navýšení součtu.

## Řízené provedení

1. Schval konkrétní cíl, secret creation, image build/push, kapacitu/repliky, případné modelové SQL migrace a backend/frontend release samostatně. Ověř VPN session policy a vypni lokální helper během prvního cloudového přihlášení. Systémová VPN na notebooku nesmí maskovat cloudový test.
2. Sestav root `Dockerfile` a `scripts/vpn_spike/Dockerfile` ze schválených současných zdrojů, nahraj je do existujícího ACR a zaznamenej digesty. Nástroj image nesestavuje ani neposílá.
3. Ověř aktuální SQL tabulky; jen pokud chybějí, proveď schválené `migrate_model_access.py`, `migrate_model_registry.py`, `migrate_model_metadata.py`, `migrate_model_limits.py` s jejich vlastními target guards. Backend image je obsahuje. Neprováděj automatický reembedding ani aktivaci indexu. Příprava embedding indexu v admin UI zůstává local-only; cloud backfill je samostatná operace.
4. Spusť nový plán s digesty. Zkontroluj `blockers=[]`, fingerprint, previous_revision, kapacitu a modelové nastavení. Před Apply znovu ověř účet a ukonči ostatní deploymenty.
5. Ke stejnému příkazu přidej `--apply --expected-fingerprint <aktuální plán> --expected-revision <aktuální revize> --migrations-confirmed --session-policy-confirmed --models-confirmed` a při změně resources také `--resources-confirmed`. Při aktualizaci už existujícího sidecaru musí být vyřešen souběh relací staré/nové revize a přidán `--overlap-confirmed`. Single revision mode sám souběh neřeší.
6. `apply-requested` znamená přijatý ARM zápis, nikoli dokončenou akceptaci. Timeout se automaticky neopakuje: nejprve přečti skutečný stav, aby nevznikly dva rollouty. Nástroj PATCHuje pouze template a location; zachovává existující env/secretRef hodnoty v paměti, bez generování jejich kopie na disk. Kontrola fingerprintu před zápisem plus dostupný If-Match omezuje závody; bez ETag nevytváří atomický CAS.
7. Samostatně použij read-only plány `deploy_frontend.ps1` pro existující user/admin SWA, ověř backendURL, tenant theme a CORS, potom jejich schválený Apply. Starý `deploy_backend.ps1` je určen pouze pro single-container image release a nesmí nahradit dvoukontejnerový template.

## Akceptace a náprava

- Backend health/verze a přihlášení musí fungovat i při nedostupné VPN. Stav v administraci: autentizovaný `GET /api/models/connection`. Veřejný health nevrací secret ani detaily tunelu.
- Z cloudového backendu ověř discovery a syntetický český dotaz s citací skutečně vybraným JHU modelem, vedle něj Azure-mini. Pro embedding ověř jedno konkrétní připravené povolené index UUID; pokud cloudový index ještě není, nezaměňuj discovery s jeho naplněním. Oprávnění a tenant se nemění.
- `POST /api/models/connection/refresh` obnovuje pouze backendový KV snapshot. Bootstrap chyba helperu potřebuje opravu reference/secretu a řízený restart revize; neprovádí nekonečné automatické přihlášení. Ztráta spojení ukončí dotaz bez replay/fallbacku.
- Helper běží UID 65532 bez požadavku TUN/NET_ADMIN. Privátní runtime soubory jsou 0600/0700 v efemérním ACA filesystemu, nikoli sdílený volume ani deklarovaný tmpfs. Nezapínej raw SDK/OpenVPN/request-body logování.
- Rollback nejprve zastaví/deaktivuje novou VPN revizi (ověř konec relace), potom reaktivuje předchozí zaznamenanou revizi a vrátí předchozí frontend artefakty. Neprováděj v rollbacku smazání SQL tabulek, indexů, korpusu ani secrets. Předchozí frontend potřebuješ uchovat před releasem. Pouhé zapnutí staré revize při běžící nové může způsobit souběžné VPN přihlášení.

## Lokální regrese bez Azure

```powershell
.venv\Scripts\python.exe -m pytest tests/test_jhu_sidecar.py tests/test_jhu_sidecar_deployment.py tests/test_jhu_transport.py tests/test_jhu_gateway.py -q --tb=short
docker build --tag ai-search-vpn-sidecar:local scripts/vpn_spike
```

Mocky ověřují MI-only bootstrap, přesnou vazbu repliky, společný transport a deployment guards. Nenahrazují živou cloudovou UDP/MI/modelovou akceptaci.

## Souběžný lokální vývoj

Nasazený cloudový sidecar používá existující VPN účet z KV. Podpora více současných relací téhož účtu není ověřená. Pro další živé API kontroly preferuj existující ACA cestu; lokální managed helper se stejným účtem nespouštěj současně bez ověření serverové politiky nebo koordinace relací. Pro nezávislý souběžný vývoj lze později použít oddělený VPN účet. Tento deployment žádný nový účet nevytvářel.
