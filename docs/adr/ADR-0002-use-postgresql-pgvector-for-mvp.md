# ADR-0001: Use PostgreSQL with pgvector as the MVP search and knowledge store

- Status: accepted
- Date: 2026-05-26
- Owners: project owner / implementation agent
- Supersedes: none
- Superseded by: none

## Context

The project needs a first production-oriented storage and search layer for documents, chunks, embeddings, metadata, ACL information, audit logs, feedback, model/profile configuration, glossary entries, and search sessions.

The design goal is Azure-first, but with minimal vendor lock-in outside Microsoft Azure. MVP complexity should stay low while preserving future ability to add Azure AI Search, Qdrant, OpenSearch, or another backend.

## Decision

Use Azure Database for PostgreSQL Flexible Server with the pgvector extension as the MVP data and vector search layer.

Use PostgreSQL full-text search for keyword search in MVP.

Do not use Azure AI Search in MVP, but keep the search layer behind provider interfaces so it can be added later.

Do not use Chroma as production vector store. It may be used only for local experiments.

## Options considered

### PostgreSQL Flexible Server + pgvector

Pros:

- one central store for documents, chunks, metadata, ACLs, audit, feedback, and embeddings
- lower MVP operational complexity
- Azure-managed database
- keeps architecture portable enough through PostgreSQL and provider interfaces
- supports both vector and full-text search in one system

Cons:

- may not match specialized search engines for scale or relevance tuning
- requires careful schema/index design
- future migration may be needed if corpus or query load grows

### Azure AI Search in MVP

Pros:

- managed enterprise search service
- strong future fit for Azure-first strategy
- specialized indexing/search features

Cons:

- more components in MVP
- higher operational and cost complexity
- not necessary for first technical spike

### Qdrant or another dedicated vector database

Pros:

- specialized vector search capabilities
- good future option if vector search becomes bottleneck

Cons:

- additional infrastructure
- more non-Azure vendor surface unless self-hosted
- not needed for MVP

## Consequences

Positive:

- MVP can move faster with fewer services.
- Data model can evolve in one database first.
- Retrieval, audit, feedback, and configuration can share transactional storage.

Negative / trade-offs:

- Search relevance and scale must be measured early.
- Provider abstraction must be designed before adding future search backends.
- PostgreSQL indexes, vector dimensions, and query plans must be evaluated with real corpus size.

## Implementation notes

- Create provider interfaces for vector search, keyword search, hybrid retrieval, and embeddings.
- Store embedding model version and dimensions with chunks or index metadata.
- Keep ACL and freshness filtering in retrieval pipeline before context packing.
- Add retrieval evals before replacing or augmenting the search backend.

## Follow-ups

- [x] Define initial PostgreSQL schema for documents and chunks.
- [x] Define pgvector index strategy.
- [ ] Define full-text search language configuration for Czech and English (scheduled for Version 0.2.0 FTS integration).
- [ ] Create first retrieval eval dataset (scheduled for Version 0.2.0 evaluation phase).
