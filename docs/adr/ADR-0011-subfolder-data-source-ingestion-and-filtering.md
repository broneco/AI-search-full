# ADR-0011: Subfolder Data Source Ingestion and Filtering

- Status: accepted
- Date: 2026-07-09
- Owners: Antigravity (AI Architect), Ondrej Bronec (Lead Developer)
- Supersedes: None
- Superseded by: None

## Context

The local document ingestion pipeline originally assumed all input documents (`.pdf` and `.txt` files) resided directly inside the flat `data/` root directory. Consequently, the document's database `source_uri` was saved as `file://{basename}`, and the filename was used directly as the Azure Blob Storage upload key.

However, corporate document sets are now organized into subfolders (e.g. `data/1. ŘÍDÍCÍ DOKUMENT 0 + TP`, `data/2. METODICKÉ POKYNY`, etc.). This layout introduces two key problems:
1. **Namespace Collisions**: If two different folders contain a file with the same name (e.g. `Traumaplán.pdf`), they will share the same `source_uri` (`file://Traumaplán.pdf`) and Azure Blob key, leading to database uniqueness violations or file overwrites.
2. **Metadata Filtering by Source**: Business users need to filter search queries and documents in the dashboard by their original folder source (the "Zdroj dat" filter).

## Decision

We decide to:
1. **Utilize Relative Paths for source_uri & Blob Storage**: Change the document unique URI resolution in `IngestionPipeline` to use the relative path of the file starting from the `data/` directory (e.g. `file://1. ŘÍDÍCÍ DOKUMENT 0 + TP/Traumaplán.pdf` and `azure://originals/1. ŘÍDÍCÍ DOKUMENT 0 + TP/Traumaplán.pdf`). This isolates namespaced files and prevents any storage conflicts.
2. **Inject source_folder ("Zdroj dat") Metadata**: Calculate the relative path of the containing directory during ingestion and store it under keys `"source_folder"` and `"Zdroj dat"` in the `metadata_json` column of the `documents` and `chunks` tables.
3. **Handle Root Directory Files Gracefully**: If a document lies directly in `data/`, do not write any source folder metadata. The frontend will display these files without folder badges and skip them in directory dropdowns.
4. **Resilient Local PDF Fallback Search**: Implement recursive directory scanning inside the `/view/{document_id}` endpoint. If a file is not found at its direct `source_uri` path, the backend searches for it recursively under the `data/` folder, ensuring the inline viewer works even if files are shifted.
5. **Implement Frontend Dynamic Dropdown & Sidebar Filters**:
   * Gather unique folder paths directly from loaded documents via `useMemo`.
   * Render a styled select dropdown in the collapsible search settings panel.
   * Filter the sidebar document list locally and badge each card with its directory path.
   * Send the selected folder filter in `/api/chat` requests to restrict LLM RAG answers to documents in that folder.

## Options considered

### Option A: Flatten all input files and prefix names (e.g., `folder_subfolder_filename.pdf`)
- *Pros*: Simple filesystem structure.
- *Cons*: Modifies the original filename, making visual display in the UI ugly and breaks standard document titles.

### Option B: Keep original ingestion and only filter on frontend using folders parsed from filename
- *Pros*: Zero database schema changes.
- *Cons*: Does not prevent Blob Storage collision when uploading. Breaks if files are in different subdirectories since the database cannot distinguish between them.

### Option C: Namespace via Relative Paths & Ingest metadata tags (Chosen)
- *Pros*: Complete namespace isolation on database and Blob Storage levels. Extremely clean UI representation. Dynamic and database-driven filters on the backend without requiring a new database schema migration.

## Consequences

- **Collision Prevention**: Different files with identical names can be safely ingested and deployed.
- **Granular Filtering**: Queries can be scoped to a single document folder on both client and retrieval levels.
- **Path Resilience**: Shifting directories locally does not break document views.
