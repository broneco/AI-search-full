# Changelog

All notable project and agent-environment changes must be recorded here.

Format follows the spirit of Keep a Changelog: human-readable, chronological, with an `Unreleased` section.

## [Unreleased]

### Added
- **Subfolder Data Source Ingestion ("Zdroj dat")**: Modified the local ingestion scripts (`ingest.py`, `full_refresh_ingest.py`) and background reindexing endpoint (`/reindex` in `app/api/routes/documents.py`) to recursively scan subdirectories of the `data/` folder and tag all documents and chunks with `source_folder` and `Zdroj dat` metadata properties containing the relative subfolder path.
- **Data Source Filtering (Frontend)**: Added a "Zdroj dat" dropdown selector to the Collapsible Search Settings Panel on the frontend. The dropdown dynamically lists all unique folder paths extracted from the ingested documents list.
- **Active Filters Badge & Local Sidebar Filtering (Frontend)**: Rendered a styled folder badge on each document card in the sidebar showing its directory, and implemented local document filtering by data source. Added an active filter pill at the top of the chat interface showing the active data source constraint.
- **Data Source RAG Filtering (Backend/Frontend)**: Propagated the selected data source filter in search requests to `/api/chat` under the `filters` body payload, which is automatically evaluated by the backend hybrid retriever.
- **Automated Backend Deployment Script**: Created `deploy_backend.ps1` in the workspace root to automate Docker builds via Azure ACR Tasks and rolling-deploy to Azure Container Apps. Documented usage instructions in `README.md`.

### Changed
- **Relative Path source_uri Resolution**: Updated the ingestion pipeline (`IngestionPipeline.ingest_file`) to construct `source_uri` (and Azure Blob storage upload paths) using the document's relative path from the `data/` folder rather than its basename. This avoids namespace conflicts and overwrites for documents of the same name stored in different folders.
- **Robust Local PDF Fallback Search**: Enhanced the PDF viewing route `/view/{document_id}` to recursively search for the file under the `data/` folder if its stored absolute path does not exist, preventing 404 errors when serving files.

### Added
- **Azure Static Web Apps Workflow**: Added `.github/workflows/azure-static-web-apps.yml` to automatically build and deploy the Next.js frontend to Azure Static Web Apps.
- **Complete UI Localization (Frontend)**: Replaced all remaining hardcoded Czech text strings in `frontend/app/page.tsx` with dynamic key lookups from the `TRANSLATIONS` dictionary. This includes localizing the Category Migration Modal, Re-indexing Progress Modal, the initial/greeting assistant message, document list tooltip texts, and the active source section titles when multiple sections are selected.
- **Document Language Detection & Ingestion (Backend)**: Added automated language detection in `MetadataTagger.detect_language` using the Azure OpenAI `flash` profile. Return `"suggested_language"` (`"cs"` or `"en"`) in the metadata suggestion endpoint. Added a `language` parameter to `IngestionPipeline.ingest_file` to write the language to the `DBDocument` and `DBChunk` tables.
- **Localized LLM Grounded Prompts (Backend)**: Added support for translating LLM system prompts and enforcing the correct response language in `/api/chat` based on the requested `locale` (supporting Czech and English).
- **Application Localization Selector (Frontend)**: Implemented a language switcher toggle button (CZ/EN) in the navigation header. Added a `TRANSLATIONS` mapping dictionary to translate all UI labels, button states, placeholders, and sidebar tabs based on `appLanguage`.
- **Document Language Filter & Previews (Frontend & Backend)**: Added a document language filter to restrict searches to Czech, English, or all documents. Extended `VectorRetriever._apply_filters` to check direct database columns (`doc.language`/`chunk.language`) in addition to JSON metadata. Added visual `CZ`/`EN` badges to document cards in the sidebar and filtered the sidebar list dynamically.

