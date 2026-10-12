# Azure Deployment Handoff: Showcase Tenant Azure Key Vault Provisioning & Secret Population

- Status: waiting-for-human
- Created: 2026-10-06
- Related task: Azure Key Vault secret management integration & Showcase tenant onboarding
- Related ADR: ADR-0017, ADR-0018
- Related branch/PR: main

## Why this handoff exists

The agent has implemented dynamic fetching of credentials (SQL Password, OpenAI API Key, Storage Connection String, PostgreSQL Password) from Azure Key Vault in `app/core/config.py` and `deploy_backend.ps1`.
To test and run the Showcase tenant (`showcase`) using Azure Key Vault instead of hardcoded plaintext values in local `.env` files, the human operator must create the Azure Key Vault resource `showcase-ais-kv-dev` (in resource group `ai-search-showcase-rg-dev`) and populate the secret values.

## Goal

Provide a secure, isolated Azure Key Vault for the Showcase environment with proper RBAC roles and secret entries so that Azure Container Apps (`showcase-ai-search-ca-dev`) and local backend scripts can retrieve credentials without storing secret strings in repository files.

## Resources to create or modify

| Resource | Action | Suggested name | Required settings | Notes |
|---|---|---|---|---|
| Resource Group | create/use | `ai-search-showcase-rg-dev` | region: `northeurope` | Standard showcase RG |
| Key Vault | create/use | `showcase-ais-kv-dev` | RBAC authorization model, Standard SKU | Secret store for showcase DEV |
| Role Assignment | grant | `Key Vault Secrets User` | Principal: Managed Identity / Developer Account | Enables reading secrets at runtime |

## Secrets that must exist in Key Vault (`showcase-ais-kv-dev`)

| Secret Purpose | Secret Name in Key Vault | Created? | Value to Store |
|---|---|---:|---|
| Azure SQL Admin Password | `showcase-ai-search-sql-sqlaccount-password-dev` | no | Password for `ai-search-showcase-sql-dev.database.windows.net` |
| Azure OpenAI API Key | `showcase-ai-search-openai-api-key-dev` | no | API Key for `https://ai-search-showcase-aif-dev.openai.azure.com/` |
| Azure Blob Storage Connection String | `showcase-ai-search-storage-connection-string-dev` | no | Connection string for `aisearchshowcasestdev` |
| PostgreSQL Admin Password | `showcase-ai-search-postgres-password-dev` | no | Password for `ju-ai-search-postgresql.postgres.database.azure.com` |

## Human execution steps (Azure CLI Commands)

Run the following commands in your Azure CLI / PowerShell session:

```powershell
# 1. Create Key Vault resource if it does not already exist
az keyvault create `
  --name "showcase-ais-kv-dev" `
  --resource-group "ai-search-showcase-rg-dev" `
  --location "northeurope" `
  --enable-rbac-authorization true

# 2. Populate secrets into Key Vault
az keyvault secret set --vault-name "showcase-ais-kv-dev" --name "showcase-ai-search-sql-sqlaccount-password-dev" --value "<YOUR_SQL_PASSWORD>"
az keyvault secret set --vault-name "showcase-ais-kv-dev" --name "showcase-ai-search-openai-api-key-dev" --value "<YOUR_OPENAI_API_KEY>"
az keyvault secret set --vault-name "showcase-ais-kv-dev" --name "showcase-ai-search-storage-connection-string-dev" --value "<YOUR_STORAGE_CONNECTION_STRING>"
az keyvault secret set --vault-name "showcase-ais-kv-dev" --name "showcase-ai-search-postgres-password-dev" --value "<YOUR_POSTGRES_PASSWORD>"

# 3. Grant 'Key Vault Secrets User' role to your CLI identity / Managed Identity
$userObjectId = (az ad signed-in-user show --query id --output tsv)
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee-object-id $userObjectId `
  --assignee-principal-type "User" `
  --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/ai-search-showcase-rg-dev/providers/Microsoft.KeyVault/vaults/showcase-ais-kv-dev"
```

## Validation steps for human

```powershell
# Verify that secrets can be read from Key Vault via Azure CLI
az keyvault secret show --vault-name "showcase-ais-kv-dev" --name "showcase-ai-search-sql-sqlaccount-password-dev" --query value --output tsv
az keyvault secret show --vault-name "showcase-ais-kv-dev" --name "showcase-ai-search-openai-api-key-dev" --query value --output tsv
```

## Validation steps for agent after completion

- Run `pytest tests/test_keyvault_config.py` to confirm mock and environment resolution.
- Run `deploy_backend.ps1 -Client showcase -Environment dev` to deploy and verify Container App Key Vault integration.
