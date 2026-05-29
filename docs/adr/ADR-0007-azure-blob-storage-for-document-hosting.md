# ADR-0007: Azure Blob Storage for Document Hosting

- Status: accepted
- Date: 2026-05-29
- Owners: Antigravity AI
- Supersedes: None
- Superseded by: None

## Context

In early Phase 0 and Phase 1 vertical spikes, the source document PDF files were stored and loaded exclusively on the local filesystem. As we scale the application to a visual web dashboard in Phase 2 and prepare for production deployment, local file hosting becomes a blocker:
1. Production runtimes (Azure Container Apps) are stateless and ephemeral; original files cannot be saved on local container disks.
2. Users must be able to securely click and view original PDF documents directly from the Next.js web application.
3. Access to source files must remain restricted by active security group ACLs.

We need a scalable, enterprise-grade cloud file hosting service with robust SDK support, low latency, and secure access boundaries.

## Decision

We decided to adopt **Azure Blob Storage** utilizing the official `azure-storage-blob` Python SDK library as the primary repository for RAG source files. 

Key details of the integration:
1. **Blob Storage Provider**: Built `BlobStorageProvider` inside `app/providers/blob_storage.py` to wrap cloud upload (`upload_blob`) and download (`download_blob`) actions.
2. **Local Fallback Design**: Implemented a seamless local filesystem fallback. If storage credentials are not configured in `.env`, the pipeline gracefully falls back to storing and reading from local data directories, maintaining 100% offline local development and test integrity.
3. **Ingestion Upload Hook**: Updated `IngestionPipeline` (`app/ingestion/pipeline.py`) to automatically upload PDF binaries to the Azure container `"originals"` and write the `source_type="azure_blob"` and `source_uri="azure://originals/{filename}"` fields to the database.
4. **FastAPI Streamed View Route**: Exposed `GET /api/documents/view/{document_id}` which dynamically streams PDF bytes inline from Azure Blob (using `StreamingResponse`) or local disk (using `FileResponse`).

## Options considered

### Option A: Direct Azure Blob Storage Integration (Selected)

Integrate the official Azure Blob Storage client SDK into FastAPI.

* **Pros:**
  * Strategic alignment with Azure-first enterprise architecture.
  * Ephemeral containers are fully stateless; files are persisted reliably in the cloud.
  * Fast inline streaming capabilities with high bandwidth.
  * Seamless local fallback enables zero-overhead local sandboxes.
* **Cons:**
  * Introduces external Azure dependency.

### Option B: Local Ephemeral Docker Volume Mapping

Keep using standard local file directories and map them to Docker volumes in production.

* **Pros:**
  * Simplifies backend code; no storage provider layer needed.
* **Cons:**
  * Ephemeral container scaling makes volume synchronization highly complex and error-prone.
  * Expensive file storage overheads on virtual machine disks.

## Consequences

### Positive

* **Stateless Runtimes**: FastAPI Container Apps can be scaled up or down freely without worrying about copying PDF files across instances.
* **Security & ACLs**: Blob containers are kept strictly `Private`. The application acts as a secure gateway, authorizing, fetching, and streaming PDFs inline, meaning raw connection strings or blobs are never exposed to the public internet.
* **Zero-Setup Local Dev**: Developers can boot the entire stack and test retrieval offline out-of-the-box without provisioning Azure Storage Accounts, thanks to the local disk fallback.

### Negative / trade-offs

* **Deployment Secret**: Requires configuring the `AZURE_STORAGE_CONNECTION_STRING` variable in production settings (Azure Key Vault).

## Implementation notes

* **Ingestion Side**: If `blob_provider.is_configured()` is true, files are uploaded to Azure and marked as `azure_blob`. If false, they are saved as `local` and read from the `data/` folder.
* **Retrieval Side**: The `GET /api/documents/view/{document_id}` API route parses `source_type` and handles both `azure_blob` downloading and `local` filesystem loading automatically.

## Follow-ups

- [x] Create Azure deployment setup handoff instructions for human resource provisioning.
- [ ] Implement chunk metadata cleanups once Azure Storage lifecycle policies are established.
