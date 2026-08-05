# Azure Container Apps & Static Web Apps Multi-Environment Deployment Guide

This guide describes how to deploy the Dolphin Consulting AI Search application (Backend + User Search App + Admin Console) across **DEV** and **PROD** environments.

---

## 1. Multi-Environment Topology

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

---

## 2. Automated One-Command Deployment

### A. Deploy Backend Container App

To build and deploy the FastAPI backend for a specific client and environment:

```powershell
# Deploy DEV environment:
.\deploy_backend.ps1 -Client dolphin -Environment dev

# Deploy PROD environment:
.\deploy_backend.ps1 -Client dolphin -Environment prod
```

The script automatically:
1. Builds the Docker image in Azure ACR using `az acr build`.
2. Updates or provisions Container App `<client>-ai-search-backend-<environment>`.
3. Injects environment variables (`APP_ENV`, `POSTGRES_DB`, `AZURE_BLOB_CONTAINER_ORIGINALS`, `TENANT_ID`).
4. Updates CORS rules for frontend access.

---

### B. Deploy Frontend Applications

To build and deploy frontend applications to Azure Static Web Apps:

```powershell
# Deploy End-User Search Application (DEV):
.\deploy_frontend.ps1 -Client dolphin -Environment dev -AppType user

# Deploy Admin Console (PROD):
.\deploy_frontend.ps1 -Client dolphin -Environment prod -AppType admin
```

---

## 3. Logs & Operational Troubleshooting

Stream live logs from any container app environment:

```bash
az containerapp logs show \
  --resource-group DOLPHIN_DS \
  --name dolphin-ai-search-backend-dev \
  --follow
```
