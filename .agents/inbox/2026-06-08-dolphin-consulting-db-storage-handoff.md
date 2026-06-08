# Azure Deployment Handoff: Dolphin Consulting Parallel Environment Setup

- Status: completed
- Created: 2026-06-08
- Related task: Transition to Dolphin Consulting branding and parallel deployment
- Related ADR: ADR-0002, ADR-0007

## Why this handoff exists

To run the university project and the new Dolphin Consulting platform in parallel without incurring new billing charges, we will reuse your existing Azure PostgreSQL Flexible Server and Azure Storage Account. 

However, to avoid data mixing and table dropping, we need to create a **new database** inside PostgreSQL and a **new container** inside the Storage Account.

---

## Goal

Enable the Dolphin Consulting RAG pipeline to run on isolated storage and database schemas on the same underlying Azure servers.

---

## Resources to create or modify

Please execute the following actions in the Azure Portal or via Azure CLI:

| Resource | Action | Suggested Name | Required Settings | Notes |
|---|---|---|---|---|
| **PostgreSQL Database** | Create | `dolphin_ai_search` | Standard settings on server `ju-ai-search-postgresql` | Creates isolated DB catalog. |
| **Blob Container** | Create | `dolphin-originals` | Private access level on storage account `juaisearchblob` | Stores Dolphin Consulting PDFs. |

### How to create the Database via Azure CLI:
```bash
az postgres flexible-server db create \
  --resource-group <your-resource-group> \
  --server-name ju-ai-search-postgresql \
  --database-name dolphin_ai_search
```

### How to create the Storage Container via Azure CLI:
```bash
az storage container create \
  --name dolphin-originals \
  --connection-string "DefaultEndpointsProtocol=https;AccountName=juaisearchblob;AccountKey=<your-account-key>;EndpointSuffix=core.windows.net"
```

---

## Required App Configuration Keys

Please update your local `.env` file with these values once you have created the resources:

| Key | Secret? | Value to Set | Notes |
|---|---:|---|---|
| `POSTGRES_DB` | no | `dolphin_ai_search` | The new database name. |
| `AZURE_BLOB_CONTAINER_ORIGINALS` | no | `dolphin-originals` | The new container name. |

---

## Human Confirmation

Once you have completed these steps:
1. Create the database and storage container.
2. Update the `.env` file locally with the new database and container names.
3. Confirm here by replying that you are ready.
