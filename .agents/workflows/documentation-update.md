# Workflow: Documentation Update

1. Verify README commands against actual scripts and dependencies. Distinguish local/test/cloud behavior and read-only plans from Apply.
2. Update docs/development/ and docs/tests_explained/ for changed workflows/tests; use repository-relative paths and links.
3. Keep current changes in docs/CHANGELOG.md under Unreleased. Move to a version block only when the user requests a release.
4. Add an ADR for durable architectural decisions and update docs/navigation_guide.md for every added/removed/moved source file.
5. Keep .agents/memory/project-state.md concise: approved work, actual verification, deployed baseline, constraints and one next slice. Archive obsolete operational detail under .agents/memory/archive/ with an explicit historical label.
6. Preserve cloud evidence in docs/deployments/; prepare .agents/inbox/ handoffs for required external changes. Code verification alone does not establish cloud deployment.
7. Do not depend on private scratch scripts, absolute workstation paths or external agent brain/task files. Standard workflows must be understandable from a clean checkout.
