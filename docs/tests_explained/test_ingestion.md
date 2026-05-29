# Test Explanation: `test_ingestion.py`

This test suite validates the **PDF Ingestion Pipeline**. It ensures that the document scanning, text extraction, paragraph splitting, embedding generation, and bulk database persistence blocks operate correctly.

---

## Fixtures

### Fixture: `db_setup`
* **Purpose:** Initialises tables and returns a Session.
* **Low-Level Details:**
  * Validates database availability.
  * Calls `init_db()` to create required SQL tables.
  * Yields a local SQLAlchemy session (`SessionLocal`).
  * In the clean-up phase, drops all tables.

---

## Individual Tests

### Test 1: `test_pdf_extraction_and_chunking`

* **High-Level Purpose:**
  We verify that individual sub-components of our ingestion process (directory scanning, page extraction, and text chunking) function as expected.
* **Low-Level Technical Details:**
  * **File Scan:** Creates a temporary `.txt` file containing multi-paragraph strings inside the system's temporary directory (`tmp_path`) and verifies `list_local_files` discovers it correctly.
  * **Text Extraction:** Feeds the path to `DocumentExtractor` and asserts that it extracts exactly 1 page and parses the content accurately.
  * **Text Chunking:** Feeds the extracted text page to `CharacterTextSplitter` with explicit parameters (`chunk_size=100`, `chunk_overlap=20`). Asserts that the text is split into at least 2 overlapping chunks, and that chunk indices and page numbers are incremented correctly.

---

### Test 2: `test_pipeline_ingestion`

* **High-Level Purpose:**
  We verify the end-to-end ingestion flow of `IngestionPipeline`, ensuring that documents are processed, embedded via OpenAI, uploaded to storage (Azure Blob or local fallback), and written to PostgreSQL.
* **Low-Level Technical Details:**
  * Skips execution if active Azure OpenAI endpoints and API keys are not set in `.env`.
  * Creates a dummy text file.
  * Launches `IngestionPipeline` and calls its asynchronous method `pipeline.ingest_file(...)` wrapped inside an `anyio` async runner block.
  * Checks that the document is successfully uploaded to Azure Storage (setting `doc.source_type == "azure_blob"`) or falls back safely to local sandbox path logging (`doc.source_type == "local"`), depending on env configurations.
  * Runs a database `select` query on `DBChunk` using SQLAlchemy Core to assert that parent-child database relationships are created successfully and chunk text content matches the source string.
