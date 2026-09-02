# ADR-0017: Azure SQL Database DTU Purchasing Model & Three-Tier Resource Group Architecture

- Status: accepted
- Date: 2026-09-02
- Owners: AI Search Core Team
- Supersedes: Partial update to ADR-0016
- Superseded by: N/A

## Context

The AI Search Platform requires structured multi-environment isolation and predictable cloud resource pricing across clients. Previously, development infrastructure used Azure SQL Database Serverless General Purpose (`GP_S_Gen5_1`) with auto-pause, which introduced initial wake-up connection latencies after idle periods. Additionally, multi-tenant development resources and isolated showcase environments needed a standardized Azure Resource Group and naming convention standard.

## Decision

1. **Three-Tier Resource Group Isolation Strategy**:
   - **Dev Resource Group (`ai-search-rg-dev`)**: Shared multi-tenant development environment hosting dev backends, frontends, storage containers, and dev SQL databases.
   - **Prod Resource Group (`ai-search-rg-prod`)**: Multi-tenant production environment hosting client prod services.
   - **Showcase Resource Group (`ai-search-showcase-rg-dev`)**: Dedicated, fully isolated single-tenant environment for demonstration and showcase purposes.

2. **Azure SQL Database DTU Purchasing Model**:
   - Adopt the **DTU-based purchasing model** (`Basic`, `Standard S0`, `Standard S1`) for Azure SQL Database instead of vCore Serverless.
   - Default tier for Dev and Showcase environments: **Basic (5 DTU)** or **Standard S0 (10 DTU)** for predictable pricing and instant execution without cold-start wake-up delays.
   - Support live, zero-downtime scale-up to **Standard S1/S2/S3** or **Premium** as production workload increases.

3. **Standardized Resource Naming Convention**:
   - Resource Groups: `ai-search-rg-dev`, `ai-search-rg-prod`, `ai-search-showcase-rg-dev`
   - Azure SQL Server: `sql-aisearch-{env}`
   - Azure SQL Database: `sqldb-{tenant}-{env}`
   - Storage Account: `staisearch{env}`
   - Container Apps Env / App: `cae-aisearch-{env}`, `ca-aisearch-{tenant}-{env}`
   - Static Web Apps: `swa-aisearch-{tenant}-{user|admin}-{env}`

## Options considered

1. **Option 1: Serverless vCore with Auto-Pause** (Rejected due to connection wake-up latency after idle periods).
2. **Option 2: Provisioned vCore** (Rejected for early phases due to higher minimum baseline cost per month).
3. **Option 3: DTU Purchasing Model (Basic / Standard S0/S1)** (Accepted: predictable costs, zero cold start, instant live scale-up).

## Consequences

- **Positives**:
  - Immediate database responsiveness without auto-pause delay.
  - Predictable fixed monthly cost starting at ~5 USD/month (Basic) or ~13 USD/month (Standard S0).
  - Clear multi-tenant separation in Dev/Prod RG and total isolation for Showcase RG.
- **Negatives**:
  - Storage limit of 2 GB on Basic Tier (requires scale-up to Standard S0 for 250 GB storage if document chunk volume exceeds 2 GB).

## Implementation notes

- Created Bicep module `infra/modules/azuresql.bicep` supporting DTU SKU options.
- Updated `infra/main.bicep`, `deploy_backend.ps1`, `deploy_frontend.ps1`, and `infra/deploy_infra.ps1`.
- Created deployment handoff document `.agents/inbox/2026-09-02-azure-resource-deployment-handoff.md`.

## Follow-ups

- [x] Create Bicep module `azuresql.bicep`.
- [x] Update PowerShell deployment scripts.
- [ ] Human user provisions resources in Azure Portal / CLI according to handoff guide.
