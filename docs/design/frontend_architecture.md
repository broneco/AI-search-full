# Dual-Frontend Architecture & User Interface Design

The Dolphin AI Search Platform features a **Dual-Frontend Architecture** separating end-user search workflows from system administration workflows.

---

## 1. Frontend Workspace Structure

```
WIP - AI Search Full/
├── frontend-user/       # Dedicated End-User Search Application
│   ├── app/
│   │   ├── components/
│   │   │   ├── AuthModal.tsx        # Glassmorphic Login/Registration Dialog
│   │   │   ├── PdfViewerModal.tsx   # Full-screen PDF Document Viewer
│   │   │   └── ThreadSidebar.tsx    # Collapsible History & Document Library Sidebar
│   │   └── page.tsx                 # Main Conversational Search Interface & PDF Drawer
│   └── package.json
└── frontend-admin/      # Administrative Management Console
    ├── app/
    │   ├── components/
    │   │   └── AuthModal.tsx        # Admin Authentication Dialog
    │   └── page.tsx                 # Admin Console (Tabs: Search, Ingest, Categories, Config, Chunking)
    └── package.json
```

---

## 2. End-User Application (`frontend-user`)

The end-user application is tailored for fast, intuitive knowledge lookup with citation verification.

### Core Features

1. **Collapsible Left Sidebar (`ThreadSidebar.tsx`)**:
   - **💬 Konverzace**: Conversation history management (auto-titling, rename, delete).
   - **📁 Dokumenty**: Expandable Document Library listing all accessible company documents with live search filter, category badges (`SOP`, `DPL`, `SM Z`), status badges (`PLATNÝ` / `ARCHIV`), chunk counts, and one-click preview.

2. **Rich Markdown AI Responses (`renderFormattedMarkdown`)**:
   - Parses raw Markdown syntax into crisp bold white badges (`**text**`), italics (`*text*`), and indented bullet lists (`- item`).
   - Seamlessly integrates interactive yellow-highlighting citation buttons (`📄 [1]`, `📄 [2]`).

3. **Inline PDF Drawer & Inspector**:
   - Right-side slide-over panel displaying the exact page of cited PDF documents.
   - Applies AI yellow passage highlight overlays (`✨ Zvýrazněná pasáž`).
   - Header controls for Zoom in/out, Open in new tab (`↗️`), Full-screen expansion (`⛶`), and Close (`✕`).

---

## 3. Administrative Console (`frontend-admin`)

The admin console provides complete operational control over search and chunking parameters.

### Admin Tabs

1. **🔍 Vyhledávání**: Live chat testing with hybrid ranking score breakdowns.
2. **📥 Nahrávání**: File dropzone for PDF ingestion, background processing modal, and document deletion.
3. **🏷️ Kategórie**: Metadata auto-tagging rules, category creation, replacement relationships, and document archival.
4. **⚙️ Konfigurace vyhledávání**: Live control of search strategies (*Hybrid RRF, Vector, Keyword FTS*), fusion weights, score thresholds, and context expansion (*Siblings, Page, Section*).
5. **🧩 Chunkování**: Live side-by-side preview of document chunking strategies (*Standard Recursive, Semantic, Structure-based, Token-based, Agentic*) with real-time chunk size and overlap sliders.
