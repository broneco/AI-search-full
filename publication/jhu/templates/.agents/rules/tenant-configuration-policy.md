# Tenant Configuration Policy

The only bundled tenant is JHU under tenants/jhu. It has prompts.json, search_config.json, classification_config.json, branding.json and logo.webp. The public JSON/resources ship with the wheel; private .env files never do. Cloud env files live under tenants/jhu/.env.dev or .env.prod; local/test profiles use ignored .env.local/.env.test and ignored overlays.

Use app.core.tenant_identity.tenant_config_name for directory aliasing. ju-prod loads jhu configuration but remains ju-prod in data/token/ACL. Use the existing resolver for JSON. Shared default fallback remains a framework capability, but this snapshot materializes required JHU files and needs no other bundled tenant.

At least one configured tenant suffices for the optional real-env structural check. Unconfigured placeholder environments are excluded. Synthetic test tenants do not require real client configuration. Preserve key parity among actually configured files; update .env.example with non-secret settings only. Process environment wins over the Pydantic env-file sequence; later files override earlier ones.

Never hardcode tenant prompts in backend code or commit private env. Placeholder values in a newly configured environment require a focused non-secret handoff explaining the missing keys and validation. Preserve separate local/test/cloud database targets.
