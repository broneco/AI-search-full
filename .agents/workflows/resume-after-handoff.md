# Workflow: Resume After Human Handoff

Use this workflow after the human completes a file in `.agents/inbox/`.

## 1. Read handoff

Check:

- completed resources
- returned non-secret values
- skipped steps
- human notes
- open issues

## 2. Validate no secrets were written

If the handoff contains actual secrets, tell the human to rotate/remove them and do not copy them elsewhere.

## 3. Update configuration

Update only safe files:

- `.env.example`
- config schema
- docs
- deployment runbooks

Never write secret values.

## 4. Test connection

Run or prepare checks for:

- database connection
- pgvector availability
- blob storage access
- model deployment availability
- Key Vault reference resolution
- Application Insights telemetry

## 5. Record outcome

Update:

- `CHANGELOG.md`
- `.agents/memory/project-state.md`
- `.agents/memory/implementation-notes.md`
- `docs/deployments/*.md` if stable
