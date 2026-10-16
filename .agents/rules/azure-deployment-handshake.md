# Rule: Azure Deployment Handshake

## Context

Azure CLI access may be available. Read access does not authorize resource changes. Prepare a concrete, reviewable handoff before writes; a human performs the actions unless the user explicitly authorizes the agent to execute them. Reuse existing authorization within its scope.

## Required workflow

When the implementation requires Azure resources or Azure configuration:

1. Stop implementation at the integration boundary if continuing would require guessing Azure values.
2. Create a file in `.agents/inbox/` using `.agents/templates/azure-deployment-handoff-template.md`.
3. Fill in the requested resources, exact values needed back from the human, and validation steps.
4. Continue with local mocks or provider interfaces until the target values and authorization are established.
5. Read the completed handoff, validate the target and continue implementation/testing. Execute cloud writes only within explicit user authorization; otherwise leave them to the human.
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
- Azure SQL server name (or the explicitly selected alternative)
- database name
- storage account name
- blob container name
- Key Vault name
- secret names
- Azure OpenAI endpoint host
- model deployment names
- Application Insights connection setting name, not secret value when possible
