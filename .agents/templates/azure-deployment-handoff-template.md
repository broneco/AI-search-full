# Azure Deployment Handoff: <task-name>

- Status: draft | waiting-for-human | completed | blocked
- Created: YYYY-MM-DD
- Related task:
- Related ADR:
- Related branch/PR:

## Why this handoff exists

Explain why the agent cannot continue without human Azure action.

## Goal

What capability should exist after the human completes this handoff?

## Resources to create or modify

| Resource | Action | Suggested name | Required settings | Notes |
|---|---|---|---|---|
| Resource group | create/use | `<rg-name>` | region: `<region>` | |
| PostgreSQL Flexible Server | create/use | `<server-name>` | version, SKU, networking | Do not paste admin password here. |
| PostgreSQL database | create/use | `<db-name>` | enable pgvector | |
| Key Vault | create/use | `<kv-name>` | RBAC or access policy | Store secrets here. |

## Required app configuration keys

The application expects these environment/config keys.

| Key | Secret? | Source | Human should provide value here? | Notes |
|---|---:|---|---:|---|
| `AZURE_POSTGRES_HOST` | no | Azure Portal | yes | Host only, no password. |
| `AZURE_POSTGRES_DB` | no | Azure Portal | yes | Database name. |
| `AZURE_POSTGRES_USER` | no | Azure Portal | yes | If using password auth; prefer managed identity later. |
| `AZURE_POSTGRES_PASSWORD` | yes | Key Vault | no | Store in Key Vault or local untracked `.env`. |
| `AZURE_OPENAI_ENDPOINT` | no | Azure AI Foundry | yes | Endpoint host. |
| `AZURE_OPENAI_API_KEY` | yes | Key Vault | no | Store in Key Vault. |
| `AZURE_OPENAI_FLASH_DEPLOYMENT` | no | Azure AI Foundry | yes | Deployment name, not model name. |
| `AZURE_OPENAI_THINKING_DEPLOYMENT` | no | Azure AI Foundry | yes | Deployment name, not model name. |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | no | Azure AI Foundry | yes | Deployment name. |

## Human-completed values

Fill only non-secret values.

```yaml
resource_group:
region:
postgres_server:
postgres_database:
postgres_host:
postgres_auth_mode:
storage_account:
blob_container_originals:
blob_container_artifacts:
key_vault_name:
azure_openai_endpoint:
flash_model_deployment:
thinking_model_deployment:
embedding_model_deployment:
application_insights_name:
container_registry_name:
container_apps_environment:
notes:
```

## Secrets that must exist but must not be pasted here

| Secret purpose | Suggested Key Vault secret name | Created? | Notes |
|---|---|---:|---|
| PostgreSQL password, if password auth is used | `postgres-app-password` | no | Prefer managed identity where possible. |
| Azure OpenAI API key, if key auth is used | `azure-openai-api-key` | no | Prefer managed identity if supported by chosen service path. |

## Validation steps for human

```bash
# Example placeholders; adapt before running.
az account show
az postgres flexible-server show --resource-group <rg-name> --name <server-name>
```

## Validation steps for agent after completion

- Confirm config schema supports returned values.
- Confirm no secret values are committed.
- Run local config validation.
- Run integration check if environment access is available.
- If not available, provide exact command for human to run.

## Rollback

Describe how to undo or disable the resource/configuration safely.

## Open issues

- [ ]
