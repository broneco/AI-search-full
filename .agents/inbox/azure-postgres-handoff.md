# Azure Deployment Handoff: Azure PostgreSQL Flexible Server Setup

- Status: completed
- Created: 2026-05-28
- Related task: Phase 0 RAG Proof of Concept
- Related ADR: None

## Why this handoff exists

Setting up the local Docker database (`pgvector`) is blocked on Windows host environment execution privilege restrictions. Because our architecture is Azure-first, spinning up an inexpensive, small-tier **Azure Database for PostgreSQL Flexible Server** is the most efficient and robust alternative to unblock the spike.

## Goal

Provide a real, managed PostgreSQL database in Microsoft Azure with `pgvector` and `uuid-ossp` extensions enabled, allowing our locally-running FastAPI app and RAG pipeline integration tests to execute and persist records.

## Resources to create or modify

Please log into your Azure Portal and create the following resource:

| Resource | Action | Suggested settings | Notes |
|---|---|---|---|
| **PostgreSQL Flexible Server** | Create | - Name: `ai-search-postgres` (or unique name)<br>- PostgreSQL Version: **16**<br>- Workload Type: **Development** (burstable SKU, e.g. `Standard_B1ms` to minimize costs)<br>- High Availability: **Disabled** (not needed for dev)<br>- Storage: **32 GB** | Do not paste the administrator password in any shared files. |
| **Firewall / Networking** | Modify | - Select **Public access (allowed IP addresses)**<br>- Click **Add current client IP address** to authorize your local computer's IP address. | Necessary to allow connection from your local VS Code / python runtime. |
| **Server Parameters** | Modify | - Navigate to **Server Parameters** under Settings.<br>- Search for `azure.extensions`. <br>- Check **VECTOR** and **UUID-OSSP** and save. | This is required to load `pgvector` support on the Azure Postgres instance. |
| **Database** | Create | - Name: `ai_search` | Created inside the PostgreSQL Flexible Server instance. |

## Required app configuration keys

Once the server and database are created, please append or update the following environment keys in your local, untracked `.env` file at the root of the project workspace (`c:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\AI Search Full\.env`):

```ini
# PostgreSQL Azure Connection Details
POSTGRES_HOST=<your-azure-postgresql-server-name>.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=ai_search
POSTGRES_USER=<your-admin-username>
POSTGRES_PASSWORD=<your-admin-password>
POSTGRES_SSLMODE=require
```

## Validation steps for human

Verify network connectivity to the Azure Postgres database by executing a quick health check test suite:
```powershell
.venv\Scripts\pytest.exe tests/test_health.py -v
```

## Validation steps for agent after completion

Once you configure these connection variables and confirm completion, the agent will:
1. Initialize the database schemas and extensions via the `/api/documents/ingest` call.
2. Store text chunks with real 1536-dimensional OpenAI embeddings in the Azure database.
3. Run the integration test suite and assert that similarity-based RAG chat completions succeed.

## Rollback

To disable or clean up:
1. Remove the connection strings from your local `.env` file.
2. Delete the resource group or the Azure Database for PostgreSQL Flexible Server instance in the Azure Portal to avoid recurring cloud costs.
