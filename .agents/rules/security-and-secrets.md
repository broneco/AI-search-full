# Rule: Security and Secrets

## Core rule

The LLM must never receive or persist data the user is not authorized to see.

## Secrets

Never commit or write these into tracked files:

- API keys
- Azure OpenAI keys
- connection strings
- client secrets
- access tokens
- refresh tokens
- private certificates
- production `.env` values

Use placeholders such as:

```text
AZURE_OPENAI_ENDPOINT=<provided by environment>
AZURE_OPENAI_API_KEY=<stored in Key Vault or local untracked env>
```

## Azure secrets

Prefer:

1. managed identity
2. Key Vault references
3. local untracked `.env` for development only

## Retrieval ACL rule

ACL filtering must happen before context packing and before any content is sent to an LLM.

This applies to:

- flash mode
- thinking mode
- follow-up retrieval
- reranking if it sends content to a model
- debug endpoints

## Audit logs

Audit logs must be useful but minimized.

Avoid storing full sensitive prompts or private document content unless explicitly required and approved. Prefer IDs, hashes, metadata, and redacted snippets.
