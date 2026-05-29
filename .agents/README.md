# .agents

This directory contains the project-specific operating system for AI coding agents.

The goal is not to make the agent implement the whole product in one shot. The goal is to make the agent work in small, reviewable, tested increments while continuously preserving project knowledge, architectural decisions, deployment handoffs, and implementation context.

## How this directory is organized

```text
.agents/
  AGENTS.md                         # Main agent contract and source of truth
  README.md                         # This file
  rules/                            # Always-on project rules
  workflows/                        # Repeatable task procedures
  templates/                        # Templates for ADRs, deployment handoffs, task slices
  memory/                           # Agent-maintained project memory
  inbox/                            # Temporary handoff files between human and agent
```

## First files to read

Agents must start by reading:

1. `.agents/AGENTS.md`
2. `.agents/memory/project-state.md`
3. `.agents/rules/iteration-policy.md`
4. `.agents/rules/azure-deployment-handshake.md`
5. Any rule or workflow relevant to the task

## Human workflow

Use this project in slices:

1. Ask the agent for one small implementation slice.
2. Agent plans the slice and updates project memory if needed.
3. Agent implements only the agreed slice.
4. Agent updates tests, documentation, ADRs, and changelog.
5. If Azure resources are required, the agent creates a handoff file in `.agents/inbox/`.
6. Human deploys or configures Azure resources manually.
7. Human records created resource names, endpoints, deployment names, and non-secret configuration values in the same handoff file.
8. Agent resumes and validates integration without ever asking for secrets to be committed.

## Files agents may update during normal work

Agents may update these when relevant:

- `CHANGELOG.md`
- `docs/adr/*.md`
- `.agents/memory/project-state.md`
- `.agents/memory/implementation-notes.md`
- `.agents/memory/open-questions.md`
- `.agents/inbox/*.md`
- Documentation and tests related to the current slice

## Files agents must treat carefully

Agents must not modify without explicit user request:

- production credentials
- `.env` files
- cloud billing settings
- authentication tenant settings
- authorization policies that could expose private data
- CI/CD secrets

## Temporary handoff files

Temporary human-agent handoff files belong in `.agents/inbox/`.

Naming convention:

```text
.agents/inbox/YYYY-MM-DD-<short-task>-handoff.md
```

When the handoff is complete, move the final version to:

```text
docs/deployments/YYYY-MM-DD-<short-task>.md
```
