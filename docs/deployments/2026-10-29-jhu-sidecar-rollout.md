# JHU deployment 2026-10-29: backend, VPN sidecar a obě konzole

- Status: completed deployment and cloud connectivity acceptance; Management exact/vector performance issue remains open
- Created: 2026-10-26
- Related task: connectivity slice4a, cloud runtime and guarded rollout
- Related ADR: [ADR-0041](../../docs/adr/ADR-0041-jhu-aca-sidecar.md)
- Source: reviewed working tree after published v0.1.7; containers/SWAs deployed, new source Git changes remain unpublished

## Dokončený rollout a skutečný výsledek

Uživatel výslovně schválil kompletní deployment včetně čtyř modelových migrací, obou image, backendu, obou konzolí a celkové kapacity0,75CPU/1,5Gi/max1. Nasazené jsou aktuální pracovní zdroje s verzí v0.1.7; GitHub/Forgejo nebyly tímto rolloutem aktualizované. Následující skutečný stav nahrazuje starší přípravné poznámky níže.

| Položka | Ověřený výsledek |
|---|---|
| Aktivní a zdravá revize | `ju-ai-search-ca-prod--jhu-v017-1029-173112`, Running,1 replika |
| Backend image | `juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod@sha256:e639c44ada2f207a1fc4b6771c9d6ed47d99073a73e4af60d95bbc6e6449fea7` |
| Helper image | `juaisearchcrprod.azurecr.io/jhu-vpn@sha256:006c3070ecc2295cfd34d0c80e34c30d006d2bfe57d3e6aa7c58daa723275de3` |
| Kapacita | Backend0,5CPU/1Gi + helper0,25CPU/0,5Gi; min1/max1,1 backend worker |
| Původní revize | `ju-ai-search-ca-prod--0000008`, zachována neaktivní s0replikami |
| SQL modelové migrace | `model_access_policies`, `tenant_model_registry`, `model_descriptions`, `model_runtime_settings` vytvořeny čtyřmi guarded CLI |
| Korpus před/po |431 dokumentů /9372 chunků /1 index; beze změny |
| Aktivní index před/po | `b1e81c70-686c-481a-bbff-e15f034288ef`; beze změny, exact |
| SQL tier | Stávající Standard10DTU zachován; žádný SQL upgrade |
| Identity, ingress a klíče | Stávající system MI, ingress, JWT/legacy/SQL/OpenAI runtime hodnoty a reference zachovány |
| User konzole | [nice-forest-03f01f203.6.azurestaticapps.net](https://nice-forest-03f01f203.6.azurestaticapps.net) |
| Admin konzole | [kind-tree-0c95d5203.2.azurestaticapps.net](https://kind-tree-0c95d5203.2.azurestaticapps.net) |

### Provedená akceptace

- Nová backendová health200/verzev0.1.7, existující serverová identita a Management GET API200. Managed connection skutečně `sidecar/ready`, attempt1/generation1/TLS1, bez systémové či lokální helper VPN. KV secrets přečetly skutečné ACA managed identities; žádné nové RBAC nebo další VM.
- Cloud discovery18modelů bez chybných metadat. GPT‑5.4-mini a Qwen jsou dostupné pro chat/shrnutí/klasifikaci. GPT‑5.4 je správně nenakonfigurovaný, protože reálný deployment chybí; nedochází k jeho záměně za mini.
- Přímo v ACA backendu prošly skutečné document/query embeddingy přes VPN: Nomic768/2dokumenty1582ms, MXBAI1024/2dokumenty6622ms. Syntetické vektory se neukládaly; nevytvořil se žádný nový index/registrace modelu. Nomic/MXBAI cloudové indexy je stále nutné připravit explicitně odděleným backfillem.
- User vector+Qwen200/5citací/uložený model a původní index:41703ms, z toho generation37240ms a model load11174ms. User vector+mini200/5citací/provenance:9750ms, generation3288ms. User výchozí hybrid+mini200/5citací:6296ms. Management explicitní keyword+Qwen200/5citací:37859ms. Jde o jednotlivé funkční dotazy, nikoli p95 či výkonovou akceptaci.
- Během těchto testů vznikly jen vlastní dočasné konverzace a byly odstraněny přes scoped API. Správce vytvořil jediný syntetický User účet; skutečný heslový login a `/auth/me`200, Management discovery správně403. Účet byl odstraněn s přesným UUID+email+tenant guardem. Veřejná anonymní registrace správně403; nebyla obcházena ani povolena.
- Oba produkční Next buildy/TypeScript prošly. Veřejné HTML a7JS souborů každé konzole se hashově shodují s novými artefakty, CORS obou originů povolen. Žádná vizuální browserová akceptace nebo dlouhodobý cloud soak se netvrdí.
- Oprávněný User PDF preview skutečně200/application/pdf/platná `%PDF` hlavička, obsah se neukládal ani nevypisoval. Závěrečná connection kontrola stále sidecar/ready, attempt1/generation1/TLS1, health3ms. Po aktualizaci dokumentace a SWA skriptu prošly publication+frontend deployment regrese32testy; AST/navigace/current-only projekce458veřejných/307JHU cest a whitespace kontrola prošly.
- Cílené source deployment/runtime regrese54passed; po úpravě předávání SWA tokenu14frontend deployment testů passed. Token se už předává pouze přes `SWA_CLI_DEPLOYMENT_TOKEN`, nikoli argv; debug se dočasně omezí a původní prostředí obnoví.

### Otevřené výkonové omezení

Management vector a hybrid, včetně zkoušeného document_type filtru, skončily po cca10–11s s `X-Search-Error-Code=search_timeout`, SQLSTATE HYT00. Logy potvrzují selhání v native exact SQL ještě před generováním; nejde o VPN nebo nedostupnost Ollamy. User exact vektorová část v těchto bězích1421/1471ms, retrieval2865/2531ms. Vector SQL, eligibility filtry i exact_statement jsou vůči v0.1.4 nezměněné; z toho samotného nelze určit příčinu špatného plánu ani zpětně tvrdit, že stejný Management test prošel na staré revizi.

Administrace má ověřený explicitní keyword režim; automatický fallback se nepřidal. ANN se nezapnulo, SQL timeout/tier ani modelové limity se nezvýšily. Jediný doporučený další slice: diagnostika a optimalizace Management exact dotazu se skutečnými SQL plány, zachováním všech prefiltrů a testem stejného korpusu.

### Receipt a rollback

Soukromý adresář `.local/deployments/jhu-sidecar-20261029-173112/` obsahuje původní a výsledný app snapshot šifrovaný Windows DPAPI, počáteční source manifest, plány, migration-results, image digesty, SQL baseline/after, cloud-smoke, cloud-rag/user/strategies, password-login a výsledný deployment-result. Veřejný předchozí statický obsah byl archivován jako12user/14admin souborů s manifesty. Tyto artefakty ani přihlašovací údaje nepatří do Git/JHU exportu.

Rollback nebyl proveden ani netestován jako outage drill. Před vrácením konfigurace nejprve zastav novou VPN relaci/revizi a ověř nula replik. Podle potřeb Single režimu obnov starý template z DPAPI v paměti s novým jedinečným revision suffixem, nebo použij podporovaný návrat k zachované revizi; nekopíruj credentials do YAML/argv a nepředpokládej bez ověření možnost aktivovat více Single revizí. Obnov původní single-container0,5CPU/1Gi/max3 template a předchozí statické artefakty. Z databáze nemaž nové tabulky, korpus ani indexy; signing/legacy klíče a hesla nerotuj. Nezastavuj celý Rancher ani jiné tenanty.

## Uzavřený původní handoff a přípravná historie

## Latest read-only preflight — 2026-10-29

User created both new secrets. Actual Get+validation passed for full VPN profile and64lower-hex gateway key without logging values. Fresh deployment plan still targets revision0000008 and fingerprint3f2e9ad7daed3376f96ad6c918922d31513f985941a2864c3e124121c6d094b3; only backend/helper immutable image blockers remain. The source CLI still defaults read-only, no Apply performed.

Read-only SQL connection to confirmed ju-ai-search-sql-prod.database.windows.net / ju-ai-search-sqldb-prod succeeded. SELECT TOP(0) checks returned missing-table42S02 for ALL FOUR: model_access_policies, tenant_model_registry, model_descriptions, model_runtime_settings. Therefore migration confirmation MUST NOT be supplied until the four existing guarded migration CLIs have actually run under separate explicit authorization. No DDL/data/capacity/image/frontend/source Git writes performed. Exact tenant remains ju-prod. Public receipts are ignored .local/jhu-deployment-plan-20261029.json and .local/jhu-deployment-prerequisites-20261029.json. This supersedes earlier absent-secrets / uninspected-SQL notes below. Next concrete operation: approved four additive model migrations, image build/push and existing ACA/SWA rollout with the already proposed0.75CPU/1.5Gi/max1 budget; no SQL tier/index/corpus change.

## Why this handoff exists

Uživatel požádal připravit současnou aplikaci pro Azure. Bylo oznámeno samostatné schválení konkrétních cloudových zápisů. Následující operace mění image, kapacitu, repliky a přidávají dvě secret hodnoty; samotný CLI přístup k Azure je nepovoluje. Lokální implementace a read-only plán byly provedeny bez Azure zápisů. Nepoužívat starý PostgreSQL Bicep ani single-container deploy_backend.ps1 pro tento rollout.

## Goal

Existující backend komunikuje s JHU modelovým API přes vlastní userspace VPN helper ve stejné ACA replice. Notebook ani jeho OpenVPN nejsou součástí síťové cesty. Žádný nový VM, VPN gateway, veřejný modelový ingress, tenantové přejmenování nebo automatická aktivace ANN.

## Verified targets (read-only 2026-10-26)

| Resource | Target / change |
|---|---|
| Subscription | `24e4a9a6-bab0-43f7-ba20-3b774704fade` |
| Azure directory | `c35f5da4-9a03-44e6-8bf9-92833634f6a7` |
| RG / region | `ju-ai-search-rg-prod` / Sweden Central |
| Container App | `ju-ai-search-ca-prod`; existing environment `ju-ai-search-cae2-prod` |
| Current ready revision | `ju-ai-search-ca-prod--0000008` |
| Current image | `juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod:prod-v014-20261015-145009` |
| Existing ACR | `juaisearchcrprod` |
| Exact runtime/data tenant | `ju-prod`; configuration alias `jhu` only |
| SQL | `ju-ai-search-sql-prod.database.windows.net` / `ju-ai-search-sqldb-prod` |
| KV | `ju-ai-search-kv-prod` |
| System-assigned principal | `ccacbf26-dcd6-4f7b-af7b-e3e769137de8`; existing vault-scoped Key Vault Secrets User |
| Existing SWA | `ju-ai-search-swa-user-prod`, `ju-ai-search-swa-admin-prod` |
| Fixed API target | `http://160.217.182.41:11434`; outbound VPN UDP according to verified profile |

Read-only public fingerprint: `3f2e9ad7daed3376f96ad6c918922d31513f985941a2864c3e124121c6d094b3`. Re-read immediately before Apply; do not assume it remains current. Private/public plan receipt is ignored `.local/sidecar-azure-plan.json`, not needed after a new clone: reproduce with [runbook](../../docs/development/jhu-sidecar-azure.md).

## Concrete writes proposed for approval

1. Add **only two** secrets in existing KV (four account secrets already enabled). No password changes or RBAC changes. External original Client.ovpn is read without modification, loaded into `ju-ai-search-vpn-client-config-prod`. Generate a new cryptographically random 32-byte key (64 lower hex) into `ju-ai-search-jhu-gateway-key-prod` with SDK/in-memory or portal, without logging/CLI value. Do not place either value in this handoff or Git.
2. Build/push root backend image and helper `scripts/vpn_spike/Dockerfile` to existing ACR from reviewed current cloud sources, record immutable digests. Published v0.1.7 tag predates these changes and cannot stand in for them. New source Git release is a separate approval.
3. Preserve backend **0.5CPU/1Gi** and add helper **0.25CPU/0.5Gi**, total **0.75CPU/1.5Gi**. Change maxReplicas3→1, min remains1, WEB_CONCURRENCY1. This increases per-replica reserved capacity; price/performance not measured. Alternative: retain total0.5/1 by explicitly assigning0.25/0.5 to each, which halves backend capacity and is not recommended without load validation. Do not silently choose it.
4. New single-mode ACA revision with digest-pinned two-container template and MI references. Gateway loopback18081, liveness18082, ingress8000 only. Existing other env, JWT signing key, credentials, secretRefs, identity and external ingress config preserved. No further resource creation or networking/RBAC changes.
5. Inspect SQL table presence read-only first. If missing, separately authorize guarded model access/registry/metadata/runtime settings migrations; schema has not been inspected in this source slice. Root image now includes all four CLI scripts. Never run a broad migration/reindex/bootstrap on prod by inference.
6. Separately release both existing SWAs using current frontend scripts and reviewed backendURL/theme/CORS. Preserve previous frontend artefacts for rollback. No SWA creation.

## Required secrets (names only)

| Name | State / consumer |
|---|---|
| `ju-ai-search-vpn-username-prod` | enabled, helper only |
| `ju-ai-search-vpn-password-prod` | enabled, helper only |
| `ju-ai-search-jhu-api-username-prod` | enabled, backend only |
| `ju-ai-search-jhu-api-password-prod` | enabled, backend only |
| `ju-ai-search-vpn-client-config-prod` | absent in preflight, create profile, helper only |
| `ju-ai-search-jhu-gateway-key-prod` | absent in preflight, create random capability, both |

The source external profile is supplied by the operator; no machine-specific path is needed by the deployed app. Shared MI technically has vault-wide read permission; logical consumer separation does not create per-container RBAC. Private runtime files use container ephemeral storage0600/0700, not a claim of memory-only storage.

## Models, configuration and session assumptions

- Existing GPT‑5.4-mini and Azure text-embedding-3-large deployments verified in `ju-ai-search-aif-prod`. Actual GPT‑5.4 absent. Current THINKING deployment misleadingly points to mini. Proposed default clears that advanced deployment so it is unavailable; creating GPT‑5.4 is not included. To enable it, provide a separately verified real deployment with `--advanced-model-deployment`.
- `qwen3.8:latest` was locally probed previously. Recheck actual JHU tags/digest and permissions from ACA after tunnel connection; the CLI flag is an operator confirmation, not a live probe. Dynamic registered models require their persistent SQL tables. No fallback if JHU fails.
- Runtime APP_VERSION explicitly passed. Existing private .env may be stale; it is neither deleted nor copied into image by this tooling.
- First cloud login: local helper and system VPN disconnected; no unapproved concurrent VPN login. Initial old revision has no sidecar. Subsequent sidecar rollouts may overlap sessions despite Single mode and require a coordinated shutdown or confirmed concurrency policy plus `--overlap-confirmed`.
- Existing native index/provider remains selected. Cloud embedding preparation UI is still local-only; cloud backfill requires its own target-guarded operation if requested. No new vectors are created by this connectivity rollout.

## Validation steps

1. Generate read-only plan using runbook, supply reviewed immutable images; require no blockers. Guard account/directory/exact SQL tenant, same old revision and fresh fingerprint. Re-read secret enabled metadata, existing MI/RBAC; do not create roles.
2. Confirm model schemas/session policy/resources. Apply once with explicit flags and expected fingerprint/revision. If timeout occurs, inspect actual state before any repeat. Only location/template PATCH body in memory. If-Match used when available; without returned ETag the pre-read fingerprint is not atomic CAS, so no concurrent deployment window.
3. Wait for actual new ready revision; `apply-requested` alone is not success. Backend health/auth must remain available even if VPN bootstrap fails. Check Management connection status without raw OpenVPN/SDK payload logs.
4. With notebook VPN off, run cloud discovery, one short synthetic cited JHU RAG question, an Azure-mini question and a selected existing prepared embedding index query. Confirm used profile/index provenance and no cross-index search/fallback. If Nomic cloud index absent, report separately and do not auto-backfill.
5. Validate both consoles, persisted conversation/model provenance, permissions, descriptions/output settings and three prompt editors after approved frontend release. Basic5DTU unchanged; no performance target claimed.

## Rollback

Save previous revision/template and frontend artefact references securely; never dump full existing env. Deactivate/stop new VPN revision and verify session ended, then reactivate `ju-ai-search-ca-prod--0000008` and restore old frontend artefacts. Keep old revision available until acceptance. No destructive SQL rollback, corpus/index deletion, password rotation or secret deletion. A backend image-only command must not overwrite a two-container deployment. Stop after failed activation and diagnose fixed status codes; no direct HTTP/cloud fallback.

## Uzavřená schválení původního plánu

- [x] Approve two secret creations, image build/push, existing app/SWA rollout and the **0.75CPU/1.5Gi, max1** proposal (or select explicit alternative).
- [x] Confirm VPN session policy; local helper will be disconnected before first cloud login.
- [x] Inspect SQL read-only in the activation step, then approve only concretely missing model migrations before DDL.
- [x] Review final source test receipt and fresh plan before applying.

## Source verification receipt

Full isolated suite + wheel553 passed /116 expected skips; clean JHU targeted runtime/deployment/transport/gateway/status/wheel88 passed. Helper image built and actual offline Linux cloud bootstrap passed UID65532/caps0/liveness/no private files/no retry; test container removed. Current public457/projected307 paths passed AST/navigation/projection. Frontends unchanged. Azure MI, UDP egress and cloud RAG remain unverified; no Azure writes performed.
