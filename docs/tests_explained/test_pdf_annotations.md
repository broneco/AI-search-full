# Test Explanation: `test_pdf_annotations.py`

This test suite verifies the dynamic backend PDF highlighting capabilities of the document serving endpoint (`GET /api/documents/view/{document_id}`). It ensures that if a RAG chunk ID is provided, the backend successfully uses PyMuPDF to locate the text inside the PDF file, apply transparent yellow highlights, and serve the annotated PDF stream.

---

## Individual Tests

### Test 1: `test_view_document_with_highlights`

* **High-Level Purpose:**
  We verify that the backend's document viewing endpoint successfully parses `highlight_chunk_id`, retrieves the targeted text chunk from the database, opens the source PDF using PyMuPDF, searches for the chunk text coordinates, draws a highlight annotation, and returns the modified PDF stream.
* **Low-Level Technical Details:**
  * **PDF Setup Fixture:**
    * Checks if the test database connection is functional (skips otherwise).
    * Initializes the isolated test database schema (`init_db()`).
    * Programmatically compiles a valid, searchable 1-page PDF document containing a specific Czech test phrase using the **`PyMuPDF`** (`fitz`) library, and writes it to the local `data/test_highlight.pdf` sandbox directory.
    * Closes the document and yields the database session.
    * **Teardown:** Cleans up the mock PDF file from the disk and drops all database tables inside `ai_search_test` to keep the testing environment clean.
  * **Test Execution Flow:**
    * Ingests a mock `DBDocument` record pointing to the newly compiled local PDF.
    * Ingests a child `DBChunk` record containing the exact text embedded in the PDF on page 1.
    * Triggers a synchronous `GET` request to `/api/documents/view/{document_id}` passing the query parameter `highlight_chunk_id={chunk_id}` using FastAPI's `TestClient`.
    * Asserts that the response code is `200 OK` and the `Content-Type` header is exactly `"application/pdf"`.
    * Loads the returned byte stream response content into PyMuPDF (`fitz.open(stream=response.content, filetype="pdf")`).
    * Asserts that the document contains exactly 1 page.
    * Extracts all annotations from page 1 (`page.annots()`) and asserts that at least one annotation is present.
    * Inspects the annotation type and asserts that it is exactly type `8` (the standard PDF Highlight annotation type).
    * Closes the document safely.
