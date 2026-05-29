# Test Explanation: `test_security_freshness.py`

This test suite validates our granular **Security ACLs** and **Freshness Validation** filters. It ensures that sensitive corporate materials (HR files, finance budgets) are hidden from unauthorized roles, and that expired or archived versions are hidden from freshness-filtered searches.

---

## Fixtures

### Fixture: `db_setup`
* **Purpose:** Prepares clean schemas and tables.
* **Low-Level Details:**
  * Connects to local PostgreSQL.
  * Calls `init_db()` to register tables and drops them in the `finally` clean-up block.

---

## Individual Tests

### Test 1: `test_security_roles_authorizations`

* **High-Level Purpose:**
  We verify that search candidates are filtered dynamically based on active user security groups, ensuring standard users cannot access HR or Finance files, while the Management role bypasses all checks.
* **Low-Level Technical Details:**
  * Seeds a parent document and adds 3 chunks with different security group permissions:
    * *Chunk 1:* Restricted to `["Management", "HR"]`.
    * *Chunk 2:* Restricted to `["Management", "Finance"]`.
    * *Chunk 3:* Restricted to `["Management", "HR", "Finance", "User"]` (public/User default).
  * Initializes `VectorRetriever(db)`.
  * **Management Bypass:** Queries with `acl_groups=["Management"]` and asserts `_apply_filters` yields all 3 chunks.
  * **HR Specialist:** Queries with `acl_groups=["HR"]` and asserts it yields 2 chunks (matching HR or User groups), while blocking the Finance chunk.
  * **Finance Auditor:** Queries with `acl_groups=["Finance"]` and asserts it yields 2 chunks (matching Finance or User groups), while blocking the HR chunk.
  * **Standard User:** Queries with `acl_groups=["User"]` and asserts it yields only 1 chunk (the public User chunk), blocking both HR and Finance.

---

### Test 2: `test_freshness_filters`

* **High-Level Purpose:**
  We verify that freshness filters successfully restrict search candidate evaluations based on document creation year and current validity status.
* **Low-Level Technical Details:**
  * Seeds 3 documents representing different timeframes and validity states:
    * *Document A:* Platný/current & dated in 2026 (this year).
    * *Document B:* Archivovaný/archived & dated in 2024.
    * *Document C:* Platný/current & dated in 2025.
  * Adds 1 chunk to each document and initializes `VectorRetriever`.
  * **All Documents (`'all'`):** Queries with `filters={"freshness_filter": "all"}` and asserts it yields all 3 chunks.
  * **Latest Platné (`'latest'`):** Queries with `filters={"freshness_filter": "latest"}` and asserts it yields 2 chunks (Current Document A and Document C), blocking the archived Document B.
  * **This Year (`'this_year'`):** Queries with `filters={"freshness_filter": "this_year"}` and asserts it yields exactly 1 chunk (Document A, dated in 2026), filtering out Document C (2025) and Document B (2024).
