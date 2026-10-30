# Project Agent Operating Contract

## Role and source of truth

Maintain this AI Search application in tested, reversible increments. Read this contract, `.agents/memory/project-state.md`, the iteration policy, deployment policy and relevant rules before edits.

Precedence: latest explicit user request, security/privacy, this contract, rules, workflows, current memory, implementation, historical notes. Explicitly approved batches may contain multiple related fixes; do not stop after the first item of an approved batch.

## Implemented architecture


- Cloud mutable prompts/search/chunking/summary/classification use exact-tenant SQL tenant_settings; bundled JSON is only a missing-row default, SQL failure never falls back. local/test overlays remain. Before first new release capture/reconcile current ephemeral files and legacy Blob configuration, then guarded insert-only migrate_tenant_settings.py; startup excludes cloud DDL. Read docs/development/non-destructive-updates.md. Source support is not cloud migration acceptance.

- Python 3.12 reference environment, FastAPI, Pydantic and synchronous SQLAlchemy repositories.
- Two Next.js/React/TypeScript applications: `frontend-user/` and `frontend-admin/`.
- Azure SQL native VECTOR exact retrieval; shared tenant, metadata and relational document/chunk ACL predicates before top K.
- Native Azure SQL fulltext keyword retrieval; local SQL Server 2022 uses the documented JSON cosine/LIKE reference.
- Immutable embedding profiles, per-profile index tables and one explicitly active index per tenant.
- Management can prepare/resume local embedding indexes in admin. Both consoles bind a question to one existing allowed, complete index UUID; normal users only see the tenant default or published/group-authorized experiments. This never changes ingestion, fans out or falls back. Cloud preparation remains operator-only.
- A revisioned tenant_model_registry persists explicit local-model approvals and user publication; JSON defaults remain. Discovery is read-only, registration rechecks metadata, and pinned providers verify digest before/after calls. Nomic and MXBAI have distinct versioned input recipes; changes create new spaces and preserve existing vectors.
- Admin comparison sends one shared question through two independent standard chat threads, each with one model/index and its own filters. When both variants use JHU inference/embedding, schedule A then B to respect the shared slot; other pairs may run concurrently. Editable CS/EN descriptions use exact-tenant SQL model_descriptions with separate CAS revision, never mutate profile identity. Admin model pickers are searchable, discovery is modal and all three prompt editors share one section. Read docs/development/admin-comparison.md; cloud description DDL uses only guarded migrate_model_metadata.py.
- Management edits per-model output ceilings in the same overview. Exact-tenant model_runtime_settings uses independent CAS revisions and nullable reset, layered over the immutable JSON/registry profile. Limits apply to new chat/summary/classification operations; local context bounds reserve input and never truncate. Azure and JHU adapters enforce the ceiling even on internal per-call max_tokens. Cloud runtime DDL is only guarded migrate_model_limits.py; embedding identities/indexes never change. See ADR-0037.
- DiskANN v3+ is optional and explicitly configured. Default and deployed JHU mode remains exact; representative ANN/performance acceptance is open.
- Tenant LLM catalogs select Azure OpenAI or JHU Ollama generate through bound providers; model access uses current server groups and revisioned SQL policies. Embedding providers remain separate.
- JHU embedding_config adds digest-pinned Ollama Nomic 768. Active index selects query/ingest provider; explicit backfill/activation preserves other model indexes and shared chunks. Do not silently substitute profiles or truncate inputs.
- Blob Storage, Azure Container Apps, Static Web Apps and optional Key Vault resolution are implemented.
- JHU `sidecar` is an explicit Linux ACA dev/prod mode, separate from local `managed`. MI snapshots and protected loopback health bind app/revision/replica/exact tenant/target. `deploy_jhu_sidecar.py` defaults to read-only, patches only an existing reviewed template and requires separate capacity/session/schema/model approval. Read docs/development/jhu-sidecar-azure.md; source readiness is not cloud acceptance.
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
- Record durable architectural decisions in `docs/adr/`, using the highest existing ADR number plus one. `ADR-0001-template.md` remains a generic template.
- Add/update the corresponding explanations in `docs/tests_explained/` for changed test modules.
- Keep `docs/navigation_guide.md` synchronized with source files using relative paths and concise Czech descriptions.
- Keep project-state and implementation notes concise and current. Historical details belong in `.agents/memory/archive/` or deployment reports; archive contents are not current instructions.
- Use repository-relative links in documents. Do not depend on another machine's absolute paths, hidden agent brain folders or private scratch scripts for standard workflows.
- Report outcome, relevant verification, remaining risks and exactly one recommended next slice. Do not imply cloud deployment when only sources changed.

## Repository publication

Before a normal release or a JHU handoff, read `.agents/workflows/jhu-publication.md`. Keep the GitHub development graph, independent Forgejo snapshot graph and Azure runtime deployment separate. The versioned exporters/templates are canonical; ignored historical operators are not required. Never mirror/merge the development history into JHU. A source-repository release does not implicitly authorize Forgejo or cloud changes.

## Azure actions

Azure CLI/tool access may be available. Availability alone is not authorization to change resources. For required cloud changes, prepare a concrete handoff in `.agents/inbox/` with target guards, operations, non-secret values and rollback before requesting approval. Follow existing explicit user authorization within its scope; do not repeatedly ask for the same approval.

Use managed identity/Key Vault when configured; do not invent secrets or change RBAC/capacity. Keep resource provisioning, schema migration, embedding backfill, index activation and image/frontend release separate. Current deployment scripts default to read-only plans. Only their guarded Apply paths write resources; frontend release never creates a SWA.

Maintenance must preserve exact tenant scope and validate sources before writes. A full refresh replaces documents individually and prunes initial stale rows only after all inputs succeed; it does not delete the corpus before extraction/model calls.
