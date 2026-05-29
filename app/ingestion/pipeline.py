import os
import logging
import hashlib
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.providers.azure_openai import AzureOpenAIEmbeddingProvider
from app.ingestion.extraction import DocumentExtractor
from app.ingestion.chunking import CharacterTextSplitter
from app.storage.models import DBDocument, DBChunk

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates file text extraction, chunk splitting, vector embeddings generation, and database updates."""

    def __init__(self, db_session: Session) -> None:
        self.db = db_session
        self.extractor = DocumentExtractor()
        self.splitter = CharacterTextSplitter()
        self.embedding_provider = AzureOpenAIEmbeddingProvider()

    async def ingest_file(
        self,
        file_path: str,
        document_type: str = "document",
        security_acl: Optional[Dict[str, List[str]]] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> DBDocument:
        """Process a single file end-to-end and persist it to PostgreSQL."""
        file_name = os.path.basename(file_path)
        logger.info(f"┌─ 🚀 Ingestion pipeline started for file: {file_name}")

        # 1. Generate checksum to track file changes
        logger.info(f"│  ├── [Step 1/5] Calculating file checksum & checking database status...")
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        checksum = hashlib.sha256(file_bytes).hexdigest()

        # Check if the document already exists in the database
        from sqlalchemy import select
        existing_doc_stmt = select(DBDocument).where(DBDocument.source_uri == f"file://{file_name}")
        existing_doc = self.db.execute(existing_doc_stmt).scalar_one_or_none()

        if existing_doc and existing_doc.checksum == checksum:
            logger.info(f"│  ├── ℹ️ Document {file_name} already exists and is unchanged. skipping ingestion.")
            logger.info(f"└─ 📋 Ingestion skipped: {file_name}")
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
            doc = DBDocument(
                source_type="local",
                source_uri=f"file://{file_name}",
                title=os.path.splitext(file_name)[0],
                document_type=document_type,
                language="en",
                checksum=checksum,
                security_acl=security_acl or {"allowed_groups": ["Public"]},
                metadata_json=metadata_json or {},
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
                        "language": "en",
                        "page_number": chunk.page_number,
                        "security_acl": security_acl or {"allowed_groups": ["Public"]},
                        "metadata_json": metadata_json or {},
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
