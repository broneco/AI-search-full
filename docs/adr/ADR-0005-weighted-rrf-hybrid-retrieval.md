# ADR-0003: Weighted Reciprocal Rank Fusion (Weighted RRF) Hybrid Retrieval

- Status: accepted
- Date: 2026-05-29
- Owners: USER, Antigravity Agent
- Supersedes: None
- Superseded by: None

## Context

To achieve high RAG groundedness, our retrieval layer must retrieve highly relevant document fragments. 
1. **Semantic Search (pgvector):** Captures concepts, synonyms, and intent (e.g. finding "holidays" when searching for "leave") but is weak at exact match queries.
2. **Lexical Search (PostgreSQL Full-Text Search):** Excel at finding exact matches for specific codes (e.g., contract numbers like `"R_399"`), unique acronyms (e.g., `"ZF"`, `"ISRS"`), or specific names (e.g., `"Michal Berec"`, `"Emanuel Krejcar"`), where vector search may fail.

We need a mathematically sound, robust, and performant method to fuse results from both search paths into a single ranked list for LLM context packing.

## Decision

We decide to:
1. Implement a **Weighted Reciprocal Rank Fusion (RRF)** scoring algorithm in `app/retrieval/vector.py` combining vector results and FTS keyword search results.
2. Configure RRF using the following weighted rank formula:
   $$RRF\_Score(d) = w_{vector} \cdot \frac{1}{60 + r_{vector}(d)} + w_{keyword} \cdot \frac{1}{60 + r_{keyword}(d)}$$
3. Store the weighting coefficients `RRF_WEIGHT_VECTOR` and `RRF_WEIGHT_KEYWORD` in the `.env` configuration file, defaulting to `0.6` and `0.4` respectively to prioritize conceptual vector matching while maintaining high exact-match lexical influence.
4. Establish PostgreSQL GIN indices on `DBChunk.content` using the Czech language configuration (`'cs'`) where supported to enable stemming and stop-word filtering for Czech queries.

## Options considered

### Option A: Weighted RRF (Chosen)
- **Pros**:
  - Does not rely on absolute score scaling (which are completely different and incompatible for Cosine similarity and BM25 log frequencies).
  - Highly robust and mathematically proven to yield superior hybrid retrieval relevance.
  - Weights can be configured and tuned externally in `.env` without modifying the core query parser code.
- **Cons**:
  - Executes two database queries (one vector similarity, one FTS) in parallel or sequence, slightly increasing database query footprint.

### Option B: Raw Score Normalization & Summation
- **Pros**:
  - Intuitively simple.
- **Cons**:
  - Normalizing cosine scores and FTS frequency weights dynamically is extremely unstable and prone to extreme scale distortions (e.g. a long text query can inflate FTS scores enormously, completely drowning out vector matches).

### Option C: Single-Path Retrieval (Vector-Only or Keyword-Only)
- **Pros**:
  - Simple, single-query architecture.
- **Cons**:
  - Lacks exact-match relevance (Vector-only) or conceptual semantic matching (Keyword-only), violating product requirements.

## Consequences

### Positive:
- Significantly improves RAG answer accuracy and groundedness for technical, administrative, and numeric exact-keyword queries.
- Developers can tune the hybrid performance dynamically in `.env` by adjusting the weight coefficients (e.g., changing to vector-only by setting FTS weight to `0.0`, or keyword-only by setting Vector weight to `0.0`).
- Seamlessly integrates with security ACL checks and metadata filters across both retrieval paths.

### Negative / trade-offs:
- Requires setting up GIN indices and keeping the PostgreSQL text index schema synchronized with chunk content updates.

## Implementation notes

* Hybrid searches will be triggered in the `/api/chat` router via a configurable `search_strategy` option.
* Database full-text query parsing will utilize `websearch_to_tsquery` to allow users to input normal text phrases without requiring strict Boolean notation.
* Standard smoothing constant $k$ will be set to `60` in compliance with standard information retrieval benchmarks.

## Follow-ups

- [ ] Add GIN index initialization logic in `app/storage/db.py`.
- [ ] Implement `to_tsvector` and `websearch_to_tsquery` keyword search queries in `app/retrieval/vector.py`.
- [ ] Implement the Weighted RRF fusion sorting loop.
- [ ] Implement integration tests in `tests/test_hybrid_retrieval.py`.
