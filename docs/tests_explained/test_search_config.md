# Test Explanation: `test_search_config.py`

This test suite validates our dynamic **Search Retrieval Settings** and **Context Expansion** strategies. It ensures that inputs are strictly validated, fusion algorithms produce mathematically correct outputs, and text chunk scopes are expanded sequentially or contextually.

---

## Fixtures

### Fixture: `db_setup`
* **Purpose:** Sets up a clean isolated database testing environment for context expansion.
* **Low-Level Details:**
  * Checks connection availability and skips tests if local PostgreSQL is offline.
  * Calls `init_db()` to register database tables.
  * Yields a local SQLAlchemy database session (`SessionLocal`).
  * In the `finally` block, drops the `chunks` and `documents` tables to ensure absolute cleanup isolation.

---

## Individual Tests

### Test 1: `test_search_config_validation`
* **High-Level Purpose:** Verifies that search parameters follow Pydantic schema validation rules.
* **Low-Level Technical Details:**
  * instantiates `SearchConfigSchema` with valid bounds (e.g. weights `0.7` and `0.3`, window size `2`, strategy `"hybrid"`) and asserts that the object compiles and fields match.
  * Asserts that `pytest.raises(ValueError)` is triggered when values exceed constraints (e.g. invalid strategy name, weights $> 1.0$, or context expansion size $> 3$).

### Test 2: `test_score_addition_fusion`
* **High-Level Purpose:** Validates the Weighted Score Addition algorithm by normalizing FTS scores before summing.
* **Low-Level Technical Details:**
  * Mocks vector matches (`c1`, `c2`) and keyword matches (`c2`, `c3` with FTS ranks `0.5`, `0.25`).
  * Executes the `VectorRetriever._fuse_score_addition` helper method with weights `0.6` (vector) and `0.4` (keyword).
  * Verifies normalization logic: divides FTS ranks by the maximum rank (`0.5`), scaling `c2`'s FTS rank to `1.0` and `c3`'s to `0.5`.
  * Checks final computed scores:
    * `c2` (vector + keyword): $0.6 \times 0.6 + 0.4 \times 1.0 = 0.76$ (Rank 1).
    * `c1` (only vector): $0.6 \times 0.8 = 0.48$ (Rank 2).
    * `c3` (only keyword): $0.4 \times 0.5 = 0.20$ (Rank 3).
  * Asserts correct ordering and score accuracy.

### Test 3: `test_union_fusion`
* **High-Level Purpose:** Verifies that the Union fusion strategy concatenates exact slices of vector and FTS lists without duplicating elements.
* **Low-Level Technical Details:**
  * Seeds vector and keyword results with overlaps (`c2` appears in both).
  * Calls `_fuse_union` with `vector_final_limit=1` and `keyword_final_limit=2`.
  * Verifies that the output contains `c1` (top vector result) and `c2`, `c3` (top keyword results), while deduplicating the second occurrence of `c2`.

### Test 4: `test_context_expansion_siblings`
* **High-Level Purpose:** Validates siblings context window expansion (Small-to-Large chunk retrieval).
* **Low-Level Technical Details:**
  * Seeds three sequential chunks (`chunk_index` `0`, `1`, `2`) belonging to the same document in the database.
  * Passes the matched chunk `1` to `VectorRetriever._expand_context` with mode `"siblings"` and size `1`.
  * Queries database and asserts that chunk contents are concatenated in chronological order into: `"Prvni odstavec.\nDruhy odstavec.\nTreti odstavec."`.

### Test 5: `test_context_expansion_page_and_section`
* **High-Level Purpose:** Validates page-level and section-level context retrieval expansions.
* **Low-Level Technical Details:**
  * Seeds chunks containing page number `5` and section title `"Kapitola 1"`.
  * Matcher retrieves chunk `10` and calls `_expand_context` under `"page"` and `"section"` modes.
  * Asserts that all chunks from page `5` / section `"Kapitola 1"` are concatenated sequentially.
