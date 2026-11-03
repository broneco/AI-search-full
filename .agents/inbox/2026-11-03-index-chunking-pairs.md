# Azure Deployment Handoff: indexy s vlastním chunkováním

- Status: AUTHORIZED 2026-11-03 — user explicitly approved deployment of working changes; preparing v0.1.11, GitHub/Forgejo/backend/both frontends and required additive guarded migration. Earlier no-authorization notes below are historical.
- Created: 2026-11-03
- Related task: pojmenované/mazatelné indexy jako dvojice chunkování + embedding a oprava Blob náhledu
- Related ADR: docs/adr/ADR-0044-index-chunking-pairs.md
- Source: uncommitted working tree after main 3330ebdc8c77368ffa6c557f53ab7d17b04c30d7; version remains0.1.10

## Updated source scope: 2026-11-03 index editor

Latest user asks Edit existing/Create new and explicitly authorizes once-only current-setting assumptions for unknown legacy snapshots. ADR0045 adds nullable settings_origin/current_index_id/owner_index_id/base_revision to index_settings, also via idempotent ALTER when this table already exists. Current console-script generator includes these additions; do not reuse an earlier payload. Source editor uses stable logical UUID and hidden same-profile physical generations, atomic successful publish; failed/cancelled edit preserves working head. Default ingestion pointer and baseline remain, default/vector/hybrid/keyword query follows completed head. Preserve version-pointer semantics as well as corpus filters in compatible rollback. Explicit UI initialize-settings writes only unknown metadata snapshots, not chunks/vectors/globalconfiguration; it is separate from DDL. Existing form no longer saves global parameters or rebuilds whole DB.

Final local evidence107passed/2skips inclSQL/wheel/publication, subsequent model-access/catalog/editor46passed/2skips, adminbuild/TS, JS10 and both GUI modes using mockedloopbackAPI. No new cloud or Git publication authorization; remaining deployment gates below still apply. Current adminout remains LOOPBACK and must not be uploaded.

## Purpose and integration boundary

Source implementation and local SQLite/SQL/GUI verification are authorized. Earlier v0.1.10 publication/cloud authorization is completed; do not treat it as permission for this new schema migration. User must approve the concrete deployment separately after artifact digests and the preservation check are ready. Do not publish to GitHub/Forgejo or Azure automatically.

## Exact existing resources

Subscription24e4a9a6-bab0-43f7-ba20-3b774704fade; directoryc35f5da4-9a03-44e6-8bf9-92833634f6a7; RGju-ai-search-rg-prod; regionSwedenCentral. Backendju-ai-search-ca-prod. SQLju-ai-search-sql-prod.database.windows.net / ju-ai-search-sqldb-prod / exacttenantju-prod. Config aliasjhu is never the data identity. Vaultju-ai-search-kv-prod. Both existing static sites: adminhttps://kind-tree-0c95d5203.2.azurestaticapps.net/ and userhttps://nice-forest-03f01f203.6.azurestaticapps.net/.

Last verified prior deployment revisionju-ai-search-ca-prod--v010-1102-194124, backendsha256:37b8a58b872e82594d6f5b333efaf41715165e99c5ce0d156aea35568f968f89, helpersha256:9ed7ab1f20ceaa4bd746e6fd64079f4bc3eda8752dbe44742e57922786c6e689. Re-read active identities before any action rather than assuming this is still current. Preserve SQLS2/50DTU and existing ACA .5CPU/1Gi + .25CPU/.5Gi/min1max1, MI, ingress, keys, VPN session and all existing routes. No new resources, no capacity/RBAC/Key Vault writes. Do not start a notebook JHU helper.

## Ordered operations after separate authorization

1. Read exact target/runtime and all current index identities, counts, coverage and active default. Include the user's partial MXBAI index, not only the historical Azure and Nomic pair. Capture accounts/history/config/ACL/original Blob bytes and every vector table before schema work. Preserve completed batches and latest job metadata.
2. Finish/build the candidate backend and both SWAs from the reviewed source, record immutable digests/artifacts. Current ignored admin build is explicitly LOOPBACK-ONLY for GUI testing; **never deploy frontend-admin/out from this task**, because NEXT_PUBLIC_BACKEND_URL is127.0.0.1:8766. Rebuild against the exact cloud backend and verify compiled assets contain no loopback. No version/tag was requested here.
3. Prepare an explicit original-column SQL fingerprint comparison for the schema transition. The old preservation manifest hashes `SELECT *`; new nullable corpus_id changes JSON hashes even when original values are identical, and new metadata tables are expected. Do not claim the ordinary old/new whole-row manifests are equal or broadly ignore diffs. Compare every pre-existing column/key/revision/vector/Blob and separately validate that the new tables are empty and every original corpus_id is NULL before backfill. This original-column transition checker is an OPEN deployment gate, not a completed cloud proof.
4. Review `migrate_index_corpora.py --console-script` for the exact target above. Execute only the two new metadata tables and nullable chunks.corpus_id addition in one guarded transaction. Payload runs in the old image, using its existing SQL identity; no original rows are updated. Azure startup does not perform this migration.
5. Verify old-data preservation before rollout and confirm no custom corpus rows exist. Deploy the candidate backend with the existing helper and unchanged capacity. Deploy freshly rebuilt admin/user artifacts with the cloud backend URL. Verify exactversion/artifact, CORS/auth, original catalogs and default, readyhelper, authorized originalPDF/preview, basicquery and health whilepreviewruns.
6. Perform an explicitly bounded native test with disposable own fixtures/identities, distinct chunk settings and the same embedding profile, CAS rename, protected default deletion, corpus-restricted vector/keyword/hybrid/expansion and history citations after index deletion. Preserve all pre-existing rows. Do not run a new full431-document/9372chunk model backfill merely as deployment smoke. Any cleanup must identify only the operator's own records and account for retained historical chunk text.
7. Verify the actual user workflow and issue a final report with measured native/GUI results and explicit remaining gates. No silent changes to chunking/search/model defaults.

