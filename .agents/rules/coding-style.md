# Rule: Coding Style

## General

- Prefer clear, boring code over clever code.
- Keep modules small and cohesive.
- Use explicit names for domain concepts: `Document`, `Chunk`, `QueryAuditLog`, `ModelProfile`, `RetrievalResult`.
- Avoid premature abstractions, but preserve provider boundaries from the design.

## Python backend

- Target Python 3.11+.
- Use FastAPI for HTTP API.
- Use Pydantic models for request/response and configuration contracts.
- Use type hints for all public functions.
- Keep route handlers thin.
- Do not place business logic in FastAPI route functions.
- Use dependency injection for config, database sessions, and providers.
- Prefer async only where the stack is consistently async.

## Errors

- Use explicit domain exceptions for expected failures.
- Do not leak provider-specific errors directly to API responses.
- Include correlation IDs in logs where possible.

## Configuration

- No hardcoded model names, endpoints, tenant IDs, client IDs, connection strings, or secrets.
- Use environment variables and typed settings.
- Secret values belong in Azure Key Vault or local untracked `.env` files.

## Frontend

- Use TypeScript.
- Keep API clients typed.
- Do not duplicate backend business rules in UI.
- UI should display source citations and freshness status when returned by the backend.