### Changed
- **Registry Name Documentation**: Updated the Azure Container Registry name from `dolphinacr` to `dolphinds` and documented the unique login server `dolphinds-b7asdeh8fyayaya2.azurecr.io` in `docs/deployments/cloud_deployment_guide.md` and `.agents/memory/implementation-notes.md` to align with the active cloud topology.
- **App Tab Title Styling**: Renamed the HTML title of the application from the placeholder/default to `"Dolphin AI Search"` to reflect corporate branding.
- **SWA API Endpoint Injection**: Configured SWA build pipelines to inject `NEXT_PUBLIC_API_URL` during the static export compile step, enabling the client to query backend REST endpoints dynamically.
- **Collapsible Search Settings Interface (Frontend)**: Refactored the top search filter bar into a clean, collapsible "Search Settings" drawer. Displays active filter parameters as compact glassmorphic pills with an "Adjust Filters" toggle button.
- **Ingestion & Editing Language Dropdowns (Frontend)**: Integrated a "Document Language" dropdown selector into the confirmation and edit forms. Passes `confirmedLanguage` in confirmed ingestion and update metadata requests.
- **Backward-Compatible API Schemas**: Made `language` in `DocumentUpdateMetadataRequest` default to `"cs"`, preventing validation errors (422 Unprocessable Entity) on existing API test payloads.

### Added
- **Real-Time Re-Indexing Progress Tracking (Backend)**: Added global `reindex_progress` tracking in `app/api/routes/documents.py` to monitor background re-indexing tasks (clearing DB, scanning, metadata analysis, and vector ingestion phases) and exposed it via a new `GET /api/documents/reindex-progress` endpoint.
- **Docker Deployment Configuration**: Created a production `Dockerfile` (using Python 3.12-slim) and a `.dockerignore` file in the root of the project to enable building containerized images of the backend API.
- **Dynamic Glassmorphic Re-Indexing Progress Modal (Frontend)**: Implemented a sleek centered modal in Next.js `page.tsx` that blocks user interaction during re-indexing. It polls the backend progress endpoint every 1 second, displaying Czech translation labels, real-time percentage progress (split 0%-50% for metadata analysis, 50%-100% for ingestion), file names, processing counts, and action buttons.
- **Automated Metadata Tagging System**: Created `app/ingestion/tagger.py` utilizing `gpt-5.4-mini` (flash model) to perform regex-based date candidate extraction, LLM-based release date identification, category classification, and replacement relationship mapping.
- **Dynamic Categories & AI Rules Configuration**: Added `app/core/classification_config.json` defining visual categories, allowed security groups, descriptions, and custom guidelines for document analysis.
- **Dynamic categories API Endpoints**: Created endpoints in `app/api/routes/documents.py` to get/save categories config (`/categories`), analyze uploaded file drafts (`/analyze-draft`), and ingest documents with confirmed metadata and relationship archival updates (`/ingest-confirmed`).
- **Administrative Ingest Dashboard**: Integrated an "Ingest a správa" tab in Next.js `page.tsx` with a categories config editor, a file drag-and-drop zone, an LLM analysis progress loader, and a review form for editing suggested title, date, category, and target replacement documents.
- **Automatic Document Archival**: Implemented automated transition of replaced documents (and their associated chunks) to `freshness_status = "archived"` in PostgreSQL when confirming ingestion of a new version.
- **Cloud Deployment Guide**: Created a comprehensive guide `docs/deployments/cloud_deployment_guide.md` describing standard procedures to publish the application container to Azure Container Apps and configure environment variables.
- **Category Creation & Deletion UI**: Added a dash-bordered button "➕ Přidat novou kategorii" at the bottom of the categories configuration settings tab, and a "🗑️ Odebrat" button at the top-right of each category card, allowing administrators to dynamically append and delete categories in the configuration state before saving.
- **Confidential Document Category Migrations**: Implemented a secure database migration mechanism when categories are deleted. The frontend prompts the administrator to select a replacement category to transfer all existing documents. The backend updates document metadata fields and dynamically re-keys all underlying chunk security ACLs to prevent confidential documents from leaking or becoming public. Added integration test coverage verifying the migration logic.
- **Tagger Test Suite**: Added a test file `tests/test_metadata_tagging.py` to automatically verify date parsing, category classification, and relationship updates.

