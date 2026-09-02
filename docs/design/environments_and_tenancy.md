# Environments & Multi-Tenancy Architecture

This document describes the environment separation (**DEV**, **PROD**, and **SHOWCASE**) and multi-tenant provisioning strategy for the AI Search Platform.

---

## 1. Three-Tier Resource Group Isolation Model

The platform uses a 3-tier isolation model ensuring zero cross-contamination between development, production, and demo showcase environments.

```
┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
│  DEV RG: ai-search-rg-dev            │  │  PROD RG: ai-search-rg-prod          │  │ SHOWCASE RG: ai-search-showcase-rg-dev│
│                                      │  │                                      │  │                                      │
│  ├── Backend DEV (ca-aisearch-*-dev) │  │  ├── Backend PROD (ca-aisearch-*-prod│  │  ├── Backend Showcase (ca-aisearch-  │
│  ├── SQL Server (sql-aisearch-dev)   │  │  ├── SQL Server (sql-aisearch-prod)  │  │  │   showcase)                          │
│  │   └── sqldb-dolphin-dev (DTU)     │  │  │   └── sqldb-dolphin-prod (DTU)    │  │  ├── SQL Server (sql-aisearch-     │
│  ├── Storage (staisearchdev)         │  │  ├── Storage (staisearchprod)        │  │  │   showcase)                          │
│  │   └── dolphin-originals-dev       │  │  │   └── dolphin-originals-prod      │  │  │   └── sqldb-showcase (DTU)        │
│  └── Frontends (swa-aisearch-*-dev)  │  └── Frontends (swa-aisearch-*-prod) │  └── Storage (staisearchshowcase)    │
└──────────────────────────────────────┘  └──────────────────────────────────────┘  └──────────────────────────────────────┘
```

### Resource Naming & Mapping

| Environment | Resource Group | Backend Container App | Azure SQL Database (DTU) | Azure Storage Account | Blob Container |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEV** | `ai-search-rg-dev` | `ca-aisearch-<client>-dev` | `sqldb-<client>-dev` | `staisearchdev` | `<client>-originals-dev` |
| **PROD** | `ai-search-rg-prod` | `ca-aisearch-<client>-prod` | `sqldb-<client>-prod` | `staisearchprod` | `<client>-originals-prod` |
| **SHOWCASE** | `ai-search-showcase-rg-dev` | `ca-aisearch-showcase` | `sqldb-showcase` | `staisearchshowcase` | `showcase-originals` |

---

## 2. Azure SQL Database DTU Model

All Azure SQL databases utilize the **DTU purchasing model**:
- **DEV & SHOWCASE**: Basic Tier (5 DTU, max 2 GB) or Standard Tier S0 (10 DTU, max 250 GB).
- **PROD**: Standard Tier S1 (20 DTU) to S3 (100 DTU) or Premium depending on corporate SLA.
- **Scaling**: Live, zero-downtime scale-up from Basic to Standard S0/S1 via Azure Portal or Azure CLI.

---

## 3. Provisioning a Client Environment

To deploy a backend and frontend to a specific Resource Group:

1. **Deploy Backend Container App**:
   ```powershell
   .\deploy_backend.ps1 -Client dolphin -Environment dev -ResourceGroup ai-search-rg-dev
   .\deploy_backend.ps1 -Client dolphin -Environment prod -ResourceGroup ai-search-rg-prod
   .\deploy_backend.ps1 -Client showcase -Environment dev -ResourceGroup ai-search-showcase-rg-dev
   ```

2. **Deploy Frontend Web App**:
   ```powershell
   .\deploy_frontend.ps1 -Client dolphin -Environment dev -AppType user -ResourceGroup ai-search-rg-dev
   .\deploy_frontend.ps1 -Client dolphin -Environment prod -AppType user -ResourceGroup ai-search-rg-prod
   .\deploy_frontend.ps1 -Client showcase -Environment dev -AppType user -ResourceGroup ai-search-showcase-rg-dev
   ```
