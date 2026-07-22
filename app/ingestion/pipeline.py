import os
import logging
import hashlib
import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.providers.azure_openai import AzureOpenAIEmbeddingProvider
from app.providers.blob_storage import BlobStorageProvider
from app.core.config import settings
from app.ingestion.extraction import DocumentExtractor
from app.ingestion.chunking import RecursiveCharacterTextSplitter
from app.storage.models import DBDocument, DBChunk

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates file text extraction, chunk splitting, vector embeddings generation, and database updates."""

    def __init__(self, db_session: Session) -> None:
        self.db = db_session
        self.extractor = DocumentExtractor()
        
        # Load active chunking configuration dynamically
        from app.core.search_config import SearchConfigManager
        manager = SearchConfigManager()
        config = manager.load_config_sync()
        from app.providers.azure_openai import AzureOpenAIProvider
        self.embedding_provider = AzureOpenAIEmbeddingProvider()
        self.llm_provider = AzureOpenAIProvider()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.get("chunk_size", 1500),
            chunk_overlap=config.get("chunk_overlap", 250),
            chunk_cross_page=config.get("chunk_cross_page", False),
            overlap_cross_page=config.get("overlap_cross_page", False),
            chunk_splitter_type=config.get("chunk_splitter_type", "recursive"),
            chunking_strategy=config.get("chunking_strategy", "standard"),
            semantic_params=config.get("semantic_params"),
            structure_params=config.get("structure_params"),
            token_params=config.get("token_params"),
            agentic_params=config.get("agentic_params"),
            embedding_provider=self.embedding_provider,
            llm_provider=self.llm_provider
        )
        self.blob_provider = BlobStorageProvider()

    async def ingest_file(
        self,
        file_path: str,
        document_type: str = "document",
        security_acl: Optional[Dict[str, List[str]]] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> DBDocument:
        """Process a single file end-to-end and persist it to PostgreSQL."""
        file_name = os.path.basename(file_path)
        # Determine the relative file path from data/ if applicable, to prevent folder conflicts
        parts = file_path.replace("\\", "/").split("/data/")
        if len(parts) > 1:
            relative_path = parts[-1]
        else:
            relative_path = file_name

        logger.info(f"┌─ 🚀 Ingestion pipeline started for file: {relative_path}")

        # 1. Generate checksum to track file changes
        logger.info(f"│  ├── [Step 1/5] Calculating file checksum & checking database status...")
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        checksum = hashlib.sha256(file_bytes).hexdigest()

        # Check if the document already exists in the database
        from sqlalchemy import select
        container_name = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
        existing_doc_stmt = select(DBDocument).where(
            (DBDocument.source_uri == f"file://{relative_path}") |
            (DBDocument.source_uri == f"azure://{container_name}/{relative_path}")
        )
        existing_doc = self.db.execute(existing_doc_stmt).scalar_one_or_none()

        if existing_doc and existing_doc.checksum == checksum:
            logger.info(f"│  ├── ℹ️ Document {file_name} already exists and is unchanged. Updating metadata, security ACL, and language...")
            from sqlalchemy.orm.attributes import flag_modified
            if security_acl is not None:
                existing_doc.security_acl = security_acl
                flag_modified(existing_doc, "security_acl")
            if metadata_json is not None:
                existing_doc.metadata_json = metadata_json
                flag_modified(existing_doc, "metadata_json")
                if "freshness_status" in metadata_json:
                    existing_doc.freshness_status = metadata_json["freshness_status"]
            # Update language
            existing_doc.language = language
            self.db.add(existing_doc)
            self.db.commit()
            
            # Update associated chunks as well
            update_data = {"language": language}
            if security_acl is not None:
                update_data["security_acl"] = security_acl
            if metadata_json is not None:
                update_data["metadata_json"] = metadata_json
                if "freshness_status" in metadata_json:
                    update_data["freshness_status"] = metadata_json["freshness_status"]
                    
            if update_data:
                self.db.query(DBChunk).filter(DBChunk.document_id == existing_doc.document_id).update(update_data)
                self.db.commit()
                
            logger.info(f"└─ 📋 Ingestion updated: {file_name}")
            return existing_doc

        # If it exists but changed, delete old version to perform update
        if existing_doc:
            logger.info(f"│  ├── ⚠️ Document {file_name} changed. cleaning old records...")
            self.db.delete(existing_doc)
            self.db.commit()

        # 2. Extract text page-by-page
        logger.info(f"│  ├── [Step 2/5] Extracting text page-by-page using PyPDF...")
        extracted_pages = self.extractor.extract(file_path)
        logger.info(f"│  │   └── Page extraction complete. extracted {len(extracted_pages)} pages.")

        # 3. Split into contextual chunks
        logger.info(f"│  ├── [Step 3/5] Splitting extracted text into contextual chunks...")
        chunks = self.splitter.split_pages(extracted_pages)
        if not chunks:
            raise ValueError(f"No text extracted or split from document: {file_name}")
        logger.info(f"│  │   └── Text split complete. created {len(chunks)} chunks (size: {self.splitter.chunk_size}, overlap: {self.splitter.chunk_overlap}).")

        # 4. Generate embeddings in batch for all chunks
        logger.info(f"│  ├── [Step 4/5] Sending batches to Azure OpenAI (text-embedding-3-large)...")
        chunk_texts = [chunk.content for chunk in chunks]
        logger.info(f"│  │   └── Generating embedding vectors for {len(chunk_texts)} chunks...")
        try:
            embeddings = await self.embedding_provider.embed_documents(chunk_texts)
            logger.info(f"│  │   └── Azure OpenAI vectors generated successfully.")
        except Exception as e:
            logger.error(f"│  └── ❌ Failed to generate embeddings: {e}")
            raise

        # 5. Persist document and chunk nodes to database
        logger.info(f"│  ├── [Step 5/5] Persisting document and chunks to Azure PostgreSQL...")
        try:
            # Parse created_at and clean up metadata_json to prevent database JSON serialization errors
            metadata = dict(metadata_json or {})
            created_at_val = metadata.get("created_at", None)
            
            created_at_dt = datetime.datetime.utcnow()
            if created_at_val:
                if isinstance(created_at_val, str):
                    try:
                        created_at_dt = datetime.datetime.fromisoformat(created_at_val)
                    except Exception:
                        pass
                elif isinstance(created_at_val, datetime.datetime):
                    created_at_dt = created_at_val
                    # Convert to string in metadata to avoid JSON serialization errors
                    metadata["created_at"] = created_at_val.isoformat()

            source_type = "local"
            source_uri = f"file://{relative_path}"

            if self.blob_provider.is_configured():
                container_name = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
                logger.info(f"│  ├── [Blob Storage] Uploading {relative_path} to Azure container '{container_name}'...")
                try:
                    await self.blob_provider.upload_blob(container_name, relative_path, file_bytes)
                    source_type = "azure_blob"
                    source_uri = f"azure://{container_name}/{relative_path}"
                    logger.info(f"│  │   └── Cloud upload complete. URI: {source_uri}")
                except Exception as e:
                    logger.warning(f"│  │   ⚠️ Azure Blob upload failed: {e}. Falling back to local storage path.")

            doc = DBDocument(
                source_type=source_type,
                source_uri=source_uri,
                title=os.path.splitext(file_name)[0],
                document_type=document_type,
                language=language,
                checksum=checksum,
                security_acl=security_acl or {"allowed_groups": ["Public"]},
                metadata_json=metadata,
                freshness_status=metadata.get("freshness_status", "current"),
                created_at=created_at_dt,
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)
            logger.info(f"│  │   ├── Parent DBDocument row created successfully. ID: {doc.document_id}")

            from sqlalchemy import insert
            
            chunk_mappings = []
            for idx, chunk in enumerate(chunks):
                chunk_mappings.append(
                    {
                        "document_id": doc.document_id,
                        "chunk_index": chunk.index,
                        "content": chunk.content,
                        "embedding": embeddings[idx],
                        "language": language,
                        "page_number": chunk.page_number,
                        "security_acl": security_acl or {"allowed_groups": ["Public"]},
                        "metadata_json": metadata,
                        "freshness_status": metadata.get("freshness_status", "current"),
                        "created_at": created_at_dt,
                    }
                )

            # Executing a single batch SQL insert is highly optimal for remote WAN connections
            logger.info(f"│  │   ├── Executing bulk database insertion for {len(chunk_mappings)} chunks...")
            self.db.execute(insert(DBChunk), chunk_mappings)
            self.db.commit()
            logger.info("│  │   └── Database transaction committed successfully.")

            logger.info(f"└─ 🎉 Ingestion successfully completed: {file_name}")
            return doc

        except Exception as e:
            logger.error(f"│  └── ❌ Database transaction failed: {e}")
            self.db.rollback()
            raise
