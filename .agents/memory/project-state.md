# Project State

Last updated: 2026-10-16

## Current work

Current authorization: release all approved cleanup/hardening to the normal GitHub repository and bump source/UI version to v0.1.5. Document a durable process for future JHU handoffs. This request does not include updating Forgejo or deploying Azure. Keep the three operations separate.

Latest handoff requirement: JHU only, without original Git history AND without historical changelogs, memory archives, handoffs or deployment diaries. User approved publication to https://forgejo.jcu.cz/dconsulting/jhu-ai-search.git. Completed: main at e4b116efc51ff41bae65a338155b94caee7b1a2c, exactly one root commit, 220 files; remote main/default HEAD verified. No original branches/tags/Git objects were imported. Parent development Git/remotes and tenant configurations remain separate.

Persistent publication checkout: `.local/publications/jhu-ai-search`. Canonical instructions are now VERSIONED in `.agents/workflows/jhu-publication.md` and `docs/development/jhu-publication.md`. Root export_jhu.py reads a committed ref and creates a clean JHU ZIP with a separate internal manifest; prepare_jhu_publication.py defaults to a read-only plan and requires explicit Apply/expected HEAD to change only the independent checkout. Helpers/templates are under scripts/publication/ and publication/jhu/templates/. Old ignored operators are deprecated and not required after a fresh clone. Future publication is user-requested, with a normal summary commit; never mirror/merge original history or force-push. Existing publication hashes/SHA remain under .local/publications/. Git Credential Manager handles authentication without putting credentials into source/logs.

All eight approved audit findings plus cleanup are included in v0.1.5. The current instruction authorizes commit/tag/push of the main GitHub release. No automatic subsequent Forgejo publication, Azure deployment, migration or ANN activation is authorized by that source release.

- Tenant-scoped fast reindex, safe full refresh with plan/apply guards and per-document replacement.
- One configured tenant is sufficient for private-env parity checks; isolated tests use synthetic fixtures and do not require private configuration.
- Complete Python packaging and canonical dependency declarations, authenticated HTTP ask CLI, fail-closed frontend plan/apply deployment.
- Shared configuration alias resolver: ju-prod retains its exact database identity and loads jhu JSON/configuration.
- Current operating contract/memory replaces old PostgreSQL/Entra/LangChain assumptions; historical notes archived.

## Verification

- v0.1.5: **280 passed / 84 expected skips** in the complete offline suite including wheel and **18** publication regressions; both production frontend builds passed. On 2026-10-16 Docker Engine/localhost SQL was unavailable; the attempted opt-in SQL run failed at connection setup, so no fresh local SQL acceptance is claimed. Azure/model integration stays opt-in and unrun for this source release. Details: docs/CHANGELOG.md and docs/releases/v0.1.5.md.
- Published current-state handoff: **220 files**, runtime/assets/tests byte-identical to the verified JHU input; historical documentation replaced with concise current guides. Final package/tenant/prompts/health checks: **13 passed**. Final ZIP matches the published checkout; local links and file set checked, clean worktree, one parentless commit, no tags/alternates. Source publication does not deploy Azure.
- JHU-only handoff: **282 files**, only tenants/jhu with materialized search/classification JSON, only JHU themes/logos. Full extracted-bundle offline suite including wheel: **261 passed / 85 skipped**. Both exported frontend TypeScript checks exit 0; updated parent configuration/prompt tests: **10 passed**. Evidence: tests-jhu-export.log and source-jhu-hashes.json in the ignored handoff directory. Private env/data/build dependencies are excluded.
- Clean export without private env: fresh `pip install -r requirements.txt` plus setuptools/wheel succeeded; full suite with RUN_PACKAGE_TESTS=1: **261 passed / 85 skipped**. One extra skip is the optional real-env check; the synthetic single-tenant check passed.
- Full workspace suite with local Docker SQL integration: **331 passed / 14 skipped**, followed by **16 passed** maintenance/rechunk regressions after the final exact-source protection. Final relationship rejection regression: **12 passed** in the maintenance module.
- Wheel build/import outside checkout, public JSON/PDF resources and private-env exclusion passed. Fake PowerShell deployment tests exercise both available Windows shells; they do not deploy.
- Navigation covers all **304 public files**; local Markdown links and diff whitespace checks pass. Clean ZIP and non-secret evidence are in ignored `.local/hardening-20261015/`.

These are local/clean-source results, not Azure deployment, live model or performance acceptance. No commit/push/release, cloud credentials, data, capacity or RBAC changed.

## Deployed baseline

Source baseline: v0.1.5 on microsoft-sql; use the release tag and remote verification to resolve the actual published SHA. Release evidence belongs under .local/release-v015/. The cloud baseline below is separate and is not changed by publishing source.

JHU last verified ready revision: ju-ai-search-ca-prod--0000008, image prod-v014-20261015-145009. Native coverage 9,372/9,372 over 431 documents. Native fulltext works; DiskANN v3 exists but runtime remains exact. Two earlier exact+fulltext HTTP smokes were 3,927/2,117 ms, not p95. A 60-query ANN subset had recall@30 99.11%, but broader filtered cases timed out. No representative ANN/performance acceptance or adaptive routing is complete.

Definitive cloud history: `docs/deployments/2026-10-15-jhu-search-rollout.md`. SQL was Standard 10 DTU, backend 0.5 CPU/1 GiB; no new capacity changes. Do not rerun completed corpus/schema migrations merely because context was reset.

## Constraints and private files

- Preserve data/, data - full backup/, env files, Docker volumes and user accounts.
- Private operators are under .local/operations/; checkpoint/DPAPI snapshots under .local/deployments/ and benchmark evidence under .local/benchmarks/. They do not ship in Git, wheels or images.
- Old Git history contained database passwords; rotate any still-used credentials separately. Do not rewrite history or reset passwords during routine code work.
- PostgreSQL retrieval operators, main-pipeline section_title persistence, Blob/local configuration unification, OCR, local model adapters and automatic model comparison remain deferred.
- Full refresh can retain successful individual replacements after a later failure, but must not prune remaining stale data on failure. It is not a single corpus-wide transaction.

## Next recommended slice

Representative JHU runtime benchmark by filter selectivity and optimization of the measured remaining cost before deciding on ANN activation. Recall/p95/cold-start gates remain those in `docs/architecture/azure-sql-search-roadmap.md`.

Historical phase/deployment notes are in `.agents/memory/archive/`; they must not override this current state.

