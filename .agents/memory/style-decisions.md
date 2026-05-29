# Style Decisions Memory

## Current conventions

- Python version target: 3.11+.
- API framework: FastAPI.
- Configuration should be typed and environment-driven.
- Model profiles are named `flash`, `thinking`, and `embedding`.
- Do not hardcode Azure deployment names.
- Use explicit provider interfaces for replaceable dependencies.
- Keep route handlers thin.
- Keep LangChain/LangGraph inside orchestration/provider layers.

## To be decided after implementation starts

- package manager: pip, uv, poetry, or pdm
- formatter: ruff format, black, or other
- linter: ruff likely preferred, not yet decided
- test runner: pytest likely preferred, not yet decided
- database migration tool: Alembic likely preferred, not yet decided
