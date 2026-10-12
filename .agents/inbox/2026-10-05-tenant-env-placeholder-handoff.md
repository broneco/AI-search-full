# Tenant Environment Files Parity & Placeholder Configuration Handoff

**Date**: 2026-10-05  
**Author**: Antigravity Implementation Agent  
**Status**: Pending Administrator Review  

---

## 1. Overview

Per the **Tenant File Parity Rule** (`.agents/rules/tenant-configuration-policy.md`), 100% structural key parity has been established across all tenant `.env.dev` and `.env.prod` files in `tenants/`:

- `tenants/default/.env.dev` & `.env.prod`
- `tenants/dolphin/.env.dev` & `.env.prod`
- `tenants/alzbeta/.env.dev` & `.env.prod`
- `tenants/jhu/.env.dev` & `.env.prod`
- `tenants/showcase/.env.dev` & `.env.prod`

---

## 2. Configuration Action Required

Some environment files for newly initialized tenants contain placeholder values or shared dev credentials that should be verified or replaced with tenant-specific Azure resources before deploying to production:

### Tenants Needing Credential / Azure Resource Verification:

1. **`tenants/alzbeta/.env.dev` & `.env.prod`**:
   - `AZURE_RESOURCE_GROUP`: Set to `DOLPHIN_DS` or target Azure Resource Group.
   - `AZURE_CONTAINER_REGISTRY`: Set to `dolphinds` or target ACR.
   - `AZURE_CONTAINER_APP_NAME`: `alzbeta-ai-search-backend-dev` / `alzbeta-ai-search-backend-prod`.
   - `AZURE_SWA_USER_NAME`: `swa-alzbeta-prod` or target Static Web App name.
   - `AZURE_SWA_ADMIN_NAME`: `swa-alzbeta-admin-prod` or target Static Web App name.

2. **`tenants/jhu/.env.prod`**:
   - `AZURE_OPENAI_API_KEY`: Set from `VaseAPIKlicZFoundryProJHU` to active Azure OpenAI key.
   - `AZURE_SQL_PASSWORD`: Left empty to dynamically fetch secret `ju-ai-search-sql-sqlaccount-password-prod` from Key Vault `ju-ai-search-kv-prod`.

3. **`tenants/showcase/.env.dev` & `.env.prod`**:
   - `AZURE_OPENAI_API_KEY`: Verify key validity for `ai-search-showcase-aif-dev`.
   - `AZURE_SQL_PASSWORD`: Verify password for `ai-search-showcase-sql-dev.database.windows.net`.

---

## 3. Post-Configuration Verification Command

Run unit tests to confirm all tenant configs load cleanly:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_tenant_config.py
```
