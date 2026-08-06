# Rule: Documentation, Changelog, and ADR Policy

## Changelog

Update `CHANGELOG.md` whenever the change affects:

- application behavior
- architecture
- dependencies
- infrastructure
- security posture
- developer workflow
- agent instructions

Use these categories under `[Unreleased]`:

- `Added`
- `Changed`
- `Fixed`
- `Security`
- `Deprecated`
- `Removed`

## ADRs

Create or update an ADR for durable decisions.

Examples requiring ADR:

- choosing PostgreSQL + pgvector as MVP vector store
- introducing Azure AI Search later
- selecting LangGraph for stateful workflows
- deciding how ACL filtering is enforced
- changing model profile strategy
- changing deployment architecture

Examples not requiring ADR:

- renaming a local variable
- adding a small unit test
- fixing a typo
- updating documentation wording

## Memory updates

Update `.agents/memory/` only when the information will help future agent sessions.

Good memory entries:

- current project phase
- chosen conventions
- constraints discovered during implementation
- non-secret Azure resource names returned by the human
- known blockers and open questions

Bad memory entries:

- long pasted logs
- secrets
- temporary debugging notes

## Repository Navigation Guide (navigation_guide.md)

Agents MUST maintain `docs/navigation_guide.md` in 100% synchronization with the actual repository tree (excluding individual raw input PDF files inside `data/`, where only the directory structure itself is documented).

Whenever a new codebase file or directory is created, moved, or deleted anywhere in the repository:
1. Add/update/remove the entry in `docs/navigation_guide.md`.
2. Provide a clear, concise 1-sentence description in Czech explaining the purpose and role of the file/folder.
3. Ensure no codebase files or folders are missed.
