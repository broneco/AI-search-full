# ADR-0009: Metadata Auto-Tagging and Document Archival System

- Status: proposed
- Date: 2026-06-11
- Owners: Antigravity (AI Architect), Ondrej Bronec (Lead Developer)
- Supersedes: None
- Superseded by: None

## Context

Newly uploaded documents (PDFs and TXT files) require metadata categorization, access permissions (security ACL groups), release dates, and links to older files they modify or replace. 

Relying on manual metadata entry is prone to human error and adds administrative overhead. However, relying purely on static LLM predictions can lead to inaccuracies. Therefore, an automated tagging system with human-in-the-loop review is required.

Additionally, when a new policy replaces an older one (e.g. "Směrnice S-10.150 v2.0 nahrazuje verzi v1.0"), the older document and its chunks must be marked as archived so that searches set to look for "latest only" ignore the archived chunks, while the system retains the ability to browse archival records for historic audits.

Finally, the categories (e.g., HR, Management) and AI analysis rules must be completely dynamic and editable in the system, and changes must reflect immediately across the entire application (both in the UI switcher and in the backend LLM classifier).

## Decision

We decide to:
1. Store categories, display labels, security groups, and AI analysis rules in a configuration file: `app/core/classification_config.json`.
2. Expose `GET` and `POST` API endpoints for `classification_config.json` to allow editing from the UI.
3. Build a two-stage upload pipeline:
   - **Stage 1 (Draft Analysis)**: Upload the file, extract text, scan for date candidates using regex, and send them to the LLM (using the fast `gpt-5.4-mini` model profile) to suggest the title, release date, category, and replacement relationships. Return these values as a draft.
   - **Stage 2 (Confirmed Ingestion)**: Receive the confirmed/corrected metadata from the administrator, move the file through the standard `IngestionPipeline`, and apply archival statuses to replaced documents.
4. Set `freshness_status = "archived"` in both `DBDocument` and `DBChunk` for replaced documents to ensure they are omitted by the existing RAG freshness filters when querying current documents.
5. Store cross-references (`replaces_document_id` / `replaced_by_document_id`) in `metadata_json` to maintain auditability without modifying the database schema.

## Options considered

### Option A: Hardcoded categorization and manual relationship tagging
- *Pros*: Extremely simple database/backend implementation.
- *Cons*: Cannot accommodate dynamic additions (like adding a DevOps category) without editing Python code. Relies on users to manually identify and select replaced files.

### Option B: Fully automated ingestion without user confirmation
- *Pros*: Completely hands-off ingestion.
- *Cons*: LLM mistakes in date extraction or ACL classification would instantly pollute the database and could lead to unauthorized document access or incorrect search grounding.

### Option C: Dynamic Category JSON + Two-Stage Upload & Tagging Pipeline (Chosen)
- *Pros*: Combines automated speed (LLM fills the form) with human control (administrator approves before DB write). Dynamic config file allows immediate updates to frontend UI selectors, backend classification rules, and security ACL mappings without code changes.

## Consequences

- **Dynamic Readjustment**: Adding or renaming categories in `classification_config.json` automatically updates the frontend dropdown selectors, the database ACL security groups mapped during confirmation, and the classification instructions passed to the LLM.
- **Auditing Integrity**: Documents are never hard-deleted during replacements. They are archived by changing `freshness_status` to `"archived"`, maintaining historical retrieval traces.
- **Preserved Highlight Mapping**: By decoupling draft analysis from final ingestion, we ensure the file is chunked and embedded using the standard pipeline, keeping line-highlighting annotations fully functional.
- **Dependency**: The backend must have read/write access to `app/core/classification_config.json`.

## Implementation notes

- Date regex candidates should be fed to the LLM as text snippets containing the line with the date and +/- 3 adjacent lines to provide sufficient reading context.
- Fallback release date order: Text Date -> PDF Metadata Date -> Current Date.
- Archival updates must run in a single transaction during the confirmed ingestion stage.
