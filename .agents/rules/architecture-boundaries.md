# Rule: Architecture Boundaries

## Backend boundaries

The backend must keep these layers separate:

- API routes: HTTP concerns only
- schemas: request and response contracts
- retrieval: search, ranking, freshness, context packing
- agents: LangGraph/LangChain orchestration and prompts
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

- API routes directly querying PostgreSQL
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

MVP can implement only Azure/PostgreSQL providers, but interfaces must not make future replacement impossible.
