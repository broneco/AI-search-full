# ADR-0014: Context Expansion Strategies

- Status: accepted
- Date: 2026-07-16
- Owners: Antigravity (AI Architect), Ondrej Bronec (Lead Developer)
- Supersedes: None
- Superseded by: None

## Context

In retrieval-augmented generation (RAG), vector searches perform best on small, granular chunks (e.g. 50-150 words) because they preserve semantic density. However, sending small chunks to the LLM can starve it of surrounding context (e.g. preceding explanations, full page context, or chapter header scopes).

We need a Parent-Child style retrieval mechanism to match on child chunks but feed larger parent structures to the LLM.

## Decision

We decide to implement a dynamic retrieval-time **Context Expansion** system with three expansion modes:

1. **Siblings (Sousedé)**:
   Loads neighboring chunks from the same document in the index range \([i - N, i + N]\) based on the sequential `chunk_index` column.
2. **Page-level (Celá stránka)**:
   Loads all chunks sharing the same `document_id` and `page_number` as the matched chunk.
3. **Section-level (Celá sekce)**:
   Loads all chunks sharing the same `document_id` and `section_title`.

This expansion is resolved dynamically inside `VectorRetriever._expand_context` after fusion/filtering, querying Postgres quickly by indexes.

## Consequences

* **Retroactive Compatibility**: No database changes or ingestion modifications are required. All existing 100+ documents in the DB automatically support context expansion.
* **Precision + Breadth**: We keep semantic vectors dense and precise, but send rich paragraphs, full pages, or entire sections to the LLM.
* **Overlapping Deduplication**: If neighboring chunks overlap, they are merged sequentially based on their `chunk_index`.
