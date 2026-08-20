# ADR-0016: Architectural Migration to Azure SQL Database (Microsoft SQL)

- Status: accepted
- Date: 2026-08-18
- Owners: AI Search Core Team
- Supersedes: ADR-0002-use-postgresql-pgvector-for-mvp.md
- Superseded by: N/A

## Context

The initial MVP proof-of-concept utilized Azure Database for PostgreSQL Flexible Server with `pgvector` and `to_tsvector` GIN indexes for hybrid document search. To align with Microsoft-first enterprise infrastructure guidelines, enterprise SQL Server environments, and unified Azure PaaS database governance, the project requires migrating the primary backend database layer to Azure SQL Database (Microsoft SQL Server).

## Decision

We migrate the primary relational, document chunking, user thread, and vector storage layer from PostgreSQL to **Azure SQL Database (Microsoft SQL Server)** using `pyodbc` and SQLAlchemy 2.0.

Key technical specifications:
1. **Azure SQL PaaS Tier**: Azure SQL Database Serverless General Purpose (`GP_S_Gen5_1`) with auto-pause for development, scalable to vCore provisioned compute for production.
2. **Dialect Abstraction**: SQLAlchemy 2.0 models utilize cross-database types (`Uuid`, `JSON`, `UniversalVector` TypeDecorator) supporting both Azure SQL Database (`mssql+pyodbc`) and PostgreSQL.
3. **Authentication**: Support both SQL Server authentication (with passwords stored in local untracked `.env` / Key Vault) and bezheslové Microsoft Entra ID / System-Assigned Managed Identity authentication via `azure-identity` (`DefaultAzureCredential`).
4. **Hybrid Search Alignment**: Vector similarity and keyword retrieval dynamically adapt to MS SQL queries (`JSON` float arrays / T-SQL functions, `LIKE`/Full-Text catalog) with reciprocal rank fusion (RRF).

## Options considered

1. **Option 1: Retain PostgreSQL Flexible Server + pgvector** (Rejected due to requirement for native Microsoft SQL integration).
2. **Option 2: Azure AI Search (Cognitive Search)** (Deferred for future enterprise scale; Azure SQL Database fulfills current relational + RAG retrieval requirements).
3. **Option 3: Azure SQL Database + pyodbc + Managed Identity** (Accepted).

## Consequences

- **Positives**:
  - Native alignment with Microsoft enterprise Azure stack and corporate governance.
  - Support for passwordless Entra ID Managed Identity authentication in Azure Container Apps.
  - Clean separation of database engine via SQLAlchemy abstraction layer.
- **Negatives**:
  - Existing local PostgreSQL data requires re-ingestion via `python full_refresh_ingest.py`.
  - Docker container image requires `msodbcsql18` (Microsoft ODBC Driver 18 for SQL Server).

## Implementation notes

- Environment variables added: `AZURE_SQL_HOST`, `AZURE_SQL_PORT`, `AZURE_SQL_DB`, `AZURE_SQL_USER`, `AZURE_SQL_PASSWORD`, `AZURE_SQL_DRIVER`.
- Database engine automatically chooses Azure SQL if `AZURE_SQL_HOST` is configured in environment settings.
- Handled in `app/storage/db.py`, `app/storage/models.py`, `app/retrieval/vector.py`, and `app/core/config.py`.

## Follow-ups

- [x] Provision Azure SQL Server (`dolphin-ai-search-sql`) and Database (`dolphin-ai-search-sqldb`) in Azure Portal.
- [ ] Run full document re-ingestion pipeline (`python full_refresh_ingest.py`).
- [ ] Deploy updated Docker backend container image to Azure Container Apps.
