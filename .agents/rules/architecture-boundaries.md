# Rule: Architecture Boundaries

## Backend boundaries

The backend must keep these layers separate:

- API routes: HTTP concerns only
- schemas: request and response contracts
- retrieval: search, ranking, freshness, context packing
- RAG orchestration: current application code; LangGraph/LangChain are optional future choices
- providers: LLM, embeddings, search, storage provider integrations
- storage: database connections and repositories
- ingestion: loading, extraction, chunking, embedding, indexing
- observability: logging, tracing, metrics

## Dependency direction

Allowed:

- API calls services/use cases
- services call retrieval, agents, storage, providers
- retrieval uses provider interfaces and repositories
- providers wrap external services

Avoid:

- new API routes mixing HTTP handling with bulk database/model orchestration (legacy synchronous SQLAlchemy routes remain)
- LangChain objects leaking into API schemas
- agents directly bypassing retrieval ACL filters
- hardcoding Azure deployment names in business logic
- frontend depending on internal backend database shapes

## Provider abstraction rule

Any replaceable external dependency must sit behind a project interface:

- LLM provider
- embedding provider
- search backend
- blob storage
- auth identity adapter
- telemetry exporter

Current providers implement Azure SQL, Azure OpenAI and Blob integrations; PostgreSQL is experimental. Preserve interfaces for future replacement without implying that future adapters already exist.
