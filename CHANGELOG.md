# Changelog

All notable project and agent-environment changes must be recorded here.

Format follows the spirit of Keep a Changelog: human-readable, chronological, with an `Unreleased` section.

## [Unreleased]

### Added
- **Swagger Security Header Testing**: Formally declared `X-User-Id` and `X-User-Groups` headers in FastAPI chat and document endpoints, automatically exposing them in the interactive Swagger UI (`/docs`). This allows developers to directly simulate specific user personas (e.g. `Management`, `HR`, `Finance`, `User`) and test the dynamic ACL-aware RAG pipeline inside Swagger.
- **Customized Swagger Request Schema Example**: Added Pydantic `json_schema_extra` configuration to `ChatRequest` to customize the default body pre-populated in Swagger. This supplies a realistic query by default and overrides Swagger's auto-generated `"additionalProp1": {}` dictionary placeholder with an empty `"filters": {}` to prevent accidental document filtering.
- **Isolated Database Testing**: Created `tests/conftest.py` to automatically redirect database connections to a dedicated isolated test database (`ai_search_test`) during test execution. This prevents the `pytest` test suite from dropping or wiping the primary development database (`ai_search`) when teardown fixtures run.

### Changed
- **Swagger UI Routing Cleanup**: Configured duplicate routes (`/health` and trailing-slash `/api/chat/`) to use `include_in_schema=False`. This completely resolves endpoint duplicates in Swagger UI while preserving production backwards compatibility and strict trailing-slash routing.

## [0.3.0] - 2026-05-29

### Added
- **Dynamic Security ACL Filtering**: Implemented a comprehensive four-level group authorization model (`Management` full bypass, `HR`, `Finance`, `User`) inside the `VectorRetriever` pipeline.
- **Dynamic Freshness Validation**: Added support for picking and applying freshness constraints (`Všechny` all documents, `Jen 2026` this year's files, `Jen platné` active current versions) dynamically.
- **Azure Blob Storage Client**: Implemented `BlobStorageProvider` utilizing the `azure-storage-blob` library to store and retrieve files from Azure cloud container storage, featuring a seamless local disk storage fallback.
- **Streamed PDF Viewer API Endpoint**: Added a new route `GET /api/documents/view/{document_id}` that dynamically streams PDFs inline from either Azure Blob or local folder locations.
- **Interactive Visual Testing Controls**: Added dynamic select dropdown role picker in Next.js client header and segment toggle button bar in query pane.
- **Direct PDF Hyperlinks & Dynamic Page Scrolling**: Replaced static file previews in the left sidebar directory and right citations panel with direct high-contrast hyperlinked anchors (`target="_blank"`) pointing straight to the FastAPI inline PDF streaming route, and appended native PDF scroll hash anchors (`#page=N`) to instantly open documents at the exact cited page.

### Changed
- **Metadata-Aware Ingestion Pipeline**: Upgraded both `ingest.py` and `full_refresh_ingest.py` to seed files with realistic creation datetimes, freshness states, and security allowed groups based on filenames.

### Fixed
- **NameError in Documents Route**: Fixed a FastAPI router startup compilation crash in `app/api/routes/documents.py` caused by a missing import of `Request`.
- **RAG Pipeline Test Assertions**: Updated the end-to-end integration test suite in `tests/test_rag_pipeline.py` to support custom dynamic security groups and pass security filters.

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
