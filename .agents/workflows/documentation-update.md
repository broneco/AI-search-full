# Workflow: Documentation Update

Use this workflow at the end of every release cycle to ensure that all documentation, memory files, and user guides are in a clean, fully accurate, and complete state.

---

## 1. Update Project Readmes & Guides
- Review the root [**`README.md`**](file:///c:/Users/ondrej.bronec/OneDrive - dolphinconsulting.cz/Documents/Projekty/AI Search Full/README.md).
- Ensure any new service layers, providers (e.g. Blob Storage, Azure OpenAI), and environmental variables are added to the list.
- Make sure to document both **FastAPI backend** and **Next.js frontend** dependencies, run commands, and development port setups clearly.
- If database schemas were updated, ensure the design documents in `docs/design` listing database tables and columns are kept in sync.
- If test files are added, removed, or modified, their corresponding markdown explanations in [**`docs/tests_explained/`**](file:///c:/Users/ondrej.bronec/OneDrive - dolphinconsulting.cz/Documents/Projekty/AI Search Full/docs/tests_explained/) are created or updated with clear high/low technical level details.

## 2. Compile Changelog Releases
- Review [**`CHANGELOG.md`**](file:///c:/Users/ondrej.bronec/OneDrive - dolphinconsulting.cz/Documents/Projekty/AI Search Full/CHANGELOG.md).
- Move all relevant changes tracked in the `[Unreleased]` section to a new, formal version block (e.g. `## [X.Y.Z] - YYYY-MM-DD`).
- Verify subsections (`Added`, `Changed`, `Fixed`, `Security`) are chronological, objective, and represent actual code accomplishments.

## 3. Keep Project State Memory and Tasks in Sync
- Update [**`.agents/memory/project-state.md`**](file:///c:/Users/ondrej.bronec/OneDrive - dolphinconsulting.cz/Documents/Projekty/AI Search Full/.agents/memory/project-state.md):
  1. Add the completed slice under `Current recommended slice` with the `[x] Completed` tag.
  2. Update the next recommended slice at the bottom.
- Ensure the task checklist [**`task.md`**](file:///C:/Users/ondrej.bronec/.gemini/antigravity/brain/8f1b5150-d71f-4b33-ab13-b8fd0e6f2710/task.md) inside the brain folder has all its items marked as `[x]` and its status set to `completed`.

## 4. Finalize Technical Walkthrough
- Update or create the [**`walkthrough.md`**](file:///C:/Users/ondrej.bronec/.gemini/antigravity/brain/8f1b5150-d71f-4b33-ab13-b8fd0e6f2710/walkthrough.md) file inside the brain folder:
  1. Summarize exactly what was accomplished in this release.
  2. Document the directory layout and newly created files.
  3. Include copy-pasteable console verification outputs (e.g., pytest tests, Next.js build compilation logs).
  4. Provide step-by-step local testing instructions so anyone can run and verify the features independently.
