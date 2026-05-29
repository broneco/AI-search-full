# Test Explanation: `test_vector_db.py`

This test suite validates the core **Vector Database Retrieval** layers. It ensures that pgvector semantic similarity search executes, that our custom Python-based cosine similarity check is mathematically correct, and that standard metadata filters hide non-matching chunks properly.

---

## Fixtures

### Fixture: `db_setup`
* **Purpose:** Sets up database connections and initializes pgvector tables.
* **Low-Level Details:**
  * Checks database connection status.
  * Calls `init_db()` to register tables.
  * Yields the SQLAlchemy database session (`SessionLocal`) and drops tables inside `finally`.

---

## Individual Tests

### Test: `test_vector_similarity_search`

This single comprehensive integration test covers three distinct vector DB search scenarios:

#### Scenario A: Exact Semantic Similarity Match
* **High-Level Purpose:** We verify that semantic search returns the closest mathematical chunk based on the pgvector cosine distance, and that identical vectors receive a similarity score of exactly `1.0`.
* **Low-Level Technical Details:**
  * Seeds 2 chunks with mock 1536-dimensional vectors:
    * *Chunk 1:* `[1.0] + [0.0]*1535` (Account Based Collaboration topic).
    * *Chunk 2:* `[0.0, 1.0] + [0.0]*1534` (Azure Billing topic).
  * Executes an asynchronous retrieve command `retriever.retrieve` with `query_embedding` identical to *Chunk 1*'s vector.
  * Asserts that:
    * *Chunk 1* is returned first.
    * The calculated cosine similarity score is exactly `1.0` (with float precision bounds `< 1e-5`).
    * The parent document metadata details are mapped correctly in the result.

#### Scenario B: Security ACL Rejection
* **High-Level Purpose:** We verify that semantic matches are rejected and filtered out before returning if the user lacks active group access permissions.
* **Low-Level Technical Details:**
  * Executes a retrieve query with `query_embedding` matching *Chunk 2*'s vector perfectly.
  * Sets the user context groups to `acl_groups=["HR"]` (while *Chunk 2* is restricted to `"Finance"`).
  * Asserts that *Chunk 2* is successfully filtered out and absent from the final results list despite being a perfect semantic match.

#### Scenario C: Standard Metadata Filtering
* **High-Level Purpose:** We verify that additional metadata filter criteria are applied concurrently with semantic search to filter candidates.
* **Low-Level Technical Details:**
  * Executes a retrieve query with `filters={"tags": ["HR", "collaboration"]}`.
  * Asserts that the return list matches *Chunk 1* (whose metadata tags match the filter dictionary), while excluding chunks without matching keys.
