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
