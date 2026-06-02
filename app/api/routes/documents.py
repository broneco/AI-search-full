import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.providers.azure_openai import AzureOpenAIEmbeddingProvider
from app.schemas.documents import DocumentIngestRequest, DocumentIngestResponse
from app.storage.models import DBDocument, DBChunk

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache or reuse provider instance
embedding_provider = AzureOpenAIEmbeddingProvider()


@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    db: Session = Depends(get_db_session),
) -> DocumentIngestResponse:
    """Ingest a single document and generate embeddings using Azure OpenAI.

    This represents the core ingestion flow in Phase 0.
    """
    try:
        # Generate embedding vector
        logger.info(f"Generating embeddings for document: {request.title}")
        embedding = await embedding_provider.embed_query(request.content)
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Azure OpenAI Embedding generation failed: {str(e)}",
        )

    try:
        # Store DBDocument
        doc = DBDocument(
            source_type=request.source_type,
            source_uri=request.source_uri,
            title=request.title,
            document_type=request.document_type,
            language=request.language,
            security_acl=request.security_acl,
            metadata_json=request.metadata_json,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Store DBChunk
        chunk = DBChunk(
            document_id=doc.document_id,
            chunk_index=0,
            content=request.content,
            embedding=embedding,
            language=request.language,
            security_acl=request.security_acl,
            metadata_json=request.metadata_json,
        )
        db.add(chunk)
        db.commit()
        db.refresh(chunk)

        logger.info(f"Ingested document and chunk successfully. Doc ID: {doc.document_id}")
        return DocumentIngestResponse(
            document_id=str(doc.document_id),
            chunk_id=str(chunk.chunk_id),
            title=doc.title,
            status="ingested",
        )
    except Exception as e:
        logger.error(f"Database insertion failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database insertion failed: {str(e)}",
        )


@router.get("/list")
async def list_documents(
    http_request: Request,
    db: Session = Depends(get_db_session),
    x_user_groups: Optional[str] = Header(None, alias="X-User-Groups"),
):
    """List all ingested documents and their chunk counts, respecting security ACL allowed groups."""
    try:
        user_groups_str = x_user_groups or "User"
        acl_groups = [g.strip() for g in user_groups_str.split(",") if g.strip()]

        docs = db.query(DBDocument).order_by(DBDocument.ingested_at.desc()).all()
        result = []
        for doc in docs:
            # Enforce Management bypass and allowed groups filters
            if doc.security_acl and "Management" not in acl_groups:
                allowed_groups = doc.security_acl.get("allowed_groups", [])
                if "User" not in allowed_groups:
                    if allowed_groups and not any(g in acl_groups for g in allowed_groups):
                        continue

            chunk_count = db.query(DBChunk).filter(DBChunk.document_id == doc.document_id).count()
            result.append({
                "document_id": str(doc.document_id),
                "title": doc.title,
                "source_uri": doc.source_uri,
                "source_type": doc.source_type,
                "document_type": doc.document_type,
                "language": doc.language,
                "freshness_status": doc.freshness_status,
                "ingested_at": doc.ingested_at.isoformat(),
                "chunk_count": chunk_count
            })
        return result
    except Exception as e:
        logger.error(f"Failed to query document list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/view/{document_id}")
async def view_document(document_id: str, db: Session = Depends(get_db_session)):
    """Fetch the document PDF file from local storage or Azure Blob and serve it directly to the browser."""
    from fastapi.responses import FileResponse, StreamingResponse
    from app.providers.blob_storage import BlobStorageProvider
    import io
    import os
    import uuid

    try:
        doc_uuid = uuid.UUID(document_id)
        doc = db.query(DBDocument).filter(DBDocument.document_id == doc_uuid).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        # Check if stored on Azure Blob
        if doc.source_type == "azure_blob":
            blob_provider = BlobStorageProvider()
            if not blob_provider.is_configured():
                raise HTTPException(
                    status_code=500,
                    detail="Azure Blob Storage connection is not configured."
                )
            
            # Extract container and blob names from source_uri (e.g. azure://container/blob.pdf)
            uri_parts = doc.source_uri.replace("azure://", "").split("/", 1)
            if len(uri_parts) < 2:
                container_name = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
                blob_name = uri_parts[0]
            else:
                container_name = uri_parts[0]
                blob_name = uri_parts[1]
                
            logger.info(f"Downloading blob '{blob_name}' from container '{container_name}'...")
            data = await blob_provider.download_blob(container_name, blob_name)
            
            return StreamingResponse(
                io.BytesIO(data),
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename={doc.title}.pdf"}
            )
        else:
            # Serve from local file
            local_path = doc.source_uri.replace("file://", "")
            if not os.path.exists(local_path):
                # Fallback to scanning data directory by title
                data_dir = os.path.abspath("data")
                filename = os.path.basename(local_path)
                fallback_path = os.path.join(data_dir, filename)
                if os.path.exists(fallback_path):
                    local_path = fallback_path
                else:
                    raise HTTPException(status_code=404, detail=f"Local PDF file not found at path: {local_path}")
            
            return FileResponse(
                local_path,
                media_type="application/pdf",
                filename=f"{doc.title}.pdf"
            )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")
    except Exception as e:
        logger.error(f"Failed to retrieve and serve document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
