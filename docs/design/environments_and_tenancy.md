# Environments & Multi-Tenancy Architecture

This document describes the environment separation (**DEV** vs **PROD**) and multi-tenant provisioning strategy for the Dolphin AI Search Platform.

---

## 1. Environment Isolation Model

The platform uses a 3-layer isolation model ensuring zero data leakage between development and production.

```
                       ┌──────────────────────────────────────────────────────────┐
                       │                       AZURE RESOURCE GROUP               │
                       │                                                          │
   [ KLIENT (PROD) ] ──┼──> Frontend PROD ──> Backend Container (PROD) ─────┐    │
                       │                      APP_ENV=prod                  │    │
                       │                                                    ├──> PostgreSQL (ai_search_prod)
                       │                                                    ├──> Blob Container (dolphin-originals-prod)
 [ VY / TEST (DEV) ] ──┼──> Frontend DEV  ──> Backend Container (DEV)  ─────┤    │
                       │                      APP_ENV=dev                   ├──> PostgreSQL (ai_search_dev)
                       │                                                    └──> Blob Container (dolphin-originals-dev)
                       └──────────────────────────────────────────────────────────┘
```

### Resource Naming & Mapping

| Environment | Backend App Name | Database Target | Azure Blob Container | Tenant ID |
| :--- | :--- | :--- | :--- | :--- |
| **DEV** | `<client>-ai-search-backend-dev` | `<client>_ai_search_dev` | `<client>-originals-dev` | `<client>-dev` |
| **PROD** | `<client>-ai-search-backend-prod` | `<client>_ai_search_prod` | `<client>-originals` | `<client>-prod` |

---

## 2. Configuration Resolution Order

When the FastAPI application starts:
1. It reads the `APP_ENV` environment variable (`dev` by default if omitted).
2. It attempts to load settings from `.env.<APP_ENV>` (e.g. `.env.dev` or `.env.prod`).
3. If specific variables (`POSTGRES_DB`, `AZURE_BLOB_CONTAINER_ORIGINALS`) are not defined in the `.env` file, `@model_validator` in `app/core/config.py` dynamically infers default names based on `APP_ENV`.

---

## 3. Provisioning a New Client

To deploy a new client (e.g. `university` or `consulting`):

1. **Deploy Backend Container App**:
   ```powershell
   .\deploy_backend.ps1 -Client university -Environment dev
   .\deploy_backend.ps1 -Client university -Environment prod
   ```

2. **Deploy Frontend Web App**:
   ```powershell
   .\deploy_frontend.ps1 -Client university -Environment dev -AppType user
   .\deploy_frontend.ps1 -Client university -Environment prod -AppType user
   ```
