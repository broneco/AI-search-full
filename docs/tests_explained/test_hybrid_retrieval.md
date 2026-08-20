# Test Explanation: `test_hybrid_retrieval.py`

This test suite validates our custom **Hybrid Retrieval** search engine. It ensures that the lexical Full-Text Search (FTS) index retrieves documents with Czech diacritics, and that the Reciprocal Rank Fusion (RRF) algorithm scores and merges candidate lists correctly.

---

## Fixtures

### Fixture: `db_setup`
* **Purpose:** Sets up a clean testing database environment.
* **Low-Level Details:**
  * Checks connection availability and skips tests if local PostgreSQL is offline.
  * Calls `init_db()` to register database tables and build GIN indexes.
  * Yields a local SQLAlchemy database session (`SessionLocal`).
  * In the `finally` block, drops the `chunks` and `documents` tables to ensure absolute cleanup isolation.

---

## Individual Tests

### Test 1: `test_hybrid_and_lexical_fts_retrieval`

* **High-Level Purpose:**
  We verify that the database GIN text search index retrieves Czech document segments matching exact keyword queries, and that the database correctly parses Czech diacritics using FTS search configurations.
* **Low-Level Technical Details:**
  * Seed a dummy `DBDocument` and two `DBChunk` records containing distinct Czech words (*"Evidence pracovní doby"*, *"Péče o pokusná zvířata"*).
  * Constructs a `QueryContext` querying for the Czech keyword *"vedení"*.
  * Executes keyword candidate search via `retriever._get_fts_candidates()` to confirm:
    * The retrieval engine matches chunks containing exact and stem keywords across PostgreSQL (to_tsvector) and Azure SQL Database (T-SQL search).
    * The system falls back cleanly to `'simple'` text configuration if the Czech `'cs'` language configuration is not installed in host database catalogs, preventing transaction crashes.
  * Asserts that at least 1 matching chunk is returned and contains the target search term.

---

### Test 2: `test_weighted_rrf_scoring`

* **High-Level Purpose:**
  We verify the mathematical correctness of our rank-based Reciprocal Rank Fusion (RRF) algorithm, ensuring that chunks matching both vector semantic search and FTS keyword search are ranked highest.
* **Low-Level Technical Details:**
  * Subclasses `VectorRetriever` as a dummy mock class to test its internal `_fuse_rrf` rank fusion method directly.
  * Mocks two input search lists:
    * `res_vec` (vector candidates containing *chunk_A* and *chunk_B*).
    * `res_kw` (keyword FTS candidates containing *chunk_B* and *chunk_C*).
  * Executes the RRF scoring method `retriever._fuse_rrf(res_vec, res_kw, limit=3)` using settings-defined weights (e.g. 60% Vector, 40% FTS).
  * Asserts that the fused output ranks *chunk_B* first. Because *chunk_B* matches both semantic and lexical criteria, its accumulated rank reciprocal score ($W_{vec} \times \frac{1}{60 + Rank_{vec}} + W_{kw} \times \frac{1}{60 + Rank_{kw}}$) ranks it higher than chunks matching only one list.
  * Asserts that RRF metadata variables (`rrf_score`, `vector_score`) are populated in the chunk metadata correctly for auditing.
