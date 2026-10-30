# Tenant Configuration & Asset Policy (`tenant-configuration-policy.md`)

This policy dictates how multi-tenant configurations, system prompts, search metaparameters, document classification rules, visual branding profiles, logo assets, and environment variables are structured and loaded within the project.

---

## 1. Canonical Location of Tenant Configuration


Cloud mutable override exception (ADR-0042): in APP_ENV dev/prod, administrator edits to prompts.json, search_config.json and classification_config.json live in exact-tenant SQL tenant_settings. Public tenants/ files remain bundled file-level defaults only for absent rows; SQL errors must fail explicitly. Do not rewrite cloud defaults or legacy Blob config during release. First migration requires explicit capture/reconciliation and insert-only import; local/test overlays stay as below. See docs/development/non-destructive-updates.md.

All configuration files, environment variable files, and graphic assets belonging to specific client tenants MUST be placed inside the root `tenants/` directory in dedicated subfolders named after the base tenant identifier:

```text
tenants/
├── default/                  # Required public JSON/assets fallback; private env is optional
│   ├── .env.dev              # Default DEV environment settings
│   ├── .env.prod             # Default PROD environment settings
│   ├── prompts.json          # Default RAG system prompts (CS/EN)
│   ├── search_config.json    # Default chunking & retrieval parameters
│   ├── classification_config.json # Default categories & ACL rules
│   ├── branding.json         # Default visual theme & brand profile
│   └── logo.png              # Default fallback logo asset
├── dolphin/                  # Dolphin Consulting tenant
│   ├── .env.dev              # Dolphin DEV connection strings
│   ├── .env.prod             # Dolphin PROD connection strings
│   ├── prompts.json
│   ├── search_config.json
│   ├── classification_config.json
│   ├── branding.json
│   └── logo.png
├── alzbeta/                  # Nemocnice sv. Alžběty tenant
│   ├── prompts.json
│   ├── branding.json
│   └── logo.png
├── jhu/                      # Jihočeská Univerzita tenant
│   ├── .env.prod             # JHU PROD connection strings
│   ├── prompts.json
│   ├── branding.json
│   └── logo.webp
└── showcase/                 # Showcase tenant
    └── .env.dev               # Showcase DEV environment settings
```

---

## 2. File-Level Fallback Resolution Rule (`default`)

Whenever a tenant-specific file is requested or required at runtime:

1. The JSON/asset resolver checks `tenants/<tenant_base>/<filename>`.
2. **If the file is missing** in the tenant's subfolder, the system automatically falls back to **`tenants/default/<filename>`**.
3. Fallback operates at the **entire file level**, not line-by-line or key-by-key.

Environment variables use the separate precedence defined in `app/core/config.py`: process variables override Pydantic env files, and later env files override earlier ones. Do not assume JSON fallback semantics apply to env files. Local/test use their isolated profiles and ignored overlays.

---

## 3. Git Security & Environmental Isolation Policy

- **All `.env*` files residing in tenant subfolders (`tenants/*/.env*`) are strictly ignored by Git** via `.gitignore` to prevent committing sensitive connection strings or secrets.
- `deploy_backend.ps1` and `app/core/config.py` check `tenants/<tenant_base>/.env.<app_env>` first before checking root `.env` files.

---

## 4. Tenant File Parity & Structural Parity Rule

- **At least one configured tenant is sufficient; do not require ten private env files on a new checkout.**
- Configured tenant env files must agree on key structure; wholly unconfigured placeholder tenants are excluded. A clean checkout runs isolated fixtures without credentials and skips only the optional real-env structural check.
- When adding a setting, update the non-secret `.env.example` and the actually configured tenant files where applicable. Do not manufacture secret-bearing files for unused tenants.
- When placeholder values are used for new or unconfigured tenants (e.g. `<REQUIRED_VALUE>` or `YOUR_SECRET_HERE`), the agent must follow the **Placeholder Handoff Policy**.

---

## 5. Placeholder Handoff Policy (`.agents/inbox/`)

- Whenever an agent creates a new tenant `.env` file or adds new variable keys containing placeholder values:
  1. The agent **MUST NOT** commit or assume production secrets.
  2. The agent **MUST** create a handoff document in `.agents/inbox/YYYY-MM-DD-tenant-env-placeholder-handoff.md`.
  3. The handoff file must clearly list:
     - Which tenant environment files contain placeholders.
     - The exact variable names that require human configuration in Azure or local environment.
     - Post-configuration validation instructions.

---

## 6. Mandatory Agent Instructions

- **NEVER** hardcode tenant system prompts or search parameters directly inside `app/core/` code files.
- Keep cloud tenant files under `tenants/`. Documented local/test exceptions are ignored root `.env.local`/`.env.test` files and JSON overlays under `.local/`; these must never alter public tenant files.
- When creating or modifying tenant env, preserve key parity among configured environments and keep templates non-secret; one configured tenant is enough.
- Configuration aliases use `app.core.tenant_identity.tenant_config_name`; `ju-prod` loads `jhu` configuration but remains `ju-prod` in database/token/ACL identity.
- Always use `TenantConfigResolver` (`app.core.tenant_config.load_tenant_json` / `resolve_tenant_file_path`) in backend services.
