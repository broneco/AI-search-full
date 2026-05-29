# Changelog

All notable project and agent-environment changes must be recorded here.

Format follows the spirit of Keep a Changelog: human-readable, chronological, with an `Unreleased` section.

## [Unreleased]

## [0.2.0] - 2026-05-29

### Added
- **Phase 1 Hybrid Retrieval**: Integrated PostgreSQL Full-Text Search (FTS) capabilities to query lexical hits concurrently with pgvector semantic search.
- **Weighted Reciprocal Rank Fusion (RRF)**: Implemented a rank-based fusion algorithm fusing lexical and semantic outputs using weights configurable via `.env` (60% Vector, 40% FTS).
- **Next.js Single-Page Client Application**: Scaffolding of a React/TypeScript visual dashboard in `/frontend` using Geist typography and dark HSL variables.
- **Split-Panel conversational UI**: Conversational chat interface featuring grounded citation button triggers that dynamically expand details in a right-side Citations Workspace (displaying chunk text, page numbers, security ACL permissions, freshness flags, and matching scores).
- **Ingestion & Health Dashboards**: Visual stats panels listing ingested PDFs, chunk counts, backend API online/offline status checkers, and latency metrics.

### Changed
- **API Response Model Upgrades**: Added CORS middleware inside `app/main.py` and modified `ChatSource` response schemas to map segment text content. Included a `/api/documents/list` endpoint serving ingestion statistics.

### Fixed
- **Czech FTS Index Startup Warnings**: Prevented transaction abort exception tracebacks by proactively checking `pg_ts_config` catalogs for Czech (`'cs'`) configurations before trying to build GIN indexes.
- **Hybrid Retrieval Latency Timeouts**: Replaced slow sequential database query loops (which ran up to 100 SQL statements per query) with a high-performance pure-Python cosine similarity check, reducing retrieval response times to milliseconds.

## [0.1.0] - 2026-05-29

### Added
- Initial `.agents/` operating environment and canonical operating contract in `.agents/AGENTS.md`.
- Minimal FastAPI backend skeleton under `app/` with typed settings module (`app/core/config.py`).
- Interactive Swagger API docs mounted at `/docs`.
- Modern PostgreSQL+Psycopg connection session and engine setups with database schema and extension initializers (`init_db` in `app/storage/db.py`).
- Declarative SQLAlchemy models mapping `DBDocument` and `DBChunk` (with a 1536-dimensional Vector embedding field) in `app/storage/models.py`.
- Vector retrieval pipeline subclass `VectorRetriever` implementing pgvector similarity lookup, metadata filtering, and security ACL controls in `app/retrieval/vector.py`.
- Page-aware, overlapping paragraph character text splitter chunker (`app/ingestion/chunking.py`).
- PDF text extractor using `pypdf` (`app/ingestion/extraction.py`) and folder scanning loaders (`app/ingestion/loaders/local.py`).
- Concurrent batching logic using `asyncio.gather` for embedding generation in `app/providers/azure_openai.py`.
- Bulk multi-row SQL insertion compiler utilizing SQLAlchemy 2.0 multi-row insert statements in `app/ingestion/pipeline.py` to prevent network latency overheads.
- Incremental and full-refresh command line loader triggers (`ingest.py` and `full_refresh_ingest.py`) at root.
- Interactive terminal testing tool `ask.py` to quickly query corporate knowledge files.
- Automated integration test coverage validating health checks, ingestion splitting, and E2E RAG chat completions.

### Changed
- Refactored `app/ingestion/pipeline.py` to output beautiful, structured step-by-step visual progress reports during ingestion execution.
- Added strict `AZURE_OPENAI_TIMEOUT` (15.0 seconds default) parameter in `app/core/config.py` and configured the embedding and chat clients in `app/providers/azure_openai.py` to use it, preventing silent network hangs.
- Added explicit `connect_timeout` (15 seconds default) database connection settings in `app/storage/db.py` to avoid indefinite database connection hangs.

### Fixed
- Fixed potential silent hangs during batch document ingestion by ensuring clear progress indicators print for every distinct ingestion phase (file loading, page extraction, text chunk splitting, OpenAI embedding batch queries, database bulk insert).
- Fixed character splitter infinite loop bug in `chunking.py` for pages with short texts by strictly enforcing forward progress window advanced steps.

### Security
- Added rule that secrets must never be committed and must be provided through Azure Key Vault, environment variables, or explicit human handoff.
