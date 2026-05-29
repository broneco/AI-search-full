import logging
from fastapi import APIRouter, Depends, HTTPException
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
async def list_documents(db: Session = Depends(get_db_session)):
    """List all ingested documents and their chunk counts for the status dashboard."""
    try:
        docs = db.query(DBDocument).order_by(DBDocument.ingested_at.desc()).all()
        result = []
        for doc in docs:
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
