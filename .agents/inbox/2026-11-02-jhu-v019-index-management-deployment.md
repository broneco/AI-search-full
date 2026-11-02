# Azure Deployment Handoff: JHU v0.1.9 index management and VPN recovery

- Status: authorized — user approved GitHub, Forgejo, backend and both frontends; final progress UI verification in progress
- Created: 2026-11-02
- Related task: create/populate JHU embedding indexes from admin; explain current outage
- Related ADR: docs/adr/ADR-0043-administrative-index-jobs.md
- Source: working v0.1.9 on microsoft-sql, not committed/tagged/published

## Purpose and authority

User explicitly approved deployment to Git, Forgejo and backend/frontend on 2026-11-02 after requesting a file-level progress popup. This includes the previously reviewed additive jobs migration and feature flag. Prepare and test final sources before writes. No cloud write has been executed yet. Previous v0.1.8 GitHub/Forgejo authorization was completed and did not deploy Azure. This handoff covers the proposed new Azure operation only; Git/Forgejo publication remains separate. User reports notebook VPN OFF and has started Rancher only for local tests/builds. No local managed JHU helper may be started for cloud QA.

## Exact existing targets

| Target | Verified value |
|---|---|
| Subscription | 24e4a9a6-bab0-43f7-ba20-3b774704fade |
| Directory | c35f5da4-9a03-44e6-8bf9-92833634f6a7 |
| Resource group / region | ju-ai-search-rg-prod / swedencentral |
| Container App | ju-ai-search-ca-prod |
| Previous active revision | ju-ai-search-ca-prod--preserve-1030-151331 |
| Backend image | juaisearchcrprod.azurecr.io/ju-ai-search-ca-prod@sha256:5d5b6f6b45af7f1df5d863fcd08402028a669367f4c034d72dc78bdf12c6000f |
| Helper image | juaisearchcrprod.azurecr.io/jhu-vpn@sha256:006c3070ecc2295cfd34d0c80e34c30d006d2bfe57d3e6aa7c58daa723275de3 |
| Exact corpus tenant | ju-prod |
| SQL | ju-ai-search-sql-prod.database.windows.net / ju-ai-search-sqldb-prod |
| ACR / Key Vault | juaisearchcrprod / ju-ai-search-kv-prod |
| Backend HTTPS | https://ju-ai-search-ca-prod.mangosky-3e5a7049.swedencentral.azurecontainerapps.io |
| Admin / user SWA hosts | kind-tree-0c95d5203.2.azurestaticapps.net / nice-forest-03f01f203.6.azurestaticapps.net |

Existing capacities stay backend0.5CPU/1Gi +helper0.25CPU/0.5Gi, min1/max1/oneworker. No new resources, scaling, RBAC, identity, gateway key, password, API secret, SQL target or ingestion-default change. Keep the already approved SQL S2 unless separately instructed; do not increase it.

## Concrete proposed operation

