# Azure Deployment Handoff: Azure OpenAI / AI Foundry Setup

- Status: completed
- Created: 2026-05-28
- Related task: Phase 0 RAG Proof of Concept

## Why this handoff exists

The implementation agent is executing Phase 0 technical spike inside a local sandbox environment and does not possess access credentials or permissions to deploy services directly in the user's Microsoft Azure subscription.

## Goal

Provide real API connectivity to Azure OpenAI for text embeddings generation (`text-embedding-3-large`) and conversational answers (`gpt-5.4-mini`) to prove and verify the full RAG pipeline locally.

## Resources to create or modify

Please log into your Azure Portal or Azure AI Foundry directory and ensure the following resources and deployments are available:

| Resource | Suggested action | Deployment / Model Name | Target dimension | Notes |
|---|---|---|---|---|
| Azure OpenAI Service | Create or select instance | | | Ensure the service is in a supported region (e.g. East US, Sweden Central) |
| Model Deployment | Deploy embedding model | `text-embedding-3-large` | **1536** | Provide deployment name below. Make sure to select or map the output dimension size as 1536. |
| Model Deployment | Deploy chat model | `gpt-5.4-mini` | | Used for both Flash and Thinking mode queries in our MVP spike. |

## Required app configuration keys

Please copy the endpoint and keys from your Azure Portal, create a local, untracked `.env` file at the root of the project workspace (`c:\Users\ondrej.bronec\OneDrive - dolphinconsulting.cz\Documents\Projekty\AI Search Full\.env`), and populate the following keys:

```ini
# Core Configuration
APP_ENV=local
APP_NAME=ai-search-app
LOG_LEVEL=INFO

# Azure OpenAI Credentials
AZURE_OPENAI_ENDPOINT=https://<your-openai-resource-name>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-azure-openai-api-key>

# Deployment Profiles (No hardcoded names in code)
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_OPENAI_FLASH_DEPLOYMENT=gpt-5.4-mini
AZURE_OPENAI_THINKING_DEPLOYMENT=gpt-5.4-mini
```

## Validation steps for human

Verify that the local environment file is recognized and loaded by executing our health check integration tests:
```powershell
.venv\Scripts\pytest.exe tests/test_health.py -v
```

## Validation steps for agent after completion

Once you configure the keys and confirm, the agent will:
1. Run local config validation.
2. Spin up/connect database.
3. Call the real Azure OpenAI APIs to generate sample document embeddings and save them to PostgreSQL.
4. Execute an end-to-end RAG chat completion and assert citation correctness.

## Rollback

To disable or clean up:
1. Delete the local `.env` file.
2. Delete the Azure OpenAI model deployments and service instance inside the Azure portal.
