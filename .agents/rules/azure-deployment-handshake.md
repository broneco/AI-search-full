# Rule: Azure Deployment Handshake

## Context

The agent does not have direct access to Azure. Any Azure resource creation or configuration must be performed by a human.

## Required workflow

When the implementation requires Azure resources or Azure configuration:

1. Stop implementation at the integration boundary if continuing would require guessing Azure values.
2. Create a file in `.agents/inbox/` using `.agents/templates/azure-deployment-handoff-template.md`.
3. Fill in the requested resources, exact values needed back from the human, and validation steps.
4. Continue only with local mocks or provider interfaces until the human completes the handoff.
5. After the human fills the handoff, read it and continue implementation/testing.
6. Move completed handoff documentation to `docs/deployments/` when the integration is stable.

## What the handoff must include

- purpose of the deployment
- exact Azure resources to create or modify
- suggested names if known
- required SKU/tier only if relevant
- networking assumptions
- managed identity requirements
- Key Vault secret names, not secret values
- model deployment names needed by the app
- environment variable names the app expects
- validation commands or endpoint checks
- rollback instructions

## What must not be included

- secret values
- passwords
- API keys
- connection strings containing credentials
- private certificates

## Human response format

Ask the human to fill only non-secret values into the handoff file, such as:

- resource group name
- Azure region
- PostgreSQL server name
- database name
- storage account name
- blob container name
- Key Vault name
- secret names
- Azure OpenAI endpoint host
- model deployment names
- Application Insights connection setting name, not secret value when possible
