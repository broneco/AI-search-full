# Test Explanation: `test_security_prefilter.py`

This test suite validates our database-level pre-filtering mechanisms (SQL `WHERE` clause filters) and outward token-budget context expansion algorithms. It ensures that security access controls (ACLs) and freshness requirements are applied directly during SQL candidate generation to prevent recall leakage, and that LLM token budget limiters successfully contain context size during retrieval expansion.

---

## Fixtures

### Fixture: `db_setup`
* **Purpose:** Prepares clean PostgreSQL test tables and mock data contexts.
* **Low-Level Details:**
  * Establishes database connection using local SQL engine.
  * Triggers `init_db()` to create the schema.
  * Drops `chunks` and `documents` tables in the `finally` cleanup teardown block.

---

## Individual Tests

### Test 1: `test_sql_acl_prefiltering`

* **High-Level Purpose:**
  We verify that security groups (ACL) are pre-filtered at the database query level (inside SQL select statements) during candidate generation. Users with restricted roles only fetch candidate chunks they have access to, while Management bypasses all restrictions.
* **Low-Level Technical Details:**
  * Seeds 2 documents and matching chunks with distinct ACL `allowed_groups`:
    * *Doc 1:* Allowed groups: `["HR"]`
    * *Doc 2:* Allowed groups: `["IT"]`
  * Instantiates `VectorRetriever`.
  * Runs the retrieval asynchronous method inside an `anyio.run` loop for different contexts:
    * **HR Role:** Queries database with `acl_groups={"HR"}`. Asserts that the SQL filter limits candidates so only the HR document is returned.
    * **IT Role:** Queries database with `acl_groups={"IT"}`. Asserts that only the IT document is returned.
    * **Management Role:** Queries database with `acl_groups={"Management"}`. Asserts that the SQL pre-filter is bypassed and both candidate documents are returned.

---

### Test 2: `test_sql_freshness_prefiltering`

* **High-Level Purpose:**
  We verify that date-based freshness filters (`latest` and `this_year`) are applied directly in SQL query candidate selection.
* **Low-Level Technical Details:**
  * Seeds 2 documents:
    * *Doc 1 (New):* Dated `2026-01-01` with status `current`.
    * *Doc 2 (Old):* Dated `2024-01-01` with status `archived`.
  * Runs retrieval with different freshness filter values:
    * **Latest:** Filters with `freshness_filter = "latest"` and asserts that SQL only returns the `current` document.
    * **This Year:** Filters with `freshness_filter = "this_year"` and asserts that SQL extract filters limit results to year `2026`.
    * **All:** Filters with `freshness_filter = "all"` and asserts that both documents are returned.

---

### Test 3: `test_token_budget_context_expansion`

* **High-Level Purpose:**
  We verify that context expansion (`siblings`) obeys the token budget config limiter (`context_max_tokens`), expanding outward from the hit chunk and stopping once the budget is exhausted.
* **Low-Level Technical Details:**
  * Seeds a single document with 5 sequential chunks (indices 0 to 4), each containing 300 characters (approx. 100 tokens).
  * Executes a lexical search (FTS strategy) query for `"2"` targeting Chunk index 2.
  * Supplies a custom search configuration with `context_max_tokens = 200` (equivalent to a budget of 600 characters).
  * Asserts that:
    * Exactly 1 final retrieval result is returned.
    * The matched Chunk index 2 is included in the expanded content.
    * The total merged character length of the result is within the 600-character budget (meaning the expansion truncated before pulling all 5 chunks, which would be ~1250 characters).
