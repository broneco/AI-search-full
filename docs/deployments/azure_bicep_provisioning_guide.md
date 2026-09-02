# Enterprise Client Infrastructure Provisioning Guide (Azure Bicep & DTU Model)

This guide documents the Infrastructure-as-Code (IaC) deployment process for enterprise clients requiring dedicated Azure resources in `ai-search-rg-dev`, `ai-search-rg-prod`, or `ai-search-showcase-rg-dev`.

---

## 1. Feature Architecture

When provisioning a new client environment, the Bicep templates dynamically adjust based on **ON/OFF resource toggles** in `infra/main.bicep` and support **Azure SQL Database in DTU mode**.

```
                                ┌───────────────────────────────────────────────────┐
                                │            TARGET RESOURCE GROUP                  │
                                │                                                   │
   [ deploy_infra.ps1 ] ──────>│ ├── Log Analytics & App Insights                  │
                                │ ├── Storage Account (originals, artifacts)        │
   Toggles:                     │ ├── Azure SQL Server & DB (DTU Model)             │
   - provisionAzureSql = true   │ ├── Azure OpenAI (embeddings & chat models)       │
   - provisionOpenAI = true     │ ├── Container Apps Environment & Backend App      │
   - provisionStorage = true    │ └── Static Web Apps (User & Admin Frontends)      │
                                └───────────────────────────────────────────────────┘
```

---

## 2. Parameter Tuning (`infra/main.bicep`)

Before running deployment, tune parameters for your target environment:

```bicep
param clientName = 'dolphin'
param environment = 'dev'
param location = 'northeurope'

// Database DTU parameters
param provisionAzureSql = true
param dtuSkuName = 'Basic'
param dtuTier = 'Basic'
param dtus = 5

param provisionOpenAI = true
param provisionStorage = true
```

---

## 3. Launching Deployment

Run the automated deployment script for your target Resource Group:

```powershell
# Deploying to Dev RG (ai-search-rg-dev)
.\infra\deploy_infra.ps1 -Client dolphin -Environment dev -ResourceGroup "ai-search-rg-dev"

# Deploying to Prod RG (ai-search-rg-prod)
.\infra\deploy_infra.ps1 -Client dolphin -Environment prod -ResourceGroup "ai-search-rg-prod"

# Deploying to Showcase RG (ai-search-showcase-rg-dev)
.\infra\deploy_infra.ps1 -Client showcase -Environment dev -ResourceGroup "ai-search-showcase-rg-dev"
```
