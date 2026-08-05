# ADR-0015: Multi-Environment (DEV & PROD) Architecture & Data Isolation

- Status: accepted
- Date: 2026-07-31
- Owners: Dolphin AI Search Core Team

## Context

As the AI Search application matures and transitions to client deployments, we need a robust, clean separation between **Development (DEV)** and **Production (PROD)** environments.
Developers need an isolated environment where they can test new chunking strategies, document ingestion, schema modifications, and prompt adjustments without affecting the client's live production database or uploaded document repository.

Key requirements:
1. Complete data isolation between DEV and PROD environments.
2. Low cost (avoiding duplicate base infrastructure fees in Azure).
3. Zero code changes required when switching environments.
4. Seamless support for multi-client deployment provisioning (`<client>-<env>`).

## Decision

We adopt a **Dynamic Environment Precedence Architecture**:

1. **Environment Configuration Files (`.env.dev` and `.env.prod`)**:
   - The FastAPI backend (`app/core/config.py`) dynamically inspects the `APP_ENV` environment variable (`dev` or `prod`).
   - If `APP_ENV=dev`, settings load from `.env.dev` with default database `ai_search_dev` and blob container `dolphin-originals-dev`.
   - If `APP_ENV=prod`, settings load from `.env.prod` with default database `ai_search_prod` and blob container `dolphin-originals`.

2. **Automated Azure Container Apps Deployment (`deploy_backend.ps1`)**:
   - Parameterized deployment accepts `-Client` (e.g. `dolphin`, `university`) and `-Environment` (`dev` or `prod`).
   - Dynamically targets Container App `${Client}-ai-search-backend-${Environment}` and injects container environment variables (`APP_ENV`, `POSTGRES_DB`, `AZURE_BLOB_CONTAINER_ORIGINALS`).

3. **Frontend Application Environment Binding (`deploy_frontend.ps1`)**:
   - Dedicated environment files (`frontend-user/.env.development`, `frontend-user/.env.production`, `frontend-admin/.env.development`, `frontend-admin/.env.production`) configure `NEXT_PUBLIC_BACKEND_URL` for target environments.

## Options Considered

1. **Single Shared Environment with Tenant Filters Only**:
   - *Rejected*: Shared databases risk accidental data deletion or schema corruption during active development.
2. **Duplicate Azure Resource Groups**:
   - *Rejected*: Incurs redundant base costs for dedicated Azure PostgreSQL Flexible instances when schema/database separation achieves 100% isolation on the same server.

## Consequences

- Developers can run local experiments or deploy DEV containers without risking production client data.
- Deploying a new client or environment is fully automated using `deploy_backend.ps1` and `deploy_frontend.ps1`.
- Zero additional Azure infrastructure costs.
