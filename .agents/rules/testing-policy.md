# Rule: Testing Policy

## Required principle

Every behavior change needs verification.

## Temporary test workspaces

Run pytest normally without a custom `--basetemp`: `tests/conftest.py` places numbered, lock-protected sessions under `.local/tmp/pytest/`. Pytest retains three recent sessions and protects active runs; its cache remains `.local/pytest-cache`. Do not create `.tmp-pytest*` directories in the repository root. If an explicit diagnostic base is necessary, use a unique child of `.local/tmp/pytest/`, never one shared fixed base or a directory containing user files: pytest deletes an explicit base before use. Respect operator overrides through `PYTEST_DEBUG_TEMPROOT` or `--basetemp`. Windows sandbox permission errors require the normal escalation workflow, not another root-level temporary directory. Delete old artefacts only after verifying their scope and that no test still uses them.

## Backend tests

Prefer these test layers:

- unit tests for pure logic
- repository tests for database access when schema exists
- integration tests for API endpoints
- retrieval evals for search relevance and source quality
- agent evals for prompt and orchestration changes

## Retrieval-specific tests

When changing retrieval, test at least one of:

- query enrichment
- vector search request construction
- keyword search request construction
- fusion/ranking behavior
- ACL filtering before context packing
- freshness filtering
- citation metadata preservation

## Agent tests / evals

When changing prompts, model routing, or LangGraph workflows, add or update eval cases that check:

- groundedness
- source citation presence
- stale source handling
- correct mode selection: `flash` vs `thinking`
- refusal or safe handling when evidence is insufficient

## If tests cannot run

State exactly:

- which command should be run
- why it could not be run
- what risk remains
- what the next human or agent should verify