### Changed
- **Static Next.js Export Configuration**: Configured `frontend/next.config.ts` to output a static export (`output: 'export'`) and disable image optimization (`images: { unoptimized: true }`), preparing the frontend for serverless hosting on Azure Static Web Apps.
- **Configurable Frontend API URL**: Refactored `frontend/app/page.tsx` to read the backend API URL from `process.env.NEXT_PUBLIC_API_URL` (falling back to `http://localhost:8000`), allowing the frontend to target the newly deployed Azure Container App without modifying code.
- **Strict Viewport Scroll Layout**: Set strict viewport height (`h-screen overflow-hidden` on `body`) in `frontend/app/globals.css` and `frontend/app/layout.tsx` to prevent the browser window from scrolling. Only the internal feed, sidebars, and forms now scroll, keeping the header and chat input box fixed.
- **Dynamic Frontend Role Fallback**: Updated the frontend role header generator (`getHeaders`) to automatically extract the specific group from the category's `allowed_groups` (filtering out `"Management"`) if `role_name` is null or empty, preventing permission mismatches.
- **Dynamic LLM Category Mapping**: Refactored the LLM classification prompt and mapping logic in `app/ingestion/tagger.py` to dynamically resolve friendly role names and robustly match LLM responses against category labels and keys case-insensitively.
- **Dynamic Frontend Role Switcher**: Refactored Next.js user role selection dropdown to dynamically read from the categories configuration file, updating permission groups and RAG headers immediately without hardcoding.
- **Dynamic allowed groups Badges**: Updated the citations workspace drawer to render allowed groups dynamically from retrieved chunk metadata instead of hardcoded filename rules.
- **Upload File dependencies**: Added `python-multipart` to `requirements.txt` to support file uploading in FastAPI backend routes.

### Fixed
- **Category Deletion Autosave & List Refreshing**: Fixed a category deletion bug where deleted categories remained in the top-right role selector and document list views until the user manually saved and refreshed. The deletion modal now immediately saves config updates to the database, executes database migrations, and updates the frontend list and selector.
- **Dynamic Tag Input Suggestions**: Refactored the `uniqueGroups` calculation in `frontend/app/page.tsx` to dynamically query and construct the autocomplete suggestions from the active configuration categories and their current role names, preventing hardcoded values (like the renamed 'Finance' role) from showing up.
- **In-Place Ingestion Updates**: Fixed a critical bug in `app/ingestion/pipeline.py` where manual metadata confirmations and reindexing skipped updating the database record when a file's checksum was unchanged. Now, metadata, security ACLs, and freshness statuses are fully updated in both `DBDocument` and `DBChunk` tables.
- **Immediate Allowed Groups Propagation**: Fixed a bug in the categories configuration update route (`app/api/routes/documents.py`) where modifying `allowed_groups` of an existing category did not update existing documents. Now, changes to category groups are immediately propagated to all matching database records.
- **Source URI Match Bug**: Fixed a bug in `app/ingestion/pipeline.py` where the existing document query was hardcoded to `file://` URIs, failing to match existing documents when Azure Blob Storage was configured (which uses `azure://` URIs).
- **Frontend JSX Syntax & TypeScript Type Errors**: Fixed hanging JSX fragment tags and closing brackets left at the bottom of the main dashboard UI (`frontend/app/page.tsx`). Restored the accidentally deleted `BACKEND_URL` API endpoint definition and extended the `IngestedDocument` TypeScript interface to correctly support newly exposed backend fields (such as `security_acl` and `metadata_json`), allowing the Next.js production build to compile successfully.
- **Tagger NoneType AttributeError**: Fixed a crash in `MetadataTagger.classify_category` where checking a category's `role_name` raised a `'NoneType' object has no attribute 'lower'` exception if the category in the configuration file had a null `role_name` property. Implemented robust fallback logic to use the category `key` when `role_name` is absent or null, successfully resolving all failures in the metadata tagging test suites.
- **Role Permissions Leak**: Fixed a visual bug in `frontend/app/page.tsx` where selecting a user role (e.g. HR) sent all of the category's allowed viewing groups (including `Management`) in the `X-User-Groups` header. This bypassed security filters and allowed access to management-only documents. Now only the specific role group key is transmitted.
- **Non-ASCII Filename Headers & ValueError Exception Masking**: Fixed a crash in the PDF viewer endpoint where document titles containing Czech diacritics (like 'Ř', 'í') caused a latin-1 UnicodeEncodeError inside Starlette headers. Due to a broad `except ValueError` catch wrapping the entire route, this encoding error was masked and incorrectly reported as 'Invalid document UUID format'. Localized the UUID parsing exception block and percent-encoded filename parameters using the RFC 5987 standard format.

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
