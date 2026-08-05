# Enterprise Client Infrastructure Provisioning Guide (Azure Bicep)

This guide documents the Infrastructure-as-Code (IaC) deployment process for enterprise clients requiring dedicated Azure resources.

---

## 1. Feature Architecture

When provisioning a new client environment, the Bicep templates dynamically adjust based on **ON/OFF resource toggles** in `infra/main.bicepparam`.

```
                               ┌───────────────────────────────────────────────────┐
                               │            CLIENT RESOURCE GROUP                  │
                               │                                                   │
   [ deploy_infra.ps1 ] ──────>│ ├── Log Analytics & App Insights                  │
                               │ ├── Storage Account (containers: originals, art.) │
   Toggles:                    │ ├── PostgreSQL Flexible (pgvector enabled)        │
   - provisionPostgres = true  │ ├── Azure OpenAI (embeddings & chat models)       │
   - provisionOpenAI = true    │ ├── Container Apps Environment & Backend App      │
   - provisionStorage = true   │ └── Static Web Apps (User & Admin Frontends)      │
                               └───────────────────────────────────────────────────┘
```

---

## 2. Parameter Tuning (`infra/main.bicepparam`)

Before running deployment, tune your parameters for the client:

```bicep
using 'main.bicep'

param clientName = 'university'
param environment = 'prod'
param location = 'northeurope'

// Toggles: Set false to reuse your existing shared Azure resources
param provisionPostgres = true
param existingPostgresHost = ''

param provisionOpenAI = true
param existingOpenAiEndpoint = ''

param provisionStorage = true
param existingStorageAccountName = ''
```

---

## 3. Launching Deployment

Run the automated deployment script:

```powershell
.\infra\deploy_infra.ps1 -Client university -Environment prod -ResourceGroup "UNIVERSITY_AI_RG"
```
