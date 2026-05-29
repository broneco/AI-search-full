# Test Explanation: `test_rag_pipeline.py`

This test suite validates the **End-to-End Grounded RAG Chat Pipeline**. It ensures that the entire system—from ingesting a raw PDF, generating vector embeddings, executing hybrid retrieval with SSO security headers, to packing LLM contexts and generating answers with inline citation badges—operates correctly.

---

## Fixtures

### Fixture: `rag_setup`
* **Purpose:** Sets up tables and validates Azure AI credentials.
* **Low-Level Details:**
  * Checks database connectivity.
  * Skips tests if Azure OpenAI endpoint or API keys are missing in `.env`, ensuring local setups without model deployments fail gracefully.
  * Calls `init_db()` to register tables and drops them in the `finally` block for isolation.

---

## Individual Tests

### Test 1: `test_end_to_end_rag_flow`

* **High-Level Purpose:**
  We verify the full lifecycle of a RAG query. We ingest a highly specific document, run a query matching its topic, and assert that the generated AI response is mathematically grounded in the document and contains correct source citations.
* **Low-Level Technical Details:**
  * **Step A: Ingestion:** Sends an HTTP `POST` request to `/api/documents/ingest` using FastAPI `TestClient` with a payload representing a secure firewall protocol document. Asserts that the response is `200 OK` and returns the generated UUID `document_id`.
  * **Step B: Query Execution:** Sends an HTTP `POST` request to `/api/chat` with a query matching the firewall topic. The request includes custom SSO headers (`headers={"X-User-Groups": "Engineering"}`) matching the document's allowed security groups, validating authorization boundaries.
  * **Step C: Groundedness & Citation Checks:** Decodes the JSON response and asserts that:
    * An `"answer"` string is generated and contains substantial characters.
    * The `"sources"` list contains at least 1 grounded citation pointing to `"Corporate Firewall Protocols"`.
    * Retrieval metadata indicates the `vector_pgvector` search strategy was used and registers `latency_ms`.
