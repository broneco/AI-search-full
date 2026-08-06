# Changelog

All notable project and agent-environment changes must be recorded here.

Format follows the spirit of Keep a Changelog: human-readable, chronological, with an `Unreleased` section.

## [Unreleased]

### Fixed
- **RAG Hybrid Search Quality & Grounded Retrieval Fixes (`app/retrieval/vector.py`, `app/api/routes/chat.py`, `app/core/search_config.json`, `app/core/classification_config.json`)**:
  - Removed query string pollution from prior thread messages (`retrieval_query = request.query`) so new queries are not corrupted by previous chat history.
  - Added text deduplication to `_fuse_rrf` and `_fuse_union` in `VectorRetriever` to prevent duplicate header/footer page chunks from filling retrieval slots.
  - Set default `hybrid_strategy` to `rrf`, `final_limit` to 8, and `score_threshold` to 0.0 in `search_config.json`.
  - Updated `classification_config.json` to assign `User` role access to `HR` category documents (`Pracovní řád`, `Zaměstnanecké výhody`), removing security lockout for non-management users.
  - Aligned prompt citation indexing (`[1]`, `[2]`) and metric instructions (hours/days) for 100% accurate grounded LLM responses.
  - Added flexible base tenant ID matching (`DBDocument.tenant_id.in_([settings.TENANT_ID, tenant_base])`) resolving tenant string mismatch between `"dolphin"` and `"dolphin-prod"`.
- **FastAPI CORS 307 Redirect Fix (`app/api/routes/chat.py`)**: Added `@router.post("")` route decorator alongside `@router.post("/")` to prevent CORS preflight network errors on `/api/chat`.

### Added
- **Tenant-Specific System Prompts & Leadership Personalities (`app/core/prompts.py`, `app/api/routes/chat.py`, `tests/test_tenant_prompts.py`)**:
  - Implemented modular tenant prompt manager supporting isolated system prompts per client tenant (`alzbeta`, `dolphin`, `default`).
  - Integrated key organizational leadership personalities for **Nemocnice sv. Alžběty na Slupi** into the system prompt: Jednatel (RNDr. Karel Matyska, CSc.), Náměstek LPP (MUDr. Ivana Doleželová, MBA) and Náměstek NZOK (Mgr. Marcela Tomanová, MBA, LL.M.).
  - Added unit test suite `tests/test_tenant_prompts.py` verifying prompt isolation, language localization (CS/EN), and leadership identification.
