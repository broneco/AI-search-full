# Hybrid Search & Reciprocal Rank Fusion (RRF) Guide

This guide explains conceptually how the AI Search Application retrieves relevant document passages to answer user queries. It focuses on the business and retrieval logic without detailing the technical database or code implementations.

---

## 1. What is Hybrid Search?

A search system must handle two fundamentally different types of queries:
1. **Exact Matches**: Queries searching for specific words, IDs, product codes, or exact terminology (e.g., "ERP", "GDPR", "Směrnice S-10.150").
2. **Conceptual Questions**: Queries written in natural conversational language that ask about a topic without knowing the exact words used in the documents (e.g., "how do we log working hours" when the document uses "evidence pracovní doby").

To solve this, our system runs two distinct search strategies in parallel and merges their results:

```
                  ┌───────────────────────┐
                  │      User Query       │
                  └──────────┬────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   ┌────────────────────┐        ┌────────────────────┐
   │   Keyword Search   │        │  Semantic Search   │
   │  (Exact Matcher)   │        │ (Concept Matcher)  │
   └──────────┬─────────┘        └──────────┬─────────┘
              │                             │
              │  Ranked List                │  Ranked List
              └──────────────┬──────────────┘
                             ▼
               ┌───────────────────────────┐
               │ Reciprocal Rank Fusion    │
               │ (Weighted RRF Merge Step) │
               └─────────────┬─────────────┘
                             ▼
                  ┌───────────────────────┐
                  │ Unified Top Results   │
                  └───────────────────────┘
```

### Keyword Search (Lexical Matching)
* **How it works**: Scans the text files looking for the exact occurrences of the words in the query.
* **Strengths**: High precision for exact terminology, specific abbreviations, and names.
* **Weaknesses**: Cannot find information if the author used a synonym or a slightly different phrasing (e.g., searching for "contracts" will miss passages mentioning "agreements").

### Semantic Search (Vector Meaning Matching)
* **How it works**: Translates the mathematical "meaning" of the query into a high-dimensional concept space and finds passages whose semantic concepts are closest.
* **Strengths**: High recall. It understands synonyms, context, and intent. It finds answers even when there are zero overlapping words between the query and the document.
* **Weaknesses**: Can occasionally miss specific unique IDs or codes if they are semantically similar to generic terms.

---

## 2. Configurable Hybrid Fusion Strategies

Because Keyword Search and Semantic Search produce entirely different scoring metrics (keyword density rank vs. concept distance scores), their scores cannot be compared directly. It is impossible to say whether a keyword FTS score of `5.4` is better than a semantic similarity score of `0.82`.

To handle this, our system supports three distinct fusion strategies:

### A. Reciprocal Rank Fusion (RRF)
RRF looks only at the **rank (position)** of a document in each search result. It rewards documents that appear near the top of either list, and heavily rewards documents that appear in **both** lists.

$$\text{RRF Score}(d) = W_{\text{vector}} \times \left( \frac{1}{k + \text{Rank}_{\text{vector}}(d)} \right) + W_{\text{keyword}} \times \left( \frac{1}{k + \text{Rank}_{\text{keyword}}(d)} \right)$$

* **$k$ (Smoothing Constant)**: Set to `60` by default. This prevents early ranks (like #1 vs #2) from completely dominating the scores, allowing runner-ups to still be considered.
* **$W_{\text{vector}}$ / $W_{\text{keyword}}$**: Weights (default: `0.6` / `0.4`) representing the relative priority of semantic meaning versus exact word matching.

### B. Weighted Score Addition (Score-Based Fusion)
Instead of discarding raw scores, this strategy sums the exact cosine similarity (vector) score with the normalized FTS score. FTS rank values (`ts_rank_cd`) are unbounded, so they are normalized by dividing by the highest FTS score found in the query's candidate set:

$$\text{Score}_{\text{normalized}}(d) = \frac{\text{FTS Rank}(d)}{\max(\text{FTS Ranks in query batch})}$$
$$\text{Combined Score}(d) = W_{\text{vector}} \times \text{CosineSimilarity}(d) + W_{\text{keyword}} \times \text{Score}_{\text{normalized}}(d)$$

This produces a bounded combined score (typically between `0.0` and `1.0`), allowing the application of a **Score Threshold** to filter out low-relevance results.

### C. Union (Sjednocení TOP výsledků)
This strategy performs independent retrieval. It takes the top $N$ vector results and the top $M$ keyword results, merges them, and removes duplicates based on `chunk_id`. This is highly useful for scenarios where you want a guaranteed mixture of exact-word matches and semantic matches (e.g. exactly 5 of each).

---

## 3. Parent-Child & Context Window Expansion

To solve the RAG trade-off between **precise search vectors** (which work best on small sentences/paragraphs) and **rich context** (needed by the LLM to write complete answers), we implement a dynamic context expansion step:

```
    Database Search                    Context Expansion Step              Sent to LLM
 ┌───────────────────┐                 ┌────────────────────┐          ┌───────────────────┐
 │   Match Chunk i   │  ─────────────> │ Load Sibling Chunks│  ──────> │ Complete Paragraph│
 │ (Sentence level)  │                 │  [i - N, ..., i+N] │          │   or Page / Section│
 └───────────────────┘                 └────────────────────┘          └───────────────────┘
```

1. **Sousední chunky (Siblings)**:
   Fetches neighboring chunks in the range $[i - N, i + N]$ using the sequential `chunk_index`. This expands a single sentence into a full paragraph or surrounding context block.
2. **Celostránkový kontext (Page-level)**:
   Loads all chunks belonging to the same page (`page_number`).
3. **Sekční kontext (Section-level)**:
   Loads all chunks belonging to the same document section (`section_title`).

These expansions are evaluated in real time at retrieval, meaning no data re-indexing is required.

---

## 4. Administrative Configuration Schema

All settings are stored in `search_config.json`, replicated in Azure Blob Storage for resilience, and managed in the admin UI:

| Parameter | Type / Range | Default | Description |
| :--- | :--- | :--- | :--- |
| `search_strategy` | `"hybrid" \| "vector" \| "keyword"` | `"hybrid"` | Primary query route. |
| `hybrid_strategy` | `"rrf" \| "score_addition" \| "union"` | `"rrf"` | Fusion algorithm. |
| `vector_weight` | `0.0` - `1.0` | `0.6` | Semantic retrieval weight. |
| `keyword_weight` | `0.0` - `1.0` | `0.4` | Lexical matching weight. |
| `rrf_k` | `10` - `100` | `60` | Smoothing constant for RRF. |
| `vector_limit` / `keyword_limit` | `5` - `200` | `50` | Row candidates fetched from DB. |
| `final_limit` | `1` - `20` | `5` | Final chunk count sent to LLM. |
| `vector_final_limit` / `keyword_final_limit` | `1` - `20` | `5` | Slice sizes for `Union` strategy. |
| `score_threshold` | `0.0` - `1.0` | `0.0` | Minimum score required (0 = disabled). |
| `freshness_boost` | `0.0` - `0.5` | `0.0` | Score bonus for current year (2026). |
| `context_expansion` | `"none" \| "siblings" \| "page" \| "section"` | `"none"` | Parent-child context mode. |
| `context_expansion_size` | `1` - `3` | `1` | Sibling window size. |

