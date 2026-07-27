# Project State Memory

Last updated: 2026-07-21

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
Phase 2/3 Multi-lingual Frontend & Document Language Filtering (automatic language detection in tagger, localized RAG prompts, CZ/EN toggle switcher, collapsible filter settings panel, visual badges) - [x] Completed.
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
46: Phase 2/3 Direct Live PDF Right Inspector Panel & Interactive Citation Document Badges (Embedded live PDF page canvas in right panel drawer with dynamic PyMuPDF yellow text highlight overlays, zoom controls, download links, and interactive document badges in AI answer text) - [x] Completed.

Next: Phase 2 Productization (integrating user feedback loop collection, SQL query audit logging, and Microsoft Entra ID authentication skeleton).

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

