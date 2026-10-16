# Style Decisions Memory

## Current conventions

- Python minimum: 3.11; reference development environment: 3.12.
- API framework: FastAPI.
- Configuration should be typed and environment-driven.
- Model profiles are named `flash`, `thinking`, and `embedding`.
- Do not hardcode Azure deployment names.
- Use explicit provider interfaces for replaceable dependencies.
- Keep route handlers thin.
- RAG orchestration is application code; no LangChain/LangGraph dependency is currently used.

## Tooling

- package manager: pip; pyproject.toml is the canonical runtime/dev dependency declaration, requirements.txt installs .[dev].
- formatter: ruff format, black, or other
- linter: ruff likely preferred, not yet decided
- test runner: pytest with isolated SQLite fixtures and opt-in local SQL/Azure integrations.
- database migration tool: explicit guarded Python CLI scripts; Alembic is not implemented.
