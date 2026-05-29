# Workflow: Azure Manual Deploy Handoff

Use this workflow whenever a task needs Azure resources or cloud configuration that the agent cannot create directly.

## 1. Identify deployment need

Examples:

- PostgreSQL Flexible Server
- pgvector extension
- Blob Storage container
- Azure AI Foundry model deployments
- Azure Key Vault secrets
- Container Apps environment
- Container Registry
- Managed identity assignment
- Entra ID app registration
- Application Insights

## 2. Create handoff file

Create:

```text
.agents/inbox/YYYY-MM-DD-<short-task>-handoff.md
```

Use `.agents/templates/azure-deployment-handoff-template.md`.

## 3. Fill exact instructions

Include:

- resources to create
- expected names
- config keys the app expects
- non-secret values the human must return
- secret names that must exist in Key Vault
- validation steps
- rollback plan

## 4. Continue locally if possible

While waiting for human Azure work, continue only on:

- interfaces
- local mocks
- configuration schema
- tests that do not require real Azure
- documentation

Do not fake successful cloud integration.

## 5. Resume after human completion

Read the completed handoff file.

Then:

- update configuration examples with non-secret values only
- implement integration code if not done
- run connectivity checks
- update deployment docs
- update changelog and memory
