# Workflow: Implement Slice

Use this workflow for normal feature work.

## 1. Understand

- Read `.agents/memory/project-state.md`.
- Identify current phase and current focus.
- Restate the requested outcome in one paragraph.
- Identify whether this is a spike, vertical slice, hardening, refactor, or docs task.

## 2. Bound the slice

Define:

- included scope
- excluded scope
- expected changed files
- tests or verification
- whether Azure manual action is needed

If the request is too large, implement the first useful slice only.

## 3. Implement

- Make the smallest coherent change.
- Keep provider boundaries intact.
- Avoid future-only placeholder layers.
- Do not hardcode Azure resource names or model deployments.

## 4. Verify

- Run targeted tests.
- Add tests if behavior changed.
- If tests cannot run, document exact command and risk.

## 5. Record

Update as relevant:

- `CHANGELOG.md`
- `docs/adr/*.md`
- `.agents/memory/project-state.md`
- `.agents/memory/implementation-notes.md`
- `.agents/memory/open-questions.md`

## 6. Report

Use the final response contract from `.agents/AGENTS.md`.
