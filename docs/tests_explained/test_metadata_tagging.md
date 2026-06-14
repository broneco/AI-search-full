# Test Explanation: `test_metadata_tagging.py`

This test suite validates the **Automated Metadata Tagging and Archival System**. It ensures that the regex date candidate scanning, LLM-based release date parsing, category classification, dynamic configuration, and database archival updates of replaced documents function correctly.

---

## Fixtures

### Fixture: `db_setup`
* **Purpose:** Initialises tables and returns a Session.
* **Low-Level Details:**
  * Runs `init_db()` to build database tables.
  * Yields a local SQLAlchemy session (`SessionLocal`).
  * In the clean-up teardown phase, drops the database tables.

---

## Individual Tests

### Test 1: `test_scan_date_candidates`
* **High-Level Purpose:**
  We verify that the regular expression scanner in `MetadataTagger` successfully locates candidate dates within a raw text document.
* **Low-Level Technical Details:**
  * Feeds a multi-line string containing both standard Czech dates (`15. 10. 2026`) and ISO dates (`2026-11-01`) to `tagger.scan_date_candidates(...)`.
  * Asserts that it successfully extracts lines and paragraphs matching these formats.

---

### Test 2: `test_tagger_classification_and_date`
* **High-Level Purpose:**
  We verify that the individual LLM parsing methods of `MetadataTagger` successfully determine the release date, category, and relationships from text.
* **Low-Level Technical Details:**
  * Mocks the `AzureOpenAIProvider.generate` method using `unittest.mock.patch`.
  * Simulates consecutive LLM answers returning a date string, a category key, and a relationship JSON object.
  * Verifies that the tagger resolves dates, matches categories against config, and parses relationship payloads.

---

### Test 3: `test_categories_api_endpoints`
* **High-Level Purpose:**
  We verify that the categories configurations can be fetched and updated via the FastAPI API routes.
* **Low-Level Technical Details:**
  * Performs a `GET` request on `/api/documents/categories` and asserts it returns the configured category profiles.
  * Performs a `POST` request on `/api/documents/categories` to overwrite rules, checking that the modifications are saved on disk.
  * Restores original configurations upon test completion.

---

### Test 4: `test_analyze_draft_api_endpoint`
* **High-Level Purpose:**
  We verify that uploading a file to `/api/documents/analyze-draft` extracts pages, runs LLM analysis, saves the file in temporary workspace storage, and returns metadata recommendations.
* **Low-Level Technical Details:**
  * Mocks page-by-page text extraction (`DocumentExtractor.extract`) and LLM generation (`AzureOpenAIProvider.generate`).
  * Uploads a dummy PDF file using the FastAPI `TestClient`.
  * Asserts the response status code is `200` and checks that the suggested title, date, category, and temp file path are returned.
  * Cleans up the temporary file from the workspace.

---

### Test 5: `test_ingest_confirmed_with_archival`
* **High-Level Purpose:**
  We verify the final confirmed ingestion flow, checking that the standard chunking and embeddings pipeline runs, the new file is stored, and the replaced old document (along with all its chunks) is set to `archived` status in the database.
* **Low-Level Technical Details:**
  * Mocks the Azure OpenAI embedding provider to return a constant mock vector.
  * Pre-populates the database with an active document and chunk representing version 1 (`freshness_status = "current"`).
  * Submits a `POST` request to `/api/documents/ingest-confirmed` containing confirmed metadata and a reference to replace the existing document's ID.
  * Asserts that the old document and its child chunks are updated to `freshness_status = "archived"` in PostgreSQL.
  * Asserts that the new document is created with `freshness_status = "current"` and includes cross-references (`replaces_document_id` and `replaces_document_title`) in its metadata.
  * Asserts that the new document's allowed security groups match the dynamic permissions assigned to the category in the configuration file.

---

### Test 6: `test_category_migration_api_endpoint`
* **High-Level Purpose:**
  We verify that deleting a category triggers an automatic secure migration, shifting all existing documents and their chunks to the selected replacement category and updating their security ACLs to prevent leaks.
* **Low-Level Technical Details:**
  * Seeds a mock document and chunk in the database associated with a category key `DELETED_CAT_UUID` and allowed groups `SecretGroup`.
  * Sends a `POST` request to `/api/documents/categories` to save a new configuration with `category_migrations` mapping `DELETED_CAT_UUID` to `REPLACEMENT_CAT_UUID` (which has allowed groups `ReplacementGroup`).
  * Asserts that the database updates the document's metadata department key and resets the document's and its chunks' `security_acl` allowed groups to `ReplacementGroup` immediately.
  * Cleans up database records and restores the original categories configuration.

---

### Test 7: `test_ingest_confirmed_updates_existing_doc`
* **High-Level Purpose:**
  We verify that when confirming manual ingestion of a document that already exists in the database (same checksum), the system correctly updates its metadata, category, and security ACLs in-place rather than skipping without making database changes.
* **Low-Level Technical Details:**
  * Ingests a mock document with category `"HR"` and allowed groups `["Management", "HR"]`.
  * Triggers a second manual upload confirmation `/api/documents/ingest-confirmed` using the same file content (matching checksum) but selecting `"Management"` category.
  * Asserts that the database successfully finds the duplicate checksum record, overwrites the category to `"Management"`, updates its `security_acl` to `["Management"]`, and flags both attributes as modified to force SQLAlchemy JSONB change tracking persistence.
  * Cleans up the database records.

---

### Test 8: `test_category_allowed_groups_propagation`
* **High-Level Purpose:**
  We verify that modifying the allowed groups list of an existing category dynamically propagates those changes to all documents and chunks associated with that category in the database.
* **Low-Level Technical Details:**
  * Seeds a document and chunk associated with category `"HR"` and original allowed groups `["Management", "HR"]`.
  * Deep-copies the active configuration, appends a new group (`"SpecialGroup"`) to `"HR"`'s allowed groups list, and posts the updated config.
  * Asserts that the database automatically identifies all matching records and updates the document and chunk `security_acl` allowed groups to `["Management", "HR", "SpecialGroup"]` immediately.
  * Cleans up database records and restores the original configuration from the deep-copied backup.
