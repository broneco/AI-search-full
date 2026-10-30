# Project Agent Operating Contract

## Role and source of truth

Maintain this AI Search application in tested, reversible increments. Read this contract, `.agents/memory/project-state.md`, the iteration policy, deployment policy and relevant rules before edits.

Precedence: latest explicit user request, security/privacy, this contract, rules, workflows, current memory, implementation, historical notes. Explicitly approved batches may contain multiple related fixes; do not stop after the first item of an approved batch.

## Implemented architecture

- Python 3.12 reference environment, FastAPI, Pydantic and synchronous SQLAlchemy repositories.
- Two Next.js/React/TypeScript applications: `frontend-user/` and `frontend-admin/`.
- Azure SQL native VECTOR exact retrieval; shared tenant, metadata and relational document/chunk ACL predicates before top K.
- Native Azure SQL fulltext keyword retrieval; local SQL Server 2022 uses the documented JSON cosine/LIKE reference.
- Immutable embedding profiles, per-profile index tables and one explicitly active index per tenant.
- DiskANN v3+ is optional and explicitly configured. Default and deployed JHU mode remains exact; representative ANN/performance acceptance is open.
- Tenant catalogs select Azure OpenAI or JHU Ollama generate through bound providers. SQL model-access policies use current server groups; embedding providers are separate.
- JHU embedding_config includes digest-pinned Nomic 768 through /api/embed. The active index chooses query/ingest provider; explicit backfill adds vectors over shared chunks without overwriting previous spaces. Read docs/development/local-embeddings.md before activation or rollback.
- Admin Management can prepare local indexes; both consoles select exactly one allowed complete index UUID without changing ingestion. Ordinary users require registry publication and group permission. Explicit choices never fan out/fall back; cloud preparation remains guarded operator work.
- SQL tenant_model_registry stores explicit local-model approvals and revisioned user visibility. File catalogs retain defaults. Providers pin digests before/after requests, Nomic/MXBAI use versioned input recipes, and changed embedding preprocessing creates another space. See docs/development/local-model-registry.md; do not auto-download or benchmark the entire inventory.
- Admin comparison uses two independent chat threads/models/indexes on one shared question. If both use JHU LLM/embedding, schedule A → B for the shared slot, never retry/fall back. model_descriptions stores revisioned exact-tenant CS/EN metadata separately from immutable profiles; cloud needs guarded migrate_model_metadata.py. Discovery is modal, model pickers searchable, and three prompts share one section. Read docs/development/admin-comparison.md.
- Management edits output ceilings in the model overview, stored separately in exact-tenant model_runtime_settings with independent CAS revision/null reset. New chat/summary/classification operations apply them through the effective catalog. Local context bounds preserve input; providers enforce caps without truncating text or changing identity/indexes. Local startup creates the table; cloud needs guarded migrate_model_limits.py. Read the same admin guide before changes.
- Blob Storage, Azure Container Apps, Static Web Apps and optional Key Vault resolution are implemented.
- Authentication uses a custom signed two-part bearer token, Argon2id passwords and current server-side groups. `JWT_*` setting names are historical; this is not a standard JWT or an Entra ID implementation.
- RAG orchestration is application code. LangChain/LangGraph and Entra ID are future options, not current dependencies.
- PostgreSQL scaffolding remains experimental with explicitly deferred retrieval issues; it is not the supported local development path.

Do not reintroduce Azure AI Search, other databases, orchestration frameworks or auth providers without an approved architectural change. Known deferred work: PostgreSQL operators, section_title persistence in the main ingestion pipeline, Blob/local configuration unification and OCR.

## Environments and tenant identity

`APP_ENV=local` runs the persistent Docker SQL Server through `dev.ps1`; `test` uses isolated fixtures unless integration checks are explicitly enabled. Cloud uses `dev` or `prod`. DATABASE_BACKEND is independent of APP_ENV.

Database/token tenant IDs are exact identities, including suffixes. `ju-prod` must never become `ju` or `jhu` in data or ACL checks. `tenant_config_name` alone maps the configuration alias `ju` to the directory `jhu`.

Public JSON/assets under tenants/ and fixtures/ ship with the Python wheel; private `.env*` files never do. Use the tenant configuration resolver and file-level default fallback. Local/test runtime JSON writes belong in ignored overlays.

## Delivery and verification

- Keep interfaces between API, ingestion, retrieval, storage and providers explicit. Reuse shared authorization and repository writes.
- Add meaningful regressions for changed behavior, including cross-tenant and failure cases when applicable.
- Run appropriate checks and distinguish SQLite/local SQL from actual Azure native/runtime evidence. Never claim an unrun benchmark passed.
- Check installation from clean sources when changing packaging. Runtime/dev dependency declarations live in pyproject.toml; requirements.txt delegates to it.
- Isolated tests must run without private env files. Real-env structural checks accept at least one configured tenant; placeholder tenants are excluded, and all configured files must agree on keys.
- Never commit secrets, private documents, dependency caches or operational snapshots. Never dump credentials into logs or tool output.
- No automatic commit, push, release or deployment unless explicitly requested for the current work.

## Documentation and memory

- Record changes under Unreleased in `docs/CHANGELOG.md`; create a release block only when releasing.
- Preserve full public documentation and detailed test explanations. This handoff omits ADR files; describe current architecture in `docs/architecture/` and `docs/design/` and do not assume an imported ADR template exists.
- Add/update the corresponding explanations in `docs/tests_explained/` for changed test modules.
- Keep `docs/navigation_guide.md` synchronized with source files using relative paths and concise Czech descriptions.
- Keep project-state and implementation notes concise and current. Historical details belong in `.agents/memory/archive/` or deployment reports; archive contents are not current instructions.
- Use repository-relative links in documents. Do not depend on another machine's absolute paths, hidden agent brain folders or private scratch scripts for standard workflows.
- Report outcome, relevant verification, remaining risks and exactly one recommended next slice. Do not imply cloud deployment when only sources changed.

## Azure actions

Azure CLI/tool access may be available. Availability alone is not authorization to change resources. For required cloud changes, prepare a concrete handoff in `.agents/inbox/` with target guards, operations, non-secret values and rollback before requesting approval. Follow existing explicit user authorization within its scope; do not repeatedly ask for the same approval.

Use managed identity/Key Vault when configured; do not invent secrets or change RBAC/capacity. Keep resource provisioning, schema migration, embedding backfill, index activation and image/frontend release separate. Current deployment scripts default to read-only plans. Only their guarded Apply paths write resources; frontend release never creates a SWA.

Maintenance must preserve exact tenant scope and validate sources before writes. A full refresh replaces documents individually and prunes initial stale rows only after all inputs succeed; it does not delete the corpus before extraction/model calls.