- **Repository Navigation Guide & Maintenance Rule (`docs/navigation_guide.md`, `.agents/AGENTS.md`, `.agents/rules/documentation-policy.md`)**:
  - Created [`docs/navigation_guide.md`](file:///c:/Users/ondrej.bronec/OneDrive%20-%20dolphinconsulting.cz/Documents/Projekty/WIP%20-%20AI%20Search%20Full/docs/navigation_guide.md) documenting 100% of all 350 files and directories in the repository with a concise 1-sentence Czech description for each element.
  - Enforced a binding rule in `.agents/AGENTS.md` (Definition of Done) and `.agents/rules/documentation-policy.md` requiring AI agents to update `docs/navigation_guide.md` whenever any file or directory is created, moved, or deleted anywhere in the repository.
- **UI Branding & Layout Refinements (`frontend-user/app/page.tsx`, `frontend-user/app/components/ThreadSidebar.tsx`, `frontend-user/app/translations.ts`, `frontend-admin/app/page.tsx`)**: Removed header theme dropdown switcher to enforce build-time brand isolation, replaced dolphin emoji (`🐬`) in the sidebar header `AI Search Console` with brand-neutral sparkle icon (`✨`), and made initial AI welcome greeting text generic and brand-appropriate across all client environments.
- **Automated Azure Cloud Deployment (`deploy_backend.ps1`, `deploy_frontend.ps1`)**: Provisioned and deployed **3 Azure Static Web Apps** (`swa-dolphin-dev`, `swa-dolphin-prod`, `swa-alzbeta-prod`) and **4 Azure Container App Backends** (`dolphin-ai-search-backend-dev`, `dolphin-ai-search-backend-prod`, `alzbeta-ai-search-backend-dev`, `alzbeta-ai-search-backend-prod`). Configured automatic Azure ACR image compilation, dynamic deployment tokens, automated Container App revision updates, CORS configuration, and theme binding.
- **Multi-Client White-Label Branding System (`frontend-user/app/config/themes.ts`, `frontend-admin/app/config/themes.ts`, `public/logos/`)**: Created a dynamic client branding engine for both `frontend-user` and `frontend-admin`. Includes brand profiles and logo assets for **Nemocnice sv. Alžběty** (`logo-nemocnice-alzbeta-2023.png`, warm gold header `#a38244`, leaf green accent `#00965e`) and **Dolphin Consulting** (`logo-dolphin-symbol.png`, cyan/blue gradient). Features dynamic CSS variable injection, `NEXT_PUBLIC_CLIENT_THEME` environment support, and an interactive theme switcher dropdown in the header of both applications.
- **Enterprise Client Infrastructure Provisioning via Azure Bicep (`infra/main.bicep`, `infra/modules/`, `infra/deploy_infra.ps1`)**: Created modular Infrastructure-as-Code (IaC) Bicep templates for provisioning dedicated client Azure environments. Includes **ON/OFF resource toggles** (`provisionPostgres`, `provisionOpenAI`, `provisionStorage`, `provisionACR`, `provisionFrontends`) allowing enterprise clients to either create dedicated Azure resources from scratch or seamlessly reuse existing Azure PostgreSQL, OpenAI, or Storage resources.
- **Multi-Environment DEV & PROD Architecture (`app/core/config.py`, `.env.dev`, `.env.prod`, `deploy_backend.ps1`, `deploy_frontend.ps1`)**: Established full logical isolation between **DEV** and **PROD** environments. Configured dynamic `.env.dev` and `.env.prod` loading based on `APP_ENV`, isolated database targets (`ai_search_dev` vs `ai_search_prod`), isolated Azure Blob Storage containers (`dolphin-originals-dev` vs `dolphin-originals`), and parameterized Azure deployment scripts (`deploy_backend.ps1 -Client <client> -Environment <dev|prod>`).
- **PDF Drawer Toolbar UX Enhancements (`frontend-user/app/page.tsx`, `frontend-user/app/components/PdfViewerModal.tsx`, `frontend-admin/app/page.tsx`)**: Replaced `PyMuPDF Highlight` badge with human-readable label `✨ Zvýrazněná pasáž` (`✨ Highlighted Passage`), updated download button to an "Open in new window" button with icon `↗️` and tooltip `Otevřít na nové záložce`, and fixed drawer close button (`✕`) by resetting both `workspaceOpen` and `activeSource` state to properly unmount the panel.
- **Expandable Document Library Sidebar (`frontend-user/app/components/ThreadSidebar.tsx`, `frontend-user/app/page.tsx`)**: Added a dynamic tab switcher (`💬 Konverzace` | `📁 Dokumenty`) into the left sidebar of `frontend-user`. Features real-time document search filtering, category tags (`SOP`, `DPL`, `SM Z`), status badges (`PLATNÝ` / `ARCHIV`), passage counts, and one-click preview that immediately loads the target document into the live PDF drawer.
- **Rich Markdown AI Response Rendering (`frontend-user/app/page.tsx`, `frontend-admin/app/page.tsx`)**: Implemented a zero-dependency `renderFormattedMarkdown` renderer that formats AI chat outputs into crisp bold white badges (`**text**`), italics (`*text*`), and indented bullet lists (`- item`), while preserving all interactive inline citation badges (`📄 [1]`, `📄 [2]`).
- **Search & Chunking Configuration API Endpoints (`app/api/routes/chat.py`)**: Registered `GET /api/chat/config` and `POST /api/chat/config` backend endpoints using `SearchConfigManager`. Updated `frontend-admin` calls (`fetchSearchConfig`, `saveSearchConfigToServer`, `fetchPreview`) to include `Authorization: Bearer ${authToken}` headers via `getHeaders()`, fully restoring the **Konfigurace vyhledávání** and **Chunkování** admin tabs.
- **Interactive Inline Citation Badges (`frontend-admin/app/page.tsx`)**: Updated `renderMessageContent` regex in `frontend-admin` from `(\[Source \d+\])` to `/(\[(?:Source\s*)?\d+\])/gi`, matching `frontend-user`. Transforms inline text citations like `[1]`, `[2]`, `[1][2]` into clickable badges `📄 [1]` and appends the bottom citation source list with instant document preview drawer links.
- **Isolated Temp Directory Blob Cache (`app/api/routes/documents.py`)**: Moved PDF blob cache directory from `data/.blob_cache/` to OS temp directory (`tempfile.gettempdir()/dolphin_blob_cache`). Prevents `uvicorn` / `watchfiles` from detecting file changes inside project workspace and triggering mid-flight server reloads during PDF document requests.
- **Stable Webpack Dev Server Configuration (`frontend-admin/package.json`, `frontend-user/package.json`)**: Updated `"dev"` script to `"next dev --webpack"` to eliminate Turbopack panics on Windows after directory renames.
- **Frontend Admin Console Renaming (`frontend-admin/`)**: Renamed the original administrative frontend workspace from `frontend/` to `frontend-admin/` and updated title to **Administrativní Konzole AI Search** (`TRANSLATIONS.cs.title`).
- **Admin Console Authentication Integration (`frontend-admin/app/components/AuthModal.tsx`)**: Integrated `AuthModal` dialog, JWT token state, user profile badge, and logout capability into `frontend-admin`. Updated `getHeaders()` to inject `Authorization: Bearer ${authToken}` headers into all administrative API calls (`/api/chat`, `/api/documents/list`, `/api/documents/categories`, `/api/chat/config`, `/api/documents/preview-chunks`, etc.), resolving all 401 Unauthorized errors.
- **Automatic Question Thread Titling (`app/api/routes/chat.py`)**: Updated chat interaction logic so that when a user asks their first question, the thread title is automatically set to the exact question asked by the user (truncated to 50 characters).
- **Mandatory Login Enforcement (`frontend-user/`, `/api/chat`, `/api/threads`)**: Enforced strict authentication across the application. Unauthenticated users are blocked by an automatically opened `AuthModal` dialog on mount or when submitting queries, and API endpoints enforce `401 Unauthorized` without a valid token.
- **Server-Side Azure Blob Storage PDF Cache (`app/api/routes/documents.py`)**: Added an automatic disk-caching layer (`data/.blob_cache/{doc_id}.pdf`) for PDF documents fetched from Azure Blob Storage (`azure://`). On first view, PDF bytes are downloaded from Azure Blob Storage and saved to local server cache; all subsequent citation views are served instantly in ~1ms from local server cache without extra cloud roundtrips.
- **Multi-Tenant Data Isolation (`TENANT_ID="dolphin"`)**: Added `TENANT_ID` configuration setting (`app/core/config.py`) and indexed `tenant_id` columns across `users`, `chat_threads`, `chat_messages`, `documents`, and `chunks` PostgreSQL tables. Scoped all database queries, vector retrieval, and authentication lookups by tenant ID to guarantee 100% data privacy when multiple client deployments share a single PostgreSQL database server.
- **Lightweight Database Authentication & User Management (`/api/auth`)**: Built database-backed user authentication with `DBUser` PostgreSQL model, password hashing, and token authentication (`POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me`). Includes auto-seeded demo user (`user@dolphin.cz` / `password123`) for 1-click testing.
- **Chat Thread History & Multi-Turn Context (`/api/threads`)**: Built chat thread CRUD endpoints (`POST /api/threads`, `GET /api/threads`, `GET /api/threads/{id}`, `PATCH /api/threads/{id}`, `DELETE /api/threads/{id}`) with `DBChatThread` and `DBChatMessage` models. Updated `POST /api/chat` to include prior message turns in Azure OpenAI prompt context for conversational memory.
- **Collapsible Chat History Left Sidebar (`ThreadSidebar.tsx`) & Glassmorphic Login (`AuthModal.tsx`)**: Built Perplexity/ChatGPT style collapsible left sidebar in `frontend-user` with `+ Nový chat` button, thread title editing/deletion, date grouping, user profile badge, and logout. Added `AuthModal` dialog with 1-click Demo Login.
- **Direct Live Formatted PDF Page Inspector Panel (`frontend-user/`)**: Re-engineered the right Citation Panel in `frontend-user/` to directly embed a live, fully formatted PDF page canvas (`<iframe>`) positioned at the exact cited page (`#page=N`) with dynamic PyMuPDF yellow text highlight overlays (`highlight_chunk_id`). Includes zoom controls (`🔍 -` / `🔍 +`), pop-out full screen modal toggle (`⛶`), and direct download links.
- **Interactive In-Text Citation Document Badges**: Updated LLM system prompt instructions in `chat.py` and frontend regex parser in `frontend-user/app/page.tsx` to render inline citations as interactive document badges: `📄 [1] SM Z č. 4... (Strana 2)`. Clicking any inline citation instantly opens/updates the right live PDF panel.
- **Dedicated End-User Search Application (`frontend-user/`)**: Created an isolated, ultra-sleek end-user facing web application in `frontend-user/` with its own Next.js setup, dark glassmorphic UI, language switcher (CZ/EN), and ACL security role selector. Removed all admin tabs, sliders, and document catalog list to focus 100% on search and citation verification.
- **Embedded Fully Formatted PDF Viewer Modal (`PdfViewerModal.tsx`)**: Built a glassmorphic PDF viewer modal inside `frontend-user/` that renders original PDF documents with exact typography, vector graphics, logos, and dynamic PyMuPDF yellow text highlight overlays on cited passages (`GET /api/documents/view/{document_id}?highlight_chunk_id={chunk_id}#page={page}`). Includes zoom controls, page navigation, and download links.
- **Universal AI Summary Enrichment Toggle (`enrich_with_summary`)**: Decoupled AI summary generation from chunking strategy selection. Made AI summary prepending an optional universal toggle (`✨ Generovat AI shrnutí pasáží`) with custom instruction text prompt (`summary_custom_prompt`) available across ALL strategies (Standard, Semantic, Structure, Token, Agentic).
- **True Agentic LLM Boundary Splitting**: Re-engineered the Agentic strategy (`chunking_strategy = "agentic"`) to perform true LLM-driven text boundary splitting. The LLM receives text batches bounded by `max_context_chars` and splits the text into discrete chunks separated by custom delimiters (`===CHUNK_BREAK===`) based on custom user splitting rules (`agentic_params.custom_prompt`).
- **Deferred Live Preview AI Calls**: Prevented automatic debounced live preview slider drags from executing expensive Azure OpenAI LLM/Embedding API calls. Added real-time notification warning banner and `force_ai` flag connected to the `🔄 Znovu vygenerovat` (Regenerate) button.
- **Decoupled Localization and Tooltips**: Created separate translation file `frontend/app/translations.ts` containing all copy strings and nested strategy tooltips, reducing `frontend/app/page.tsx` size by 400+ lines and separating content from JSX markup.
- **Advanced Chunking Strategy Engines**: Added complete backend splitting support for Semantic Chunking (topic shifts via sentence embeddings cosine similarity), Structure-Aware (preserving markdown headers and block hierarchies), Token-Based (splitting by tiktoken token count), and Agentic (LLM-driven summaries prepend prefix).
- **Dynamic Strategies Config UI Panel**: Built dynamic parameter form input fields in the Next.js chunking tab that show or hide inputs based on the selected strategy. Added help icon widgets rendering hover tooltips bound to translated strings.
- **Dynamic Simulation Support**: Updated `/api/documents/preview-chunks` to dynamically apply semantic thresholds, token boundaries, and agentic summaries in real-time.
- **Testing Coverage**: Updated `tests/test_rechunk.py` to cover all 4 strategies (Token, Structure, Agentic, and Semantic) with mock embedding calculations, passing 4/4 backend tests successfully.
- **Advanced Chunking Strategy & Splitter Type Configuration**: Added controls to select between `"recursive"` (separators list) and `"character"` (fixed size) splitters. Added support for `"chunk_cross_page"` enabling continuous text chunks to cross page transitions while maintaining offset-based page citation mapping.
- **Visual Overlap Highlights**: Built client-side character overlap suffix-to-prefix matching in the Next.js interactive preview tab, rendering overlapping text chunks with an amber-dotted border and hover tooltip description.
- **Visual Raw PDF Formatting Warning**: Rendered a card banner explaining why PDF styling (fonts, alignments, columns) is stripped during raw plain-text parsing.
- **Original Document Page Viewer Links**: Added target-blank anchor links to chunk cards in the interactive simulation and static DB chunk modal, opening streamed PDFs positioned precisely at the specific page (`#page=N`).
- **Interactive Chunking Preview**: Added a `POST /api/documents/preview-chunks` simulation endpoint on the backend and integrated a side-by-side Live Preview panel in the Next.js frontend. Admins can select any document from a dropdown list, adjust sliders/inputs, and instantly audit how the text splits into color-coded segments in real time.
- **Dedicated Chunking Page & Tab switcher**: Segmented document chunking parameters (chunk size, overlap) from the Search Settings tab into a dedicated "🧩 Chunkování" (Czech) / "🧩 Chunking" (English) tab panel.
- **Fast Chunk-level Re-indexing**: Added a fast background re-indexing endpoint (`POST /api/documents/reindex-all` running `run_reindex_all_task`) which regenerates chunks and vector embeddings using PyPDF and Azure OpenAI without modifying LLM metadata tags.
- **Full Metadata-tagging Re-indexing**: Renamed the slow re-indexing task to `run_reindex_full_task` (exposed under `POST /api/documents/reindex-full`) to allow full metadata classification and relationship mapping.
- **Dynamic Re-indexing Progress Modal**: Localized progress states using "Reindexace" (Re-indexing) / "Reindexovat" (Re-index) instead of "Přechunkování" (Re-chunking) in Czech. Customized the progress descriptions dynamically based on whether the fast or full re-indexing was triggered.
- **Reindexing Test Coverage**: Created `tests/test_rechunk.py` and explanation document `docs/tests_explained/test_rechunk.md` verifying chunk size adjustments, database commits, Azure OpenAI vector updates, and simulated text-splitting API previews.
- **Visual Document Chunking Preview Modal**: Added `GET /api/documents/{document_id}/chunks` on the backend and integrated a dynamic, pastel-colored chunking preview modal in the Documents tab on the Next.js frontend, letting admins inspect exact text segmentations.
- **SQL Pre-filtering for ACL & Freshness**: Shifted security ACL group checks and time validity filters from post-retrieval Python loops directly into database queries using PostgreSQL JSONB query operators (`?|`) and datetime extracts. This resolves potential recall leaks and optimizes performance.
- **Outward Token-Budget Context Expansion**: Implemented a dynamic context expansion algorithm that alternates left-and-right sibling additions from the matched chunk up to a user-defined token limit.
- **Dual Slider and Number Input Controls**: Added manual numeric input boxes alongside all sliders on the search configuration page for precise tuning, and expanded the context token limit range up to 30,000.
- **Recursive character chunking**: Updated `app/ingestion/chunking.py` and `app/ingestion/pipeline.py` to use `RecursiveCharacterTextSplitter` configured dynamically from active search settings.
- **Security Prefilter Test Suite**: Created `tests/test_security_prefilter.py` and explanation document `docs/tests_explained/test_security_prefilter.md` verifying SQL filters and token budget limits.

### Added
- **Customizable Search Config REST API**: Exposed `GET /api/chat/config` and `POST /api/chat/config` endpoints to read and write Pydantic-validated search parameters.
- **Dynamic Retrieval Config Manager (`SearchConfigManager`)**: Replicated `search_config.json` locally and synced it to Azure Blob Storage container (`originals`) under key `config/search_config.json` for persistent, zero-downtime search configuration tuning.
- **Flexible Hybrid Fusion Strategies**: Extended `VectorRetriever` to support three fusion strategies:
  * **Weighted RRF (Reciprocal Rank Fusion)**: Rank-position based merging.
  * **Weighted Score Addition**: Normalized FTS rank scores combined with cosine similarity values, allowing score thresholding.
  * **Union**: Concatenated exact slices of top vector and FTS results with deduplication.
- **Parent-Child & Context Window Expansion**: Added dynamic context window expansions at retrieval time:
  * **Siblings**: Loads preceding/succeeding chunks based on `chunk_index`.
  * **Page-level**: Loads all chunks belonging to the same `page_number`.
  * **Section-level**: Loads all chunks belonging to the same `section_title`.
- **Admin Search Configuration Panel (Frontend)**: Added a dynamic, grid-based search configuration form inside the **Nastavení (Config)** tab next to dynamic categories. Localized form inputs in Czech and English.
- **Search Config Test Suite**: Created `tests/test_search_config.py` verifying validation rules, score addition normalization, union combining, and context window expansions. Added documentation in `docs/tests_explained/test_search_config.md`.
- **Architectural Decision Records (ADRs)**: Created `ADR-0012` (Dynamic Search Config), `ADR-0013` (Hybrid Fusion Strategies), and `ADR-0014` (Context Expansion Strategies) to document design decisions.

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
