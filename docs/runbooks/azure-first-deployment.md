# Runbook: Azure-first deployment workflow

This project assumes the human performs Azure provisioning and the agent prepares exact handoff instructions.

## Standard sequence

1. Agent implements local interfaces/configuration first.
2. Agent creates `.agents/inbox/YYYY-MM-DD-<task>-handoff.md` when Azure resources are needed.
3. Human provisions resources.
4. Human fills non-secret values into the handoff file.
5. Agent resumes, validates configuration, and updates docs.
6. Completed deployment documentation is copied or moved to `docs/deployments/`.

## Never commit

- API keys
- connection strings with passwords
- client secrets
- private certs
- production `.env`

## Prefer

- managed identity
- Key Vault references
- non-secret resource names in tracked docs
- local `.env` only for development and only untracked
