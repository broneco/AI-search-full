import logging
from typing import Optional
from azure.storage.blob import BlobServiceClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class BlobStorageProvider:
    """Interface provider to upload and stream source files from Azure Blob Storage.
    
    Supports dynamic fallback to local storage when Azure credentials are not configured.
    """

    def __init__(self) -> None:
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        self.account_name = settings.AZURE_STORAGE_ACCOUNT
        self.client: Optional[BlobServiceClient] = None

        if self.connection_string:
            try:
                self.client = BlobServiceClient.from_connection_string(self.connection_string)
                logger.info("Successfully initialized Azure Blob Storage client from connection string.")
            except Exception as e:
                logger.warning(f"Failed to initialize BlobServiceClient from connection string: {e}")
        elif self.account_name:
            try:
                # Fallback to Azure Managed Identity / DefaultAzureCredential if supported
                from azure.identity import DefaultAzureCredential
                credential = DefaultAzureCredential()
                self.client = BlobServiceClient(
                    account_url=f"https://{self.account_name}.blob.core.windows.net",
                    credential=credential
                )
                logger.info(f"Successfully initialized Azure Blob Storage client for account: {self.account_name} using Managed Identity.")
            except Exception as e:
                logger.warning(f"Failed to initialize BlobServiceClient using Managed Identity for account {self.account_name}: {e}")
        else:
            logger.info("Azure Blob Storage credentials not provided. Gracefully falling back to local file storage mode.")

    def is_configured(self) -> bool:
        """Return True if the Azure Blob Storage client is fully configured and ready."""
        return self.client is not None

    async def download_blob(self, container_name: str, blob_name: str) -> bytes:
        """Download binary data directly from a specified Azure Blob container."""
        if not self.client:
            raise ValueError("Azure Blob Storage client is not initialized.")
        
        try:
            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            
            # Read block blob download stream
            downloader = blob_client.download_blob()
            data = downloader.readall()
            return data
        except Exception as e:
            logger.error(f"Failed to download blob '{blob_name}' from container '{container_name}': {e}")
            raise

    async def upload_blob(self, container_name: str, blob_name: str, data: bytes) -> str:
        """Upload binary data to an Azure Blob container and return its cloud resource URI."""
        if not self.client:
            raise ValueError("Azure Blob Storage client is not initialized.")
        
        try:
            container_client = self.client.get_container_client(container_name)
            # Create container if it does not exist (useful for bootstrapping)
            try:
                container_client.create_container()
            except Exception:
                pass # Already exists
            
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(data, overwrite=True)
            
            blob_url = blob_client.url
            logger.info(f"Uploaded blob successfully. URL: {blob_url}")
            return blob_url
        except Exception as e:
            logger.error(f"Failed to upload blob '{blob_name}' to container '{container_name}': {e}")
            raise
