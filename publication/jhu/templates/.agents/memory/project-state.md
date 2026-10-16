# Current Project State

This is the standalone JHU AI Search repository, source version @@VERSION@@. It starts with a single snapshot commit; no original development Git history or operational diary is imported. Future updates are normal reviewed commits in this repository. Do not merge/mirror unrelated history or force-push.

Only tenants/jhu is bundled, including search/classification configuration and the JHU frontend theme/logo. Local identity is jhu; cloud corpus identity is ju-prod. Configuration aliases never change database/token/ACL identities. Private env, documents, dependencies and caches are excluded.

Current design: FastAPI, synchronous SQLAlchemy, two Next.js static frontends, Azure SQL native exact + fulltext and optional DiskANN v3+, Azure OpenAI factories, Blob Storage and optional Key Vault. Tokens are custom signed bearer tokens and passwords Argon2id. Local SQL 2022 uses the JSON/LIKE reference.

Run and record unit, package and frontend verification for every prepared snapshot. These checks are not a cloud deployment or performance acceptance.

Known deferred work: experimental PostgreSQL retrieval, OCR, main-pipeline section_title persistence, Blob/local configuration unification, local model adapters and automated model comparison. Default search remains exact; do not activate ANN or change capacity without target evidence and authorization.

Read README.md, docs/architecture/search.md, docs/deployment.md and docs/updates.md. Preserve tenant secrets, user data, accounts and Docker volumes. Cloud changes require explicit scope and guarded target checks; publishing source alone does not authorize them.

Next recommended technical slice: representative JHU retrieval benchmark by filter selectivity before deciding on ANN activation.