## Rollback

Before the first custom chunk, rollback may use the original backend digest and both previous SWAs; leave the additive schema in place. After any custom text row exists, **v0.1.10 is NOT a safe rollback image**: its keyword/context queries do not filter corpus_id and can mix chunks. Disable INDEX_PREPARATION_ENABLED and stop the job, then use a compatible corrected image retaining corpus filtering. Never drop the new schema or delete user corpora/history as an automatic rollback. Prepare this compatible rollback artifact before enabling the first real corpus.

## Local evidence and limitations

Full then-current source suite773passed/24skipped inclreal localSQL; final index/jobs/admin/preservation suite117passed/2skipped incl22feature/PDF cases onSQLite+localSQL; cleanJHU75passed/72expectedskips inclwheel and finalfeature14passed/8expectedSQLskips; packaging/export subset39passed inclactualwheel; JS10passed. Both frontend builds passed; finaladminbuild/TS and GUI used disposable loopbackAPI. GUIcreate800/rename/configimmutabilityafterdraft1200/delete/preview passed. PDFpreview uses an actual public fixture PDF, mockedBlobdownload, real extraction/splitting/ACL and no writes. Test helper/storage/model endpoints are synthetic. These are NOT actual AzureVECTOR/ANN/Blob/JHU/native acceptance. No live SQL/schema/resource/source publication or release was performed for this task.

## Required non-secret values

No new infrastructure identifiers or secrets are needed. Before approval, operator must fill candidate backend digest, compatible rollback digest, exact backendFQDN for frontend rebuilds, artifact hashes and preservation-transition checker receipts. Existing secret references stay unchanged; never paste their values.

## Exactly one next slice

Prepare and separately authorize the guarded schema/image/SWA rollout plus native preservation/GUI acceptance, resolving the explicit original-column preservation and compatible rollback gates first.

## 2026-11-03 additional source changes: summaries and capacity

User confirmed: omit AI summaries from neighbors during expansion, keep matched chunk summary. New persisted search flag defaults true; no reembedding/data rewrite. Management-only authorized indexed context sample counts with local reference tiktoken/o200k_base and exposes lengths only. Admin displays resultCount × sampleTokens and effective model/app budgets under token limits; unknown native token metadata remains explicitly unknown/character-derived. No provider call. Public tokenizer cache is warmed in Docker image, proven offline; do not remove this build step or rely on runtime Internet. See docs/development/context-capacity.md and tests_explained/test_context_capacity.md.

Local feature/config/access/catalog104pass1skip inclSQL; JS11pass; cleanJHUfeature/config12pass7expectedSQLskip; finaladminWebpack/TS and localDockerbuild passed. GUIfixture toggle/save/reload/dynamic count/warning passed, screenshot .local/context-capacity-config.png; owned server/tab closed. Actual installed wheel/publication21passed; receipt .local/context-capacity-packaging.txt. These additions need no extra schema or capacity; earlier migration/preservation/compatible-rollback gates above remain open. No commit/version/publication/cloud change performed.

## Current authorization and prepared gates — 2026-11-03 v0.1.11

Latest user: “Super, funguje to - můžeme deployovat.” This authorizes the previously discussed full release across GitHub, Forgejo and backend/frontends, including required additive schema. No repeated approval is needed. Version v0.1.11. Existing subscription/resources/tenant/helper/capacity unchanged. Original-column projection checker is implemented in public verify_deployment.py and passed47SQLite/localSQLtests. Separate new-schema gate requires all legacycorpusNULL and empty newtables. Cloud captures use the same recorded original projection before/migrated/after so no SELECTstar exception hides original changes. Existing configs are hashed and never reset. Tokenizer cache built into image.

Private operator receipts .local/current-v011-release.txt point to this run. before-app ARM stored only DPAPI-encrypted, both servedSWA artifacts backed up. Candidate backend and separate compatible-fallback image will be recorded in images.json; fallback keeps all new corpus/logicalhead readers and disables INDEX_PREPARATION_ENABLED in reviewed runtime template, encrypted separately. Do not use oldv010 after a customcorpus exists. Rollout freezes external ingress, verifies hashes+Blobs, applies only addivitive migration, verifies again, stops old helper before starting new revision, checks original hashes+Blobs again, then restores externalingress. NotebookVPN may be needed forForgejo and must be confirmedOFF before newcloudhelper. No full431docbackfill or newresource.