1. Confirm final whole-suite, SQLite/localSQL, wheel, both production frontends and clean JHU candidate; save safe source hashes and actual local image IDs. Local preparation tags: ai-search-backend:v0.1.9-prepared and ai-search-jhu-helper:v0.1.9-prepared. Hashes/receipts live under .local/incidents/2026-11-02-jhu and named .local/*20261102 logs. These are evidence, not hidden required implementation.
2. Re-read exact Azure account/current revision/fingerprint. Capture the current ARM rollback privately with Windows DPAPI, prior served frontend assets and a full SQL/vector/settings/Blob checkpoint before mutation. Freeze user writes for the short deployment/acceptance window; explain and bound the outage. Check no unrelated deployment or competing notebook VPN helper is running.
3. Only after approval, upload the two reviewed local images into the existing ACR and resolve actual registry manifest digests. Never substitute a tag for the immutable manifest guard or guess a digest. No new ACR/task/resource.
4. Run only the additive index_preparation_jobs migration with exact host/DB/tenant guards. The old image lacks this class; use the generated standalone payload from public migrate_index_jobs.py --console-script with the three reviewed target arguments. The generated .local/incidents/2026-11-02-jhu/migrate-index-jobs-console.py is reviewable SQL, contains no credentials and was NOT executed during source work. This creates only the missing jobs table and preserves every old row/table/index.
5. Take a new strict image-preservation baseline after the separately accepted schema addition. The verifier reflects optional job metadata identically even in the old ORM. Do not run another index job during this checkpoint.
6. Build a public read-only deploy_jhu_sidecar.py plan for the same targets, proposed suffix v019-index-1102-<unique>, reviewed image digests, app-version v0.1.9 and --enable-index-preparation. Preserve all current secrets/references, managed identity, storage, ingress, SQL settings and model approvals. The new flag authorizes subsequent explicit authenticated Manager native-index jobs; it performs no backfill itself.
7. Review blockers/fingerprint/previous revision/resource diff before Apply. Migrations/models/session/overlap confirmations remain required. The previous helper is terminal with no active tunnel according to current source/state; recheck before rollover and stop the old session before a new one can authenticate. Single revision mode alone is not proof of no overlap.
8. Apply only the guarded backend/helper template to the existing app. Publish the two verified JHU production frontend artifacts to existing SWAs separately through deploy_frontend.ps1, with the exact HTTPS backend. Never run deploy_all.ps1 or replace the two-container app with the single-container deployment helper.

## Required acceptance

- API health, runtime v0.1.9, login/current groups, existing history/PDF/CORS and both actual served frontend artifacts.
- Notebook VPN/helper OFF; cloud sidecar ready, fresh status, exact replica/tenant context. Controlled degraded/explicit-reconnect check must never replay a generation or create parallel sessions. Independent API health during JHU outage.
- Manager inventory -> existing Nomic profile/index identity retained; create/current-job HTTP202, Chunking progress and complete-index selection. No new expensive full corpus backfill or default activation merely for deployment QA.
- Separately test actual native create/backfill/resume with a very small clearly owned synthetic QA scope, preserving foreign tenants/ACL/default; clean only the exact own UUIDs/tables. Do not claim SQLite or SQL2022 validates native VECTOR. An unrun native/UI gate remains OPEN.
- Recheck original4accounts/431docs/9372chunks and both original native index vectors/settings/keys/Blob hashes against the before state after exact own-QA cleanup. Counts alone are insufficient. Preserve existing Azure default b1e81c70-686c-481a-bbff-e15f034288ef and Nomic c536b88c-8df6-4280-8063-ff8d2bb273a9.
- R_583/Nomic relevance remains an independent known limitation, not fixed by this infrastructure release. Report it honestly.

## Rollback

Stop the new helper/session before restoring the prior reviewed backend+helper images/template and previous frontend assets. Restore the exact original secret references, version and feature flag/ingress; do not change account passwords or signing keys. Leave the additive jobs table and any valid already-approved alternative vectors in place. Never drop/reset the live DB, existing indexes, chunks, accounts, history or settings in rollback. A partial job remains resumable or explicitly interrupted; never replay it automatically.

## Completion record

Approval, actual digests, new revision, timing, checks and remaining limitations must be recorded after execution. Until then current cloud is still v0.1.7 with a degraded JHU helper. A working source/build is not a completed deployment.

## Reviewed preparation results

Source752/23expectedskips; clean JHU559/151; actual SQL-focused65; frontend9; both final JHU production builds/TS; Docker offline source/import checks and two real Linux gateway cycles with synthetic bootstrap/fake VPN and no network passed. No live native Azure/UI acceptance is claimed.

Local reviewed backend image ID: `sha256:a5e542dfa2a303171180516b348ced611b5e462d4933ceb26ae55c8fb205e827`; helper image ID: `sha256:9ed7ab1f20ceaa4bd746e6fd64079f4bc3eda8752dbe44742e57922786c6e689`. Confirm actual ACR digests after the separately approved upload. Prepared migration payload is target-guarded and unexecuted. Both compiled JHU artifacts point to the cloud backend and have zero localhost:8000 literals.

Final cloud read-only check2026-11-02 17:34CET: same revision/runtimev0.1.7, degraded VPN attempts3, SQLS2/50DTU/Online, CREATE TABLE and ALTERdbo permissions1. Authorization to perform the proposed writes is still required.

Final popup release: main755/23; clean JHU561/152; JS9; native dialog/file API/phase metadata included. Current backend image sha256:379d17d8a3b90925c3b6b36d569600d7143cb256adccc31d467aa08c1eaba961 supersedes earlier local backend image. New user authorization covers publication and rollout. Existing ACR upload is part of this execution; no capacity increase. Private rollback/source/asset receipts via .local/current-v019-release.txt.
