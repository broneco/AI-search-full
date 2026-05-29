# ADR-0004: Custom SQL/SQLAlchemy Hybrid Retrieval vs. LangChain Components

- Status: accepted
- Date: 2026-05-29
- Owners: USER, Antigravity Agent
- Supersedes: None
- Superseded by: None

## Context

To support Phase 1 Hybrid Retrieval, we must implement a dual-path search (pgvector semantic similarity + FTS lexical keyword search) fused via Weighted Reciprocal Rank Fusion (Weighted RRF).
Crucially, the retrieval service must:
1. Respect security ACL filters (checking if a user's permission groups overlap with a document's `security_acl` array/JSONB values).
2. Support custom metadata filters dynamically.
3. Map results directly to our declarative SQL database schema (`DBDocument` and `DBChunk` tables).

We need to decide whether to leverage LangChain's built-in retrieval and vector storage components (such as `PGVector` vector store, `BM25Retriever`, and `EnsembleRetriever`) or build a custom database-retrieval layer using native SQL / SQLAlchemy.

## Decision

We decide to:
1. Build a custom retrieval service inside `app/retrieval/vector.py` using native SQLAlchemy queries and SQL compilation.
2. Bypass LangChain's `PGVector` storage and `EnsembleRetriever` components entirely within the database and retrieval layers.
3. Restrict the usage of **LangChain and LangGraph exclusively to high-level agentic orchestration** (such as managing dialog states, prompt chains, and thinking-mode reasoning loops in later phases).

## Options considered

### Option A: Custom SQL / SQLAlchemy Retrieval (Chosen)
- **Pros**:
  - **Schema Autonomy:** Allows us to maintain our custom, optimized database schema with explicit `security_acl` JSONB columns, page numbers, and checksums.
  - **Granular Security:** Lets us apply precise SQL array overlap and JSON containment checks for ACL filtering directly in the database query.
  - **Performance:** Database queries are executed in a single transaction round-trip. Sorting, filtering, and rank limits are computed directly by the PostgreSQL engine.
  - **Zero Lock-in:** The database and retrieval layers remain completely decoupled from LangChain's evolving internal API structures.
- **Cons**:
  - Requires writing the Weighted RRF rank matching and sorting logic manually in Python (though the algorithm is simple and robust).

### Option B: LangChain Built-in Retrievers & Vector Store
- **Pros**:
  - Built-in `EnsembleRetriever` implements standard RRF scoring out-of-the-box.
- **Cons**:
  - **Rigid Schema Requirements:** Forces the database to use LangChain's default table names (`langchain_pg_collection` and `langchain_pg_embedding`) and column shapes, making custom security ACL columns extremely difficult to implement.
  - **In-Memory Sorting Overhead:** LangChain's built-in FTS and vector retrievers query databases independently and load all raw chunk outputs into Python memory to execute RRF sorting, resulting in high network overhead and latency.
  - **API Instability:** LangChain's package structures and dependency interfaces are highly volatile, introducing potential breaking changes during upgrades.

## Consequences

### Positive:
- The database schema and retrieval layers remain extremely clean, highly performant, and database-autonomous.
- High-performance, exact security filtering is executed on the database side before any data is loaded into memory.
- Future transitions to alternative specialized search backends (e.g. Azure AI Search) are straightforward because the retrieval layer is isolated behind a clean project interface (`BaseRetriever`).

### Negative / trade-offs:
- We write the SQL filters and the RRF rank-merging loop ourselves rather than relying on a library import.

## Implementation notes

* The custom retriever in `app/retrieval/vector.py` will inherit from the abstract `BaseRetriever` interface.
* Database operations will be performed using standard SQLAlchemy 2.0 select statements.

## Follow-ups

- [ ] Implement custom pgvector similarity query in SQLAlchemy.
- [ ] Implement custom full-text search lexical query using PostgreSQL `to_tsvector` and GIN index.
- [ ] Merge and rank output arrays using the weighted RRF loop in-process.
