# Project State Memory

Last updated: 2026-10-12
31: Multi-Tenant Tenant Isolation & Search Quality Tuning (Multi-tenant JWT token authorization, admin user group resolution, RRF search tuning, score threshold tuning) - [x] Completed.
32: 3-Tier Resource Group Architecture & Azure SQL DTU Model (`ai-search-rg-dev`, `ai-search-rg-prod`, `ai-search-showcase-rg-dev`, DTU Basic/Standard mode, v0.1.1 versioning, CORS regex fix, `.env.showcase`) - [x] Completed.
33: Unified Tenant Directory & File-Level Fallback System (`tenants/` root directory, `tenants/default/` fallback tenant, `TenantConfigResolver` in `app/core/tenant_config.py`, `.agents/rules/tenant-configuration-policy.md`, ADR-0018) - [x] Completed.
34: Full-Refresh Production Document Ingestion for Tenant JHU (`full_refresh_ingest.py`, `scratch/run_jhu_prod_ingest.ps1`, 430 JHU documents ingested into Azure SQL DB `ju-ai-search-sqldb-prod` and Blob Storage `ju-originals-prod`) - [x] Completed.
35: Azure Blob Storage Connection Fix for Document View Preview (`ju-ai-search-ca-prod`, `deploy_backend.ps1`, `ju-ai-search-kv-prod`, resolved 404 in PDF preview panel) - [x] Completed.

## Product summary

Full-stack AI Search Application for company knowledge and documents.

The system should provide a web UI and backend API for hybrid search over documents, combining vector similarity, full-text search, metadata filters, freshness validation, ACL filtering, and LLM-generated answers with citations.

## Current phase

Phase 2: Productization & Visual Interface.

Primary goal: establish unified RAG retrieval dashboards, audit search actions, and ready the application for secure corporate pilot users.

## Current recommended slice

