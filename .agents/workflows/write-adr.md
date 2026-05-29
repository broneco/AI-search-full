# Workflow: Write ADR

Use this workflow when a durable architectural decision is made.

## 1. Decide whether ADR is needed

ADR is needed if reversing the decision later would be costly or if future agents need the rationale.

## 2. Choose number and slug

Use next number:

```text
docs/adr/ADR-0001-short-slug.md
```
Current number to use is in the template in step 3.
in `# ADR-000X: <Decision title>`

## 3. Use template

Copy `.agents/templates/adr-template.md`.

## 4. Keep it focused

One ADR = one decision.

Do not mix unrelated decisions.

## 5. Link follow-ups

If the ADR creates implementation work, add next slice to `.agents/memory/project-state.md` or `.agents/memory/open-questions.md`.

## 6. Update number inside the template

Update the number in the template `.agents/templates/adr-template.md` so the next model can continue