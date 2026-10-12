# Tenant Configuration & Asset Policy (`tenant-configuration-policy.md`)

This policy dictates how multi-tenant configurations, system prompts, search metaparameters, document classification rules, visual branding profiles, logo assets, and environment variables are structured and loaded within the project.

---

## 1. Canonical Location of Tenant Configuration

All configuration files, environment variable files, and graphic assets belonging to specific client tenants MUST be placed inside the root `tenants/` directory in dedicated subfolders named after the base tenant identifier:

```text
tenants/
├── default/                  # [REQUIRED] Fallback tenant
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

1. The system checks `tenants/<tenant_base>/<filename>` (or `tenants/<tenant_base>/.env.<app_env>`).
2. **If the file is missing** in the tenant's subfolder, the system automatically falls back to **`tenants/default/<filename>`** (or `tenants/default/.env.<app_env>`).
3. Fallback operates at the **entire file level**, not line-by-line or key-by-key.

---

## 3. Git Security & Environmental Isolation Policy

- **All `.env*` files residing in tenant subfolders (`tenants/*/.env*`) are strictly ignored by Git** via `.gitignore` to prevent committing sensitive connection strings or secrets.
- `deploy_backend.ps1` and `app/core/config.py` check `tenants/<tenant_base>/.env.<app_env>` first before checking root `.env` files.

---

## 4. Tenant File Parity & Structural Parity Rule

- **All `.env.dev` and `.env.prod` files across all tenant subfolders (`tenants/<tenant>/`) MUST be kept structurally identical with 100% variable key parity.**
- If a new variable, key, or section is added to any `.env` file or tenant configuration file, it **MUST be added to all tenant `.env` files** across all tenants (`default`, `dolphin`, `alzbeta`, `jhu`, `showcase`).
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
- **NEVER** place tenant-specific configuration or environment files outside of the `tenants/` directory.
- When creating or modifying a tenant `.env` file, ensure **100% variable key parity** across all tenants in `tenants/`.
- Always use `TenantConfigResolver` (`app.core.tenant_config.load_tenant_json` / `resolve_tenant_file_path`) in backend services.
