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
async def view_document(
    document_id: str,
    db: Session = Depends(get_db_session),
    highlight_chunk_id: Optional[str] = None,
):
    """Fetch the document PDF file from local storage or Azure Blob, highlight cited RAG chunk if requested, and serve it."""
    from fastapi.responses import StreamingResponse
    from app.providers.blob_storage import BlobStorageProvider
    import io
    import os
    import uuid

    try:
        doc_uuid = uuid.UUID(document_id)
        doc = db.query(DBDocument).filter(DBDocument.document_id == doc_uuid).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        # 1. Fetch raw PDF file bytes
        if doc.source_type == "azure_blob":
            blob_provider = BlobStorageProvider()
            if not blob_provider.is_configured():
                raise HTTPException(
                    status_code=500,
                    detail="Azure Blob Storage connection is not configured."
                )
            
            uri_parts = doc.source_uri.replace("azure://", "").split("/", 1)
            if len(uri_parts) < 2:
                container_name = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
                blob_name = uri_parts[0]
            else:
                container_name = uri_parts[0]
                blob_name = uri_parts[1]
                
            logger.info(f"Downloading blob '{blob_name}' from container '{container_name}'...")
            data = await blob_provider.download_blob(container_name, blob_name)
        else:
            # Serve from local file
            local_path = doc.source_uri.replace("file://", "")
            if not os.path.exists(local_path):
                data_dir = os.path.abspath("data")
                filename = os.path.basename(local_path)
                fallback_path = os.path.join(data_dir, filename)
                if os.path.exists(fallback_path):
                    local_path = fallback_path
                else:
                    raise HTTPException(status_code=404, detail=f"Local PDF file not found at path: {local_path}")
            
            with open(local_path, "rb") as f:
                data = f.read()

        # 2. Apply dynamic PDF text highlighting using PyMuPDF if chunk ID is provided
        if highlight_chunk_id:
            try:
                chunk_uuid = uuid.UUID(highlight_chunk_id)
                chunk = db.query(DBChunk).filter(DBChunk.chunk_id == chunk_uuid).first()
                if chunk:
                    import fitz
                    import re
                    import unicodedata
                    from collections import defaultdict

                    logger.info(f"Dynamically highlighting cited passage (chunk: {highlight_chunk_id}) on page {chunk.page_number}...")
                    
                    pdf_doc = fitz.open(stream=data, filetype="pdf")
                    page_num = (chunk.page_number or 1) - 1
                    
                    if 0 <= page_num < len(pdf_doc):
                        page = pdf_doc[page_num]
                        
                        def normalize_text(text: str) -> str:
                            text = text.lower()
                            # Decompose accented characters to standard ASCII characters where possible
                            text = "".join(
                                c for c in unicodedata.normalize('NFD', text)
                                if unicodedata.category(c) != 'Mn'
                            )
                            # Keep only basic English alphanumeric characters
                            return "".join(c for c in text if c.isalnum() and ord(c) < 128)

                        # Extract word objects with coordinates from PDF page
                        words_list = page.get_text("words")
                        
                        if words_list:
                            # Build character-to-word index mapping
                            normalized_page_chars = []
                            char_to_word_index = []
                            
                            for idx, w in enumerate(words_list):
                                word_text = w[4]
                                norm_w = normalize_text(word_text)
                                for char in norm_w:
                                    normalized_page_chars.append(char)
                                    char_to_word_index.append(idx)
                                    
                            normalized_page_str = "".join(normalized_page_chars)
                            
                            def find_and_group_words(search_str: str) -> list[int]:
                                norm_search = normalize_text(search_str)
                                if not norm_search:
                                    return []
                                start_pos = normalized_page_str.find(norm_search)
                                if start_pos == -1:
                                    return []
                                start_word_idx = char_to_word_index[start_pos]
                                end_word_idx = char_to_word_index[start_pos + len(norm_search) - 1]
                                return list(range(start_word_idx, end_word_idx + 1))

                            # Clean chunk content
                            search_text = chunk.content.replace("\n", " ").strip()
                            search_text = re.sub(r"\s+", " ", search_text)
                            
                            matched_word_indices = []

                            # Step 2a: Try matching the exact full-text block first
                            whole_chunk_indices = find_and_group_words(search_text)
                            if whole_chunk_indices:
                                matched_word_indices = whole_chunk_indices
                            else:
                                # Step 2b: Fallback to sentence-by-sentence matching
                                sentences = [s.strip() for s in re.split(r"[.!?]", search_text) if len(s.strip()) > 10]
                                for sentence in sentences:
                                    sentence_indices = find_and_group_words(sentence)
                                    if sentence_indices:
                                        matched_word_indices.extend(sentence_indices)

                                # Step 2c: Fallback to first 10 words
                                if not matched_word_indices:
                                    words = [w for w in search_text.split(" ") if w.strip()]
                                    if len(words) >= 5:
                                        phrase = " ".join(words[:10])
                                        phrase_indices = find_and_group_words(phrase)
                                        if phrase_indices:
                                            matched_word_indices = phrase_indices

                                # Step 2d: Fallback to first 5 words
                                if not matched_word_indices and len(words) >= 3:
                                    phrase = " ".join(words[:5])
                                    phrase_indices = find_and_group_words(phrase)
                                    if phrase_indices:
                                        matched_word_indices = phrase_indices

                            # If matches were found, merge them by block and line coordinates
                            if matched_word_indices:
                                matched_word_indices = sorted(list(set(matched_word_indices)))
                                lines_map = defaultdict(list)
                                
                                for idx in matched_word_indices:
                                    w = words_list[idx]
                                    # Group by (block_no, line_no)
                                    lines_map[(w[5], w[6])].append(w)
                                    
                                for line_words in lines_map.values():
                                    x0 = min(w[0] for w in line_words)
                                    y0 = min(w[1] for w in line_words)
                                    x1 = max(w[2] for w in line_words)
                                    y1 = max(w[3] for w in line_words)
                                    
                                    rect = fitz.Rect(x0, y0, x1, y1)
                                    annot = page.add_highlight_annot(rect)
                                    if annot:
                                        annot.update()
                                
                    annotated_data = pdf_doc.write()
                    pdf_doc.close()
                    data = annotated_data
            except Exception as e:
                logger.error(f"Failed to dynamically highlight PDF chunk {highlight_chunk_id}: {e}")

        # 3. Stream highlighted PDF bytes
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={doc.title}.pdf"}
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")
    except Exception as e:
        logger.error(f"Failed to retrieve and serve document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
