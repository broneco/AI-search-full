# ADR-0013: Hybrid Search Fusion Strategies

- Status: accepted
- Date: 2026-07-16
- Owners: Antigravity (AI Architect), Ondrej Bronec (Lead Developer)
- Supersedes: None
- Superseded by: None

## Context

In our hybrid search implementation, combining results from vector search (semantic, cosine similarity) and lexical FTS (keyword search, Postgres ts_rank) is critical. A single fusion algorithm does not fit all use cases:
* **Reciprocal Rank Fusion (RRF)** is rank-position based and doesn't consider raw score values, which makes it extremely robust but insubstantial for precise score threshold filtering.
* business users sometimes want to sum normalized scores to preserve exact relevance ratios.
* business users want to fetch exactly $N$ vector items and $M$ keyword items, merge them, and present the union to the LLM (Union retrieval).

## Decision

We decide to implement three hybrid fusion strategies, selectable via the admin config:

1. **RRF (Reciprocal Rank Fusion)** (Default):
   Calculates a rank-based score using:
   \[ RRF(d) = w_{vector} \cdot \frac{1}{k_{rrf} + rank_{vector}(d)} + w_{keyword} \cdot \frac{1}{k_{rrf} + rank_{keyword}(d)} \]
2. **Weighted Score Addition**:
   Sums the cosine similarity score with the normalized FTS score. FTS rank values (`ts_rank_cd`) are unbound, so we normalize them dynamically in each query batch:
   \[ Score_{norm}(d) = \frac{fts\_rank(d)}{\max(fts\_ranks)} \]
   \[ CombinedScore(d) = w_{vector} \cdot cosine\_similarity(d) + w_{keyword} \cdot Score_{norm}(d) \]
3. **Union (Concatenation)**:
   Extracts `vector_final_limit` items from vector search and `keyword_final_limit` items from FTS. Concatenates both lists and deduplicates by `chunk_id`.

## Consequences

* **Flexible Fusion**: Support for RRF, Score Addition, and exact Union.
* **Effective Thresholding**: Score Addition produces a bounded score where a threshold filter can be applied to drop weak, irrelevant matches.
* **Low Latency**: Normalization and sum calculations are executed in memory in Python over retrieved DB rows.
