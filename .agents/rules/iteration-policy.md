# Rule: Iterative Slice Policy

## Purpose

This project is large. Agents must avoid one-shot implementation and avoid creating many half-finished layers.

## Required behavior

For every task, classify the requested work as one of:

- `spike`: prove feasibility with minimal code
- `vertical-slice`: end-to-end thin implementation
- `hardening`: tests, security, observability, reliability
- `refactor`: improve structure without changing behavior
- `docs`: documentation, ADRs, runbooks, instructions

Prefer `vertical-slice` when building product functionality.

## Slice size rule

A slice should usually fit into one of these scopes:

- one API endpoint
- one provider interface plus one implementation
- one database migration and its repository methods
- one retrieval pipeline step
- one frontend screen stub
- one deployment handoff
- one eval dataset addition

If the task is larger, split it and implement only the first coherent slice.

## Avoid

- implementing backend, frontend, infra, auth, ingestion, and agents in one pass
- creating empty placeholder modules for the entire future architecture
- adding abstractions without a first real implementation
- leaving TODOs instead of creating a clear follow-up slice

## Git Commit Policy

Do NOT perform frequent incremental Git commits or pushes to GitHub after small edits.
Only commit to Git when:
1. The user explicitly requests a commit, or
2. A major feature milestone is completed AND approved by the user.

## Required output

At the end of each slice, recommend exactly one next slice.
