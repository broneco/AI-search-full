# Rule: Testing Policy

## Required principle

Every behavior change needs verification.

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
