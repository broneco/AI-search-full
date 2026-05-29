# AGENTS.md

This repository uses `.agents/` as the canonical source of truth for agent instructions.

Before making changes, read these files in order:

1. `.agents/AGENTS.md` — main operating contract
2. `.agents/memory/project-state.md` — current state, phase, and active constraints
3. `.agents/rules/iteration-policy.md` — how to work in small reversible slices
4. `.agents/rules/azure-deployment-handshake.md` — required workflow when Azure resources must be deployed by a human
5. Relevant rules from `.agents/rules/`
6. Relevant workflows from `.agents/workflows/`

Do not treat this file as the full instruction set. It is only the root entrypoint.
