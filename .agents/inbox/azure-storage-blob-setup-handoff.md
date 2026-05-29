# Azure Deployment Handoff: Azure Storage Blob Setup

- Status: completed
- Created: 2026-05-29
- Related task: Transition document RAG pipeline from localized to Azure Blob storage
- Related ADR: ADR-0001 (Storage abstraction boundary)

## Why this handoff exists

The AI implementation agent does not have direct CLI access or credentials to modify or provision resources in your Azure subscription. To switch your document storage from local disk folders to Azure cloud container storage, you need to create an Azure Storage Account and configure the target container.

## Goal

Enable secure cloud-based document hosting. Once completed:
1. PDFs ingested via `full_refresh_ingest.py` or the `/api/documents/ingest` endpoint will be uploaded directly to Azure Blob Storage.
2. Clicking document preview links on the frontend dashboard will dynamically fetch and stream the PDF file from your Azure Blob container inline to the browser.

---

## Resources to create or modify

| Resource | Action | Suggested name | Required settings | Notes |
|---|---|---|---|---|
| Resource Group | create/use | `rg-ai-search-prod` | region: `westeurope` (or preferred) | Can use an existing group. |
| Storage Account | create | `staisearchoriginals` | performance: `Standard`, replication: `LRS`, tier: `Hot` | Must be globally unique. |
| Blob Container | create | `originals` | public access: `Private` (No anonymous access) | Stores source original PDFs. |

---

## Required app configuration keys

Add these keys to your local, Git-ignored [**`.env`**](file:///c:/Users/ondrej.bronec/OneDrive - dolphinconsulting.cz/Documents/Projekty/AI Search Full/.env) file:

| Key | Secret? | Source | Value to provide | Notes |
|---|---:|---|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | **Yes** | Azure Portal (Access keys) | Paste your storage connection string here | Authorized connection string. Do not commit. |
| `AZURE_BLOB_CONTAINER_ORIGINALS` | no | Manual input | `"originals"` | Name of your storage container. |

---

## How to set it up in Azure (Step-by-Step)

### Option A: Via Azure CLI (Recommended - Fast)

Open your terminal or PowerShell and run these commands to set up the resources:

```bash
# 1. Login to Azure
az login

# 2. Select subscription (if you have multiple)
az account set --subscription "<subscription-name-or-id>"

# 3. Create Resource Group (skip if using an existing one)
az group create --name rg-ai-search-prod --location westeurope

# 4. Create Azure Storage Account (Change 'staisearchoriginals' if it is already taken)
az storage account create \
    --name staisearchoriginals \
    --resource-group rg-ai-search-prod \
    --location westeurope \
    --sku Standard_LRS \
    --kind StorageV2 \
    --access-tier Hot

# 5. Create the 'originals' private container
az storage container create \
    --name originals \
    --account-name staisearchoriginals \
    --public-access off

# 6. Retrieve the Storage Connection String
az storage account show-connection-string \
    --name staisearchoriginals \
    --resource-group rg-ai-search-prod \
    --query connectionString \
    --output tsv
```

### Option B: Via Azure Portal (UI)

1. Navigate to [Azure Portal](https://portal.azure.com).
2. Click **Create a resource** and select **Storage account**.
3. Fill in:
   * **Resource group**: Select `rg-ai-search-prod` (or create new).
   * **Storage account name**: `staisearchoriginals` (must be lowercase, letters and numbers only).
   * **Region**: `westeurope` (or same region as your deployment).
   * **Performance**: `Standard`.
   * **Redundancy**: `Locally-redundant storage (LRS)`.
4. Click **Review + Create**, then click **Create**.
5. Once deployed, navigate to the storage account page:
   * Go to **Containers** under *Data storage* in the left sidebar, click **+ Container nudge**, name it `originals`, set public access to `Private`, and click **Create**.
   * Go to **Access keys** under *Security + networking* in the left sidebar, click **Show keys**, and copy the **Connection string** of `key1`.

---

## Human-completed values

Once the resources are successfully created, please copy the values and fill this out to notify the agent:

```yaml
resource_group: "DOLPHIN_DS"
region: "westeurope"
storage_account: "juaisearchblob"
blob_container_originals: "originals"
notes: "Azure Blob storage created successfully. Connection string added to local .env file."
```

---

## Validation steps for human (After Setup)

1. Open your Git-ignored `.env` file at the project root and add the values:
   ```env
   AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=staisearchoriginals;AccountKey=...;EndpointSuffix=core.windows.net"
   AZURE_BLOB_CONTAINER_ORIGINALS="originals"
   ```
2. Save `.env`.
3. In your terminal, run the database seeding pipeline to test uploading the corporate Czech PDFs straight to your new Azure container:
   ```powershell
   .venv\Scripts\python.exe full_refresh_ingest.py
   ```
4. Check the logs: You should see new Blob Storage upload confirmation messages:
   `│  ├── [Blob Storage] Uploading R_399_registr_smluv.pdf to Azure container 'originals'...`
   `│  │   └── Cloud upload complete. URI: azure://originals/R_399_registr_smluv.pdf`

---

## Rollback

To revert and switch back to local file storage at any time:
1. Open `.env` and delete or comment out the `AZURE_STORAGE_CONNECTION_STRING` variable.
2. The application will automatically fall back to local disk storage mode!
