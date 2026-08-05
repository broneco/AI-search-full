# Client Infrastructure Provisioning (Azure Bicep)

This directory contains modular **Azure Bicep** templates for provisioning dedicated client environments.

---

## 1. Directory Structure

```
infra/
├── main.bicep                  # Orchestration Bicep template with ON/OFF resource toggles
├── main.bicepparam             # Parameter file for tuning new vs existing resources
├── deploy_infra.ps1            # Automated PowerShell script executing 'az deployment group create'
└── modules/
    ├── log_analytics.bicep     # Observability (Application Insights & Log Analytics)
    ├── storage.bicep           # Storage Account & Blob Containers (originals, artifacts)
    ├── postgres.bicep          # PostgreSQL Flexible Server & pgvector extension
    ├── openai.bicep            # Azure OpenAI & Model Deployments (embeddings & chat)
    ├── acr.bicep               # Azure Container Registry
    ├── containerapp.bicep      # Azure Container Apps Environment & Backend App
    └── staticwebapp.bicep      # Azure Static Web Apps (user & admin frontends)
```

---

## 2. Resource Provisioning Modes

`infra/main.bicep` supports **ON/OFF resource toggles**:

- **Mode A: Full Client Isolation (Create All)**:
  Set `provisionPostgres = true`, `provisionOpenAI = true`, `provisionStorage = true`.

- **Mode B: Hybrid / Shared Infrastructure (Reuse Existing)**:
  Set `provisionPostgres = false` and supply `existingPostgresHost`.
  Set `provisionOpenAI = false` and supply `existingOpenAiEndpoint`.

---

## 3. Deployment Command

```powershell
# Deploy infrastructure for a client:
.\infra\deploy_infra.ps1 -Client dolphin -Environment dev

# Deploy for a new university client:
.\infra\deploy_infra.ps1 -Client university -Environment prod -ResourceGroup "UNIVERSITY_AI_RG"
```
