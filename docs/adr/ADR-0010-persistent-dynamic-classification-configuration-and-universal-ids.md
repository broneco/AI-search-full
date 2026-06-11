# ADR-0010: Persistent Dynamic Classification Configuration and Universal IDs

- Status: accepted
- Date: 2026-06-11
- Owners: Antigravity (AI Architect), Ondrej Bronec (Lead Developer)
- Supersedes: None
- Superseded by: None

## Context

The document classification categories and AI analysis rules were previously stored in a local JSON file (`app/core/classification_config.json`) and identified by human-readable keys like `HR`, `Management`, `Finance`, `User`.

However, this setup has several drawbacks:
1. **Dynamic Category Decoupling**: If category keys are readable names, renaming a category (e.g. from `HR` to `DevOps`) changes the key. This breaks references on all previously ingested documents (which store the key in their metadata) and requires data migrations.
2. **Cloud Longevity**: Local file storage is ephemeral in cloud environments like Azure Container Apps. The configuration gets lost when container replicas recycle or scale down. To survive container lifecycles, configuration must be stored persistently, e.g. in Azure Blob Storage.
3. **Configuration Isolation**: Editing categories and AI rules is an administrative task and should be isolated from document ingestion on the frontend, using a dedicated configuration page.

## Decision

We decide to:
1. **Adopt Universal category IDs**: Category keys will be standard UUID strings (e.g. `3f6b7c5e-8e9d-4c3a-8b2f-7a1b3c5e7d9f`), fully decoupling the category's unique identifier from its display label.
2. **Add Mapped Role Names**: Introduce a `role_name` field for each category to map the category to its primary security group / Entra ID role (e.g. `Management`, `HR`, `Finance`, `User`), ensuring the backend permissions checking logic remains clean and robust.
3. **Store Dynamic Configuration in Azure Blob Storage**: Move config loading/saving to async methods in `MetadataTagger` and load `config/classification_config.json` dynamically from the Blob Storage originals container if configured, falling back to local files.
4. **Isolate configuration UI and prompt reindexing**: Separate configuration into a third tab `Nastavení (Config)` and display a confirmation prompt upon saving to clear the database and run a full re-indexing of all documents.

## Options considered

### Option A: Store category configuration only in PostgreSQL database
- *Pros*: Natural place for dynamic entities, transactional safety.
- *Cons*: Adds database dependency to simple tagger utility scripts and CLI commands that might run offline or prior to full schema setup.

### Option B: Keep local configuration file but map UUIDs in Python
- *Pros*: Keep local disk speed.
- *Cons*: Configuration is lost on Container App restarts and does not synchronize across multiple running container scale replicas.

### Option C: Azure Blob Storage + Local Disk Sync & Fallback (Chosen)
- *Pros*: Persistence across Container App replica lifecycles. Keeps a local file copy as fallback to ensure offline/local developer workflows and pytest suites continue running cleanly without connection exceptions.

## Consequences

- **Persistence**: Configuration changes will persist across ACA container recycles.
- **Reference Integrity**: Modifying a category's display name or AI rules will not break existing document relations, as they remain bound to the category's UUID key.
- **Background Tasks**: Reindexing all documents can take time depending on the file count, and is therefore offloaded to a FastAPI background task to prevent frontend timeouts.
- **Role Mapping**: The frontend will map the category selection to `activeCat.role_name` when sending headers, maintaining compatibility with Entra ID.

## Implementation notes

- The `X-User-Groups` header will carry the role name (e.g., `Management`), not the UUID, so standard backend RAG ACL checking continues to work out of the box.
- The reindexing background task must use a context-managed `SessionLocal` to ensure db connections are properly disposed.