Build the smallest backend skeleton - [x] Completed.
Local PostgreSQL / pgvector proof spike - [x] Completed.
Phase 0 RAG Proof of Concept - [x] Completed.
Phase 1 Local PDF Ingestion & Chunking pipeline - [x] Completed.
Visual Progress Reporting & Timeout Safety - [x] Completed.
Phase 1 Hybrid Retrieval & RRF (PostgreSQL full-text search index, weighted Reciprocal Rank Fusion, latency subquery loops optimization) - [x] Completed.
Phase 2 Next.js Dashboard Client (conversational chat workspace, inline citations trigger, right-side metadata drawer, live database statistics sidebar, health checks) - [x] Completed.
Phase 2/3 Productization (Granular Security ACLs, Dynamic Freshness Filters, Blob Storage client, inline streamed PDF viewer, target="_blank" direct document links, and dynamic page-scrolling PDF links) - [x] Completed.
Phase 2/3 Productization (resilient dynamic PDF highlight annotations via character-mapping sliding-window matching and line-by-line merging) - [x] Completed.
Transition to Dolphin Consulting (universal product branding, parallel database setup, and new corporate document ingestion) - [x] Completed.
Phase 2/3 Metadata Auto-Tagging & dynamic category administration panel (drag-and-drop analysis, release date parsing, replacement relationships, archival updates, custom rules configuration editor) - [x] Completed.
Phase 2/3 Cloud Deployment Guide (Azure Container Apps packaging and publishing guide) - [x] Completed.
Phase 2/3 Universal category IDs, persistent blob configuration, background reindexing trigger and UI refinements - [x] Completed.
Phase 2/3 Label consistency, manual ingestion updates, and strict viewport scrolling layout - [x] Completed.
Phase 2/3 Dynamic category tag suggestions, automatic deletion save and list refreshing - [x] Completed.
Phase 2/3 Real-time re-indexing progress bar (backend global state tracking, progress polling endpoint, frontend glassmorphic progress modal with per-file updates) - [x] Completed.
35: Phase 2/3 Multi-lingual Frontend & Document Language Filtering (automatic language detection in tagger, localized RAG prompts, CZ/EN toggle switcher, collapsible filter settings panel, visual badges) - [x] Completed.
36: Phase 2/3 Multi-Client Cloud Infrastructure & Production RAG Quality Fixes (4x Container App backends, 3x Static Web Apps, automated PowerShell deployment, white-label branding, deduplicated RRF hybrid retrieval, unpolluted query search, and grounded citation alignment) - [x] Completed.
37: Phase 2/3 Repository Navigation Guide & Mandatory Maintenance Rule (docs/navigation_guide.md cataloging 100% of 350 files and folders, .agents/AGENTS.md & .agents/rules/documentation-policy.md rule enforcement) - [x] Completed.
Phase 2/3 Subfolder Ingestion & Data Source UI Filtering ("Zdroj dat" metadata tagging, relative source_uri computation to prevent file conflicts, dynamic folder selector dropdown, local sidebar filtering) - [x] Completed.
Phase 2/3 Customizable Search Settings & Context Expansion (RRF/Score Addition/Union strategies, Azure Blob replicated JSON config, siblings/page/section context window expansion, admin UI settings manager, test suite) - [x] Completed.
Phase 2/3 SQL Pre-filtering, Token-budget Expansion & Visual Chunking Preview (PostgreSQL JSONB operators, outward token-budget sibling expansion, epsilon divisor calibration, dual settings sliders/inputs, Next.js chunk preview modal, test suite) - [x] Completed.
Phase 2/3 Separation of Ingestion Chunking Settings Page & Fast database re-indexing task (Dedicated Chunking tab, fast background re-chunking/re-embedding without LLM tagging, full metadata-analysis reindexing fallback, custom progress modal styling, pytest test coverage) - [x] Completed.
Phase 2/3 Interactive Live Chunking Preview (POST /preview-chunks simulator, dropdown document selector, debounced UI, color-coded segment indicators, and TestClient API test cases) - [x] Completed.
Phase 2/3 Dynamic Chunking strategies, Overlap Visualizations, and PDF page viewer links (Recursive vs Character splitter settings, chunk_cross_page continuous boundary combination with offset-based page mapping, visual overlap dotted highlighter, raw PDF format description card, and original streamed PDF anchor links) - [x] Completed.
Phase 2/3 Advanced Chunking strategies & localized tooltips decoupling (Semantic sentence embeddings similarity splitting, Structure-aware Markdown parsing, Token-based Tiktoken splitting, Agentic LLM-summary chunk prefixes, decoupled translations.ts localized dictionary, conditional settings panel layout, and pytest test suite) - [x] Completed.
43: Phase 2/3 Pure Overlap Elimination, Cross-page Overlap toggle & Agentic LLM Execution (Eliminated 100% duplicate overlap chunks, added overlap_cross_page setting, executed custom prompts with AzureOpenAIProvider, added tooltips and pytest coverage) - [x] Completed.
44: Phase 2/3 Universal AI Summary Enrichment, True Agentic LLM Boundary Splitting & Deferred Preview Calls (Decoupled AI summaries into universal toggle for all strategies, implemented true LLM delimiter splitting with max_context_chars batching, deferred preview AI API calls to 'Znovu vygenerovat' button with warning banner) - [x] Completed.
45: Phase 2/3 Dedicated End-User Search Application & Embedded Formatted PDF Viewer (Created frontend-user Next.js application, glassmorphic search UI without admin controls, CZ/EN dictionary, ACL role switcher, and PdfViewerModal with dynamic PyMuPDF yellow text highlight overlays) - [x] Completed.
46: Phase 2/3 Multi-Tenant Azure SQL User Seeding & Document List/Chat Security ACL Fixes (JWT token group extraction, email fallback resolution, multi-tenant seeding for all 6 Azure SQL DB tenants) - [x] Completed.
46: Phase 2/3 Direct Live PDF Right Inspector Panel & Interactive Citation Document Badges (Embedded live PDF page canvas in right panel drawer with dynamic PyMuPDF yellow text highlight overlays, zoom controls, download links, and interactive document badges in AI answer text) - [x] Completed.
47: Phase 2/3 Multi-Tenant Data Isolation, Lightweight DB Auth & Saved Chat Threads History (Indexed tenant_id='dolphin' across PostgreSQL tables, DBUser JWT auth, DBChatThread/DBChatMessage CRUD, multi-turn LLM context assembly, collapsible left history sidebar ThreadSidebar.tsx, AuthModal.tsx, and pytest test suite) - [x] Completed.
48: Phase 2/3 Multi-Environment DEV & PROD Architecture Split (Dynamic .env.dev and .env.prod resolution in app/core/config.py, isolated database targets, isolated Azure Blob Storage containers, frontend env files, parameterized deploy_backend.ps1 and deploy_frontend.ps1 scripts, pytest test suite) - [x] Completed.
49: Phase 2/3 Azure Bicep Enterprise Infrastructure Provisioning (Modular infra/main.bicep, modules for PostgreSQL/pgvector, Azure OpenAI, Storage, ACR, Container Apps, Static Web Apps, ON/OFF resource toggles, and infra/deploy_infra.ps1 script) - [x] Completed.
50: Phase 2/3 Multi-Client White-Label Branding & Theme Engine (Organized public/logos/ directory, brand profiles for Nemocnice sv. Alžběty & Dolphin Consulting, warm gold header #a38244, medical green accent #00965e, dynamic CSS variables, theme switcher dropdown in frontend-user & frontend-admin) - [x] Completed.
51: Phase 2/3 Live Multi-Environment Azure Cloud Deployment (Deployed 3 Azure Static Web Apps: swa-dolphin-dev, swa-dolphin-prod, swa-alzbeta-prod; and 4 Azure Container App Backends: dolphin-dev, dolphin-prod, alzbeta-dev, alzbeta-prod with isolated PostgreSQL databases and Blob Storage containers) - [x] Completed.
52: Phase 2/3 Architectural Migration to Azure SQL Database (Microsoft SQL Server) (pyodbc connection engine, universal Uuid/JSON/UniversalVector models, T-SQL FTS catalog & vector distance fusion, Docker msodbcsql18 image update, ADR-0016) - [x] Completed.
53: Phase 2/3 Three-Tier Resource Group Architecture & Azure SQL DTU Model (Configured Dev ai-search-rg-dev, Prod ai-search-rg-prod, Showcase ai-search-showcase-rg-dev isolation, transitioned to Azure SQL DTU purchasing model, created azuresql.bicep, updated deployment scripts, created ADR-0017 and 2026-09-02-azure-resource-deployment-handoff.md) - [x] Completed.
54: Phase 2/3 Unified Tenant Infrastructure Configuration & Version v0.1.2 (`tenants/<tenant>/.env.<env>` explicit `AZURE_RESOURCE_GROUP`, `AZURE_CONTAINER_REGISTRY`, `AZURE_CONTAINER_APP_NAME`, updated `deploy_backend.ps1` and `deploy_frontend.ps1`, `app/core/config.py`, ADR-0018, pytest suite) - [x] Completed.
55: Phase 2/3 Azure Key Vault Secret Management & JHU PROD Container App Live Deployment (Dynamic Key Vault fetching in `app/core/config.py`, updated `deploy_backend.ps1` with Windows Unicode cp1250 fix `--no-logs`, provisioningState wait loops, ACR `adminUserEnabled: true`, deployed `ju-ai-search-ca-prod` with System-Assigned Managed Identity `ccacbf26-dcd6-4f7b-af7b-e3e769137de8`, created `.agents/inbox/2026-10-07-jhu-keyvault-rbac-handoff.md`) - [x] Completed.
55: Phase 2/3 Azure Key Vault Secret Management & Showcase Tenant Onboarding (`app/core/config.py`, `deploy_backend.ps1`, `tenants/showcase/` configuration files, 100% 38-key tenant `.env` structural parity, `tests/test_keyvault_config.py`, `.agents/inbox/2026-10-06-showcase-keyvault-deployment-handoff.md`) - [x] Completed.
56: Phase 2/3 Dynamic Multi-Tenant Frontend Branding & JCU Login Fixes (`tenants/*/branding.json`, `frontend-admin/`, `frontend-user/`, `AuthModal.tsx`, `page.tsx`, `test_tenant_config.py`) - [x] Completed.

Next: Human operator provisions `showcase-ai-search-kv-dev` Azure Key Vault using handoff file and runs deployment via `.\deploy_backend.ps1 -Client showcase -Environment dev`.

## Target roadmap

1. Phase 0: Technical spike
   - FastAPI skeleton
   - PostgreSQL/pgvector proof
   - one document embedded
   - vector query
   - simple model answer
   - minimal web UI or API-only demo

2. Phase 1: Ingestion and retrieval
   - Blob Storage integration
   - document extraction
   - chunking
   - embeddings
   - PostgreSQL full-text search
   - hybrid ranking
   - metadata filtering
   - eval dataset

3. Phase 2: Agent and productization
   - flash agent
   - thinking agent
   - source citations
   - freshness validation
   - feedback
   - audit
   - frontend
   - Entra ID auth

4. Phase 3: Enterprise hardening
   - ACL filtering
   - production monitoring
   - rate limiting
   - cost tracking
   - ingestion worker scaling
   - reindexing
   - admin endpoints
   - security review

5. Phase 4: Channel expansion
   - Teams interface
   - Outlook interface
   - API for internal systems
   - optional specialized search backend

## Active architectural constraints

- Azure-first.
- Microsoft Azure is the only accepted strategic vendor lock-in.
- Backend primary language: Python 3.11+.
- Backend framework: FastAPI.
- MVP data/search layer: Azure Database for PostgreSQL Flexible Server + pgvector + PostgreSQL full-text search.
- Azure AI Search is not part of MVP.
- Chroma may be used only for local experiments, not production.
- LangChain/LangGraph may be used inside orchestration/providers but must not leak through the whole domain model.
- LLM provider, embedding provider, and search backend must be replaceable through project interfaces.
- Model deployment names must be configuration, not code.

## Current known blockers

- First document sources are not yet chosen.
- Expected document/chunk volume is unknown.
- ACL mapping from source systems is not yet designed.
- Exact Azure model deployments are not known.
- Pilot environment is not chosen.

## Next slice recommendation

Implement Phase 2 Productization: User feedback loop collection database schemas/API, SQL query audit logging, and Microsoft Entra ID authentication skeleton.

