import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.dependencies import get_db_session
from app.core.config import settings
from app.providers.factory import create_embedding_provider
from app.core.embedding_selection import active_embedding_provider
from app.schemas.documents import DocumentIngestRequest, DocumentIngestResponse, CategoryConfigRequest, DocumentConfirmedIngestRequest
from app.storage.models import DBDocument, DBChunk
from app.api.identity import Principal, get_principal, require_manager
from app.retrieval.access import access_context, visible_document, safe_data_path
from app.retrieval.filters import document_filters, eligibility_filters, exact_value
from app.storage.vector_store import write_chunks
from app.core.model_selection import model_provider
from app.core.model_config import ModelError

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache or reuse provider instance
embedding_provider = create_embedding_provider()

# Global state for re-indexing progress tracking
reindex_progress = {
    "status": "idle",       # "idle" | "running" | "completed" | "failed"
    "type": None,           # "reindex_full" | "reindex_fast"
    "total_files": 0,
    "processed_files": 0,
    "current_file": None,
    "phase": None,          # "clearing_db" | "scanning_files" | "analyzing" | "ingesting"
    "error": None
}


@router.post("/ingest", dependencies=[Depends(require_manager)], response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(require_manager),
) -> DocumentIngestResponse:
    """Ingest a single document using the active index's embedding space.

    This represents the core ingestion flow in Phase 0.
    """
    try:
        # Generate embedding vector
        logger.info(f"Generating embeddings for document: {request.title}")
        document_provider = active_embedding_provider(db, principal.tenant_id, fallback=embedding_provider)
        document_embeddings = await document_provider.embed_documents([request.content])
        if len(document_embeddings) != 1:
            raise ValueError("Embedding provider did not return exactly one document embedding.")
        embedding = document_embeddings[0]
    except ModelError:
        raise
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        raise HTTPException(
            status_code=500,
            detail="Document embedding generation failed.",
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
        db.flush()

        # Store DBChunk
        import uuid
        chunk_id = uuid.uuid4()
        write_chunks(db, [{"chunk_id": chunk_id, "document_id": doc.document_id,
            "chunk_index": 0, "content": request.content, "embedding": embedding,
            "language": request.language, "security_acl": request.security_acl,
            "metadata_json": request.metadata_json}], document_provider.profile)
        db.commit()

        logger.info(f"Ingested document and chunk successfully. Doc ID: {doc.document_id}")
        return DocumentIngestResponse(
            document_id=str(doc.document_id),
            chunk_id=str(chunk_id),
            title=doc.title,
            status="ingested",
        )
    except ModelError:
        raise
    except Exception as e:
        logger.error(f"Database insertion failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database insertion failed: {str(e)}",
        )


@router.get("/list")
async def list_documents(
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(get_principal),
):
    """List all ingested documents and their chunk counts, respecting security ACL allowed groups."""
    try:
        context = access_context(principal)
        docs = db.query(DBDocument).filter(
            *document_filters(context, db.bind.dialect.name)
        ).order_by(DBDocument.ingested_at.desc()).all()
        result = []
        for doc in docs:
            chunk_count = db.query(DBChunk).join(DBDocument).filter(
                DBChunk.document_id == doc.document_id,
                *eligibility_filters(context, db.bind.dialect.name, metadata=False)
            ).count()
            result.append({
                "document_id": str(doc.document_id),
                "title": doc.title,
                "source_uri": doc.source_uri,
                "source_type": doc.source_type,
                "document_type": doc.document_type,
                "language": doc.language,
                "freshness_status": doc.freshness_status,
                "ingested_at": doc.ingested_at.isoformat(),
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "chunk_count": chunk_count,
                "security_acl": doc.security_acl,
                "metadata_json": doc.metadata_json,
            })
        return result
    except ModelError:
        raise
    except Exception as e:
        logger.error(f"Failed to query document list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/view/{document_id}")
async def view_document(
    document_id: str,
    db: Session = Depends(get_db_session),
    highlight_chunk_id: Optional[str] = None,
    principal: Principal = Depends(get_principal),
):
    """Fetch the document PDF file from local storage or Azure Blob, highlight cited RAG chunk if requested, and serve it."""
    from fastapi.responses import StreamingResponse
    from app.providers.blob_storage import BlobStorageProvider
    import io
    import os
    import uuid

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")

    try:
        doc = visible_document(db, doc_uuid, principal, full_document=True)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        # 1. Fetch raw PDF file bytes
        data = None

        def strip_diacritics(text: str) -> str:
            import unicodedata
            normalized = unicodedata.normalize('NFD', text)
            return "".join(c for c in normalized if unicodedata.category(c) != 'Mn').lower().strip()

        if doc.source_type == "azure_blob":
            uri_parts = doc.source_uri.replace("azure://", "").split("/", 1)
            if len(uri_parts) < 2:
                container_name = settings.AZURE_BLOB_CONTAINER_ORIGINALS or "originals"
                blob_name = uri_parts[0]
            else:
                container_name = uri_parts[0]
                blob_name = uri_parts[1]

            if container_name != settings.AZURE_BLOB_CONTAINER_ORIGINALS:
                raise HTTPException(404, "Document source is outside the configured tenant container.")

            # Server-side Blob Cache check for ultra-fast serving
            import tempfile
            cache_dir = os.path.join(tempfile.gettempdir(), "dolphin_blob_cache")
            os.makedirs(cache_dir, exist_ok=True)
            import hashlib
            cache_identity = "|".join([
                settings.TENANT_ID, settings.APP_ENV, settings.AZURE_STORAGE_ACCOUNT or "",
                container_name, blob_name, str(doc.document_id), doc.checksum or "",
            ])
            cache_file = os.path.join(cache_dir, hashlib.sha256(cache_identity.encode()).hexdigest() + ".pdf")

            if os.path.exists(cache_file):
                logger.info(f"Serving blob '{blob_name}' from server local cache ({cache_file})...")
                with open(cache_file, "rb") as f:
                    data = f.read()
            else:
                blob_provider = BlobStorageProvider()
                if blob_provider.is_configured():
                    try:
                        logger.info(f"Downloading blob '{blob_name}' from container '{container_name}'...")
                        data = await blob_provider.download_blob(container_name, blob_name)
                    except Exception as blob_err:
                        logger.warning(f"Exact Azure Blob download failed for '{blob_name}': {blob_err}. Attempting diacritic-fuzzy cloud search...")
                        try:
                            container_client = blob_provider.client.get_container_client(container_name)
                            target_norm = strip_diacritics(blob_name)
                            matched_blob_name = None
                            for b in container_client.list_blobs():
                                if strip_diacritics(b.name) == target_norm:
                                    matched_blob_name = b.name
                                    break
                            if matched_blob_name:
                                logger.info(f"Found cloud blob diacritic match '{matched_blob_name}' for target '{blob_name}'...")
                                data = await blob_provider.download_blob(container_name, matched_blob_name)
                        except Exception as fuzzy_err:
                            logger.warning(f"Fuzzy cloud search failed: {fuzzy_err}")

                    if data:
                        # Persist to local cache for instant sub-millisecond future responses
                        try:
                            with open(cache_file, "wb") as f:
                                f.write(data)
                            logger.info(f"Successfully cached blob '{blob_name}' to {cache_file}.")
                        except Exception as cache_err:
                            logger.warning(f"Could not save blob to cache: {cache_err}")

        if data is None:
            # Fallback to local file read
            raw_uri_path = doc.source_uri.replace("azure://", "").replace("file://", "")
            if "/" in raw_uri_path and not raw_uri_path.startswith("/"):
                # strip container name prefix if azure://
                parts = raw_uri_path.split("/", 1)
                if len(parts) > 1:
                    raw_uri_path = parts[1]

            local_path = safe_data_path(raw_uri_path) or safe_data_path(os.path.join("data", raw_uri_path))
            if local_path is None:
                raise HTTPException(404, "Document source is outside the data directory.")
            if not os.path.isabs(local_path):
                data_dir = os.path.abspath("data")
                local_path = os.path.join(data_dir, local_path)

            if not os.path.exists(local_path):
                data_dir = os.path.abspath("data")
                filename = os.path.basename(local_path)
                filename_norm = strip_diacritics(filename)

                # Recursive fallback search inside the data folder with exact & diacritic-fuzzy matching
                found = False
                for root, _, files in os.walk(data_dir):
                    if filename in files:
                        local_path = os.path.join(root, filename)
                        found = True
                        break
                    for f in files:
                        if strip_diacritics(f) == filename_norm:
                            local_path = os.path.join(root, f)
                            found = True
                            break
                    if found:
                        break

                if not found:
                    raise HTTPException(status_code=404, detail=f"PDF document file not found in Blob storage or local disk: {filename}")

            if safe_data_path(local_path) is None:
                raise HTTPException(404, "Document source is outside the data directory.")
            with open(local_path, "rb") as f:
                data = f.read()

        # 2. Apply dynamic PDF text highlighting using PyMuPDF if chunk ID is provided
        if highlight_chunk_id:
            try:
                chunk_uuid = uuid.UUID(highlight_chunk_id)
                chunk = db.query(DBChunk).join(DBDocument).filter(
                    DBChunk.chunk_id == chunk_uuid, DBChunk.document_id == doc_uuid,
                    *eligibility_filters(access_context(principal), db.bind.dialect.name, metadata=False)
                ).first()
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
            except ModelError:
                raise
            except Exception as e:
                logger.error(f"Failed to dynamically highlight PDF chunk {highlight_chunk_id}: {e}")

        # 3. Stream highlighted PDF bytes
        from urllib.parse import quote
        safe_filename = quote(f"{doc.title}.pdf")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}"}
        )

    except ModelError:
        raise
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Failed to retrieve and serve document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories(db: Session = Depends(get_db_session)):
    """Read the dynamic classification configuration from Blob Storage or disk."""
    from app.ingestion.tagger import MetadataTagger
    tagger = MetadataTagger(db_session=db)
    return await tagger.load_config()


@router.post("/categories", dependencies=[Depends(require_manager)])
async def update_categories(request: CategoryConfigRequest, db: Session = Depends(get_db_session)):
    """Save the updated classification configuration to Blob Storage and disk, and execute migrations if any."""
    from app.ingestion.tagger import MetadataTagger
    tagger = MetadataTagger(db_session=db)
    
    # 1. Load the old config to detect group/role renames
    try:
        old_config = await tagger.load_config()
    except ModelError:
        raise
    except Exception as e:
        logger.warning(f"Could not load old config for rename propagation: {e}")
        old_config = {"categories": []}
        
    old_categories = {c["key"]: c for c in old_config.get("categories", [])}
    
    # Track group/role renames
    renames = {}
    for new_cat in request.categories:
        old_cat = old_categories.get(new_cat.key)
        if old_cat:
            # Determine old role name
            old_role = old_cat.get("role_name")
            if not old_role:
                non_mgmt = [g for g in old_cat.get("allowed_groups", []) if g != "Management"]
                old_role = non_mgmt[0] if non_mgmt else old_cat["key"]
            
            # Determine new role name
            new_role = new_cat.role_name
            if not new_role:
                non_mgmt = [g for g in new_cat.allowed_groups if g != "Management"]
                new_role = non_mgmt[0] if non_mgmt else new_cat.key
            
            if old_role and new_role and old_role != new_role:
                renames[old_role] = new_role
                logger.info(f"Group rename detected: {old_role} -> {new_role}")

    if renames:
        for new_cat in request.categories:
            updated_groups = []
            for g in new_cat.allowed_groups:
                updated_groups.append(renames.get(g, g))
            new_cat.allowed_groups = updated_groups
            
    # Save the config (excluding category_migrations since it shouldn't persist in json)
    config_dict = request.model_dump(exclude={"category_migrations"})
    await tagger.save_config(config_dict)
    
    # Process category migrations in database
    if request.category_migrations:
        for deleted_key, replacement_key in request.category_migrations.items():
            logger.info(f"Migrating documents from category {deleted_key} to {replacement_key}")
            
            # Find the allowed groups of the replacement category in the request
            replacement_cat = next((c for c in request.categories if c.key == replacement_key), None)
            if not replacement_cat:
                logger.warning(f"Replacement category {replacement_key} not found in the new configuration.")
                continue
                
            allowed_groups = replacement_cat.allowed_groups
            security_acl_val = {"allowed_groups": allowed_groups}
            
            # Fetch and update all documents belonging to the deleted category key
            documents_to_migrate = db.query(DBDocument).filter(exact_value(DBDocument.tenant_id, settings.TENANT_ID, db.bind.dialect.name)).all()
            migrated_count = 0
            from sqlalchemy.orm.attributes import flag_modified
            for doc in documents_to_migrate:
                if doc.metadata_json and doc.metadata_json.get("department") == deleted_key:
                    # Update metadata
                    meta = dict(doc.metadata_json)
                    meta["department"] = replacement_key
                    doc.metadata_json = meta
                    flag_modified(doc, "metadata_json")
                    
                    # Update security ACL on document
                    doc.security_acl = security_acl_val
                    flag_modified(doc, "security_acl")
                    
                    # Fetch and update security ACL and department on its chunks
                    chunks = db.query(DBChunk).filter(DBChunk.document_id == doc.document_id).all()
                    for chunk in chunks:
                        chunk.security_acl = security_acl_val
                        flag_modified(chunk, "security_acl")
                        if chunk.metadata_json:
                            chunk_meta = dict(chunk.metadata_json)
                            chunk_meta["department"] = replacement_key
                            chunk.metadata_json = chunk_meta
                            flag_modified(chunk, "metadata_json")
                            
                    migrated_count += 1
            
            if migrated_count > 0:
                db.commit()
                logger.info(f"Successfully migrated {migrated_count} documents from {deleted_key} to {replacement_key}")
                
    # Propagate allowed groups changes to existing documents/chunks for ALL categories in the configuration
    for cat in request.categories:
        allowed_groups = cat.allowed_groups
        security_acl_val = {"allowed_groups": allowed_groups}
        
        # Query all documents in this category
        docs_to_update = db.query(DBDocument).filter(exact_value(DBDocument.tenant_id, settings.TENANT_ID, db.bind.dialect.name)).all()
        updated_count = 0
        for doc in docs_to_update:
            if doc.metadata_json and doc.metadata_json.get("department") == cat.key:
                if doc.security_acl != security_acl_val:
                    doc.security_acl = security_acl_val
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(doc, "security_acl")
                    
                    for chunk in db.query(DBChunk).filter(DBChunk.document_id == doc.document_id).all():
                        chunk.security_acl = security_acl_val
                        flag_modified(chunk, "security_acl")
                    updated_count += 1
        if updated_count > 0:
            db.commit()
            logger.info(f"Propagated config allowed_groups to {updated_count} documents in category {cat.key}")
                
    return {"status": "success", "message": "Kategorie byly úspěšně uloženy."}


class DocumentUpdateMetadataRequest(BaseModel):
    document_id: str
    title: str
    date: str
    category: str
    freshness_status: str
    language: str = "cs"


@router.post("/update-metadata", dependencies=[Depends(require_manager)])
async def update_document_metadata(
    request: DocumentUpdateMetadataRequest,
    db: Session = Depends(get_db_session)
):
    """Update metadata, category, allowed groups and freshness status for an existing document and its chunks in the database."""
    import uuid
    from sqlalchemy.orm.attributes import flag_modified
    from app.ingestion.tagger import MetadataTagger
    
    try:
        doc_uuid = uuid.UUID(request.document_id)
        doc = db.query(DBDocument).filter(DBDocument.document_id == doc_uuid, exact_value(DBDocument.tenant_id, settings.TENANT_ID, db.bind.dialect.name)).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Dokument nenalezen.")
            
        # 1. Update document title, freshness and language
        doc.title = request.title
        doc.freshness_status = request.freshness_status
        doc.language = request.language
        
        # Update metadata_json
        meta = dict(doc.metadata_json) if doc.metadata_json else {}
        meta["department"] = request.category
        meta["created_at"] = f"{request.date}T00:00:00"
        doc.metadata_json = meta
        flag_modified(doc, "metadata_json")
        
        # 2. Resolve security ACL groups based on the selected category's allowed_groups
        tagger = MetadataTagger(db_session=db)
        config = await tagger.load_config()
        
        category_item = next((c for c in config.get("categories", []) if c["key"] == request.category), None)
        if category_item:
            allowed_groups = category_item.get("allowed_groups", [])
        else:
            allowed_groups = ["Management"]
            
        security_acl_val = {"allowed_groups": allowed_groups}
        doc.security_acl = security_acl_val
        flag_modified(doc, "security_acl")
        
        # 3. Update all chunks of this document to match
        chunks = db.query(DBChunk).filter(DBChunk.document_id == doc_uuid).all()
        for chunk in chunks:
            chunk.freshness_status = request.freshness_status
            chunk.security_acl = security_acl_val
            flag_modified(chunk, "security_acl")
            chunk.language = request.language
            
            chunk_meta = dict(chunk.metadata_json) if chunk.metadata_json else {}
            chunk_meta["department"] = request.category
            chunk_meta["created_at"] = f"{request.date}T00:00:00"
            chunk.metadata_json = chunk_meta
            flag_modified(chunk, "metadata_json")
            
        db.commit()
        logger.info(f"Successfully updated document {doc_uuid} metadata to category {request.category} and freshness {request.freshness_status}")
        return {"status": "success", "message": "Metadata dokumentu byla úspěšně upravena."}
        
    except ModelError:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update document metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-draft", dependencies=[Depends(require_manager)])
async def analyze_draft(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
    classification_model_id: Optional[str] = Form(None),
    principal: Principal = Depends(require_manager),
):
    """Save upload to temp location and run metadata auto-tagger LLM analysis."""
    import os
    import shutil
    import uuid
    from app.ingestion.tagger import MetadataTagger

    temp_dir = os.path.abspath("data/temp_drafts")
    os.makedirs(temp_dir, exist_ok=True)

    original_filename = os.path.basename((file.filename or "upload").replace("\\", "/"))
    unique_filename = f"{uuid.uuid4()}_{original_filename}"
    temp_path = os.path.join(temp_dir, unique_filename)

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        provider = model_provider(db, principal.tenant_id, "classification", classification_model_id, principal)
        tagger = MetadataTagger(db_session=db, llm_provider=provider)
        suggestions = await tagger.analyze_file(temp_path)
        suggestions["classification_model_id"] = provider.profile.id
        import json, hashlib
        with open(temp_path, "rb") as content:
            checksum = hashlib.sha256(content.read()).hexdigest()
        with open(temp_path + ".model.json", "w", encoding="utf-8") as receipt:
            json.dump({"tenant_id": principal.tenant_id, "user_id": str(principal.user_id),
                       "model_id": provider.profile.id, "checksum": checksum}, receipt)
        
        # Restore original filename in the suggested title
        suggestions["title"] = os.path.splitext(original_filename)[0]
        
        # Append the temp file path for the confirmed ingest step
        suggestions["temp_file_path"] = temp_path
        
        return suggestions
    except ModelError:
        raise
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.error(f"Failed to analyze draft: {e}")
        raise HTTPException(status_code=500, detail=f"Chyba při analýze dokumentu: {str(e)}")


@router.post("/ingest-confirmed", dependencies=[Depends(require_manager)])
async def ingest_confirmed(
    request: DocumentConfirmedIngestRequest,
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(require_manager),
):
    """Ingest the document with confirmed/edited metadata and apply replacement archival rules."""
    import os
    import datetime
    from app.ingestion.pipeline import IngestionPipeline
    from app.ingestion.tagger import MetadataTagger

    if safe_data_path(request.temp_file_path) is None or not os.path.exists(request.temp_file_path):
        raise HTTPException(status_code=400, detail="Dočasný soubor nebyl nalezen. Nahrajte dokument znovu.")

    classification_id = None
    receipt_path = request.temp_file_path + ".model.json"
    if os.path.exists(receipt_path):
        import json, hashlib
        with open(receipt_path, encoding="utf-8") as receipt:
            provenance = json.load(receipt)
        with open(request.temp_file_path, "rb") as content:
            checksum = hashlib.sha256(content.read()).hexdigest()
        if (provenance.get("tenant_id") != principal.tenant_id or
                provenance.get("user_id") != str(principal.user_id) or provenance.get("checksum") != checksum):
            raise HTTPException(403, "Analýza dokumentu nepatří aktuálnímu uživateli nebo se dokument změnil.")
        classification_id = provenance["model_id"]
        if request.classification_model_id and request.classification_model_id != classification_id:
            raise HTTPException(422, "Změna klasifikačního modelu vyžaduje novou analýzu dokumentu.")
        model_provider(db, principal.tenant_id, "classification", classification_id, principal)
    elif request.classification_model_id:
        raise HTTPException(422, "Chybí záznam analýzy dokumentu. Spusťte analýzu znovu.")

    summary = model_provider(db, principal.tenant_id, "summary", request.summary_model_id, principal)

    try:
        # 1. Resolve security ACL and metadata from the selected category using config
        tagger = MetadataTagger(db_session=db)
        config = await tagger.load_config()
        
        # Find selected category configuration details
        category_item = None
        for cat in config.get("categories", []):
            if cat.get("key") == request.category:
                category_item = cat
                break
        
        if not category_item:
            allowed_groups = ["Management", "HR", "Finance", "User"]
        else:
            allowed_groups = category_item.get("allowed_groups", ["Management", "HR", "Finance", "User"])
            
        security_acl = {"allowed_groups": allowed_groups}

        # Format release date
        try:
            release_date = datetime.datetime.strptime(request.date, "%Y-%m-%d")
        except ValueError:
            release_date = datetime.datetime.utcnow()

        # Build metadata dictionary to be stored in DB
        metadata = {
            "department": request.category,
            "year": release_date.year,
            "created_at": release_date.isoformat(),
            "freshness_status": "current",
            "relationship_type": request.relationship.relationship_type,
        }
        if classification_id:
            metadata["classification_model_id"] = classification_id

        # Check and apply archival operations if it replaces an existing document
        target_doc = None
        if request.relationship.relationship_type == "replaces" and request.relationship.target_document_id:
            import uuid
            try:
                target_uuid = uuid.UUID(request.relationship.target_document_id)
                target_doc = db.query(DBDocument).filter(DBDocument.document_id == target_uuid, exact_value(DBDocument.tenant_id, settings.TENANT_ID, db.bind.dialect.name)).first()
                if target_doc:
                    logger.info(f"Archiving replaced document: {target_doc.title} (ID: {target_doc.document_id})")
                    
                    # Update target document status to archived
                    target_doc.freshness_status = "archived"
                    if not target_doc.metadata_json:
                        target_doc.metadata_json = {}
                    target_doc.metadata_json["replaced_by_document_title"] = request.title
                    
                    # Update target document's chunks to archived
                    db.query(DBChunk).filter(DBChunk.document_id == target_uuid).update(
                        {"freshness_status": "archived"}
                    )
                    
                    # Add replaces references to new document's metadata
                    metadata["replaces_document_id"] = str(target_uuid)
                    metadata["replaces_document_title"] = target_doc.title
                    
                    # Keep DB changes in active transaction block
                    db.flush()
            except ModelError:
                raise
            except Exception as e:
                logger.error(f"Error executing archival process for replaced document: {e}")
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Nepodařilo se archivovat původní dokument: {str(e)}")

        elif request.relationship.relationship_type == "modifies" and request.relationship.target_document_id:
            metadata["modifies_document_id"] = request.relationship.target_document_id
            metadata["modifies_document_title"] = request.relationship.target_document_title

        # 2. Run standard ingestion pipeline
        pipeline = IngestionPipeline(db, summary_provider=summary, principal=principal)
        
        # We rename the temp file to the confirmed final title during ingestion to clean up filename
        _, ext = os.path.splitext(request.original_filename)
        cleaned_filename = f"{request.title}{ext}"
        
        # Safe character replacement to prevent file path injection
        cleaned_filename = "".join([c for c in cleaned_filename if c.isalnum() or c in (".", "_", "-")]).strip()
        if not cleaned_filename:
            cleaned_filename = request.original_filename
            
        confirmed_file_path = os.path.join(os.path.dirname(request.temp_file_path), cleaned_filename)
        if safe_data_path(confirmed_file_path) is None:
            raise HTTPException(400, "Invalid confirmed file path.")
        if os.path.exists(confirmed_file_path):
            os.remove(confirmed_file_path)
        os.rename(request.temp_file_path, confirmed_file_path)

        try:
            doc = await pipeline.ingest_file(
                file_path=confirmed_file_path,
                document_type="policy",
                security_acl=security_acl,
                metadata_json=metadata,
                language=request.language,
            )
            
            # Update the title of the document in the DB to match confirmed title exactly
            doc.title = request.title
            doc.created_at = release_date
            
            # If target doc is replaced, link the new doc ID into its metadata
            if target_doc:
                target_doc.metadata_json["replaced_by_document_id"] = str(doc.document_id)
                db.add(target_doc)
                
            db.commit()
            
            return {
                "status": "success",
                "document_id": str(doc.document_id),
                "title": doc.title,
                "message": f"Dokument '{doc.title}' byl úspěšně naimportován."
            }
        finally:
            # Clean up the renamed file in the temp drafts directory
            if os.path.exists(confirmed_file_path):
                os.remove(confirmed_file_path)

    except ModelError:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error in confirmed ingestion endpoint: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Chyba při dokončení ingestu: {str(e)}")
    finally:
        if os.path.exists(receipt_path):
            os.remove(receipt_path)
        # Clean up original temp upload file if it still exists
        if os.path.exists(request.temp_file_path):
            os.remove(request.temp_file_path)


async def run_reindex_full_task(tenant_id: str | None = None, model_selection=None, principal=None):
    from app.ingestion.refresh import refresh_files, refresh_documents
    tenant_id = tenant_id or settings.TENANT_ID
    reindex_progress.update(status="running", type="reindex_full", phase="scanning_files",
                            total_files=0, processed_files=0, current_file=None, error=None)
    try:
        files = refresh_files(tenant_id)
        await refresh_documents(tenant_id, files, reindex_progress, model_selection=model_selection, principal=principal)
        reindex_progress["status"] = "completed"
    except Exception:
        logger.exception("Tenant full refresh failed; stale cleanup was not completed.")
        reindex_progress.update(status="failed", error="Refresh failed; inspect server logs. Remaining corpus was retained.", phase=None)


@router.get("/reindex-progress", dependencies=[Depends(require_manager)])
async def get_reindex_progress():
    """Get the current progress of the background re-indexing task."""
    return reindex_progress


@router.post("/reindex-full", dependencies=[Depends(require_manager)])
async def reindex_full_endpoint(
    background_tasks: BackgroundTasks,
    selection: Optional[Dict[str, Optional[str]]] = None,
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(require_manager),
):
    """Trigger background full re-indexing of all local documents in the data folder (with LLM metadata analysis)."""
    for purpose in ("summary", "classification"):
        model_provider(db, principal.tenant_id, purpose, (selection or {}).get(purpose + "_model_id"), principal)
    background_tasks.add_task(run_reindex_full_task, principal.tenant_id, selection or {}, principal)
    return {"status": "success", "message": "Znovunačtení a reindexace všech dokumentů (s analýzou metadat) byla spuštěna na pozadí."}


async def run_reindex_all_task(tenant_id: str | None = None, model_selection=None, principal=None):
    logger.info("Starting background fast re-indexing (re-chunking) of all documents...")
    import os
    from app.storage.db import SessionLocal
    from app.storage.models import DBDocument, DBChunk
    from app.ingestion.pipeline import IngestionPipeline
    tenant_id = tenant_id or settings.TENANT_ID
    if tenant_id != settings.TENANT_ID:
        raise ValueError("Reindex tenant must match the configured tenant.")

    # Reset progress state
    reindex_progress["status"] = "running"
    reindex_progress["type"] = "reindex_fast"
    reindex_progress["phase"] = "scanning"
    reindex_progress["total_files"] = 0
    reindex_progress["processed_files"] = 0
    reindex_progress["current_file"] = None
    reindex_progress["error"] = None

    db = SessionLocal()
    try:
        from sqlalchemy import select
        docs = db.execute(select(DBDocument).where(
            exact_value(DBDocument.tenant_id, tenant_id, db.bind.dialect.name)
        )).scalars().all()
        
        if not docs:
            logger.info("No documents found in database for fast re-indexing.")
            reindex_progress["status"] = "completed"
            reindex_progress["phase"] = None
            return

        reindex_progress["total_files"] = len(docs)
        reindex_progress["phase"] = "ingesting"

        selection = model_selection or {}
        summary = model_provider(db, tenant_id, "summary", selection.get("summary_model_id"), principal) if model_selection is not None else None
        pipeline = IngestionPipeline(db, summary_provider=summary, principal=principal) if summary else IngestionPipeline(db)

        for idx, doc in enumerate(docs):
            reindex_progress["current_file"] = doc.title
            reindex_progress["processed_files"] = idx
            
            uri = doc.source_uri
            relative_path = uri
            if uri.startswith("file://"):
                relative_path = uri[7:]
            elif uri.startswith("azure://"):
                parts = uri.split("/", 3)
                if len(parts) > 3:
                    relative_path = parts[3]
            
            file_path = os.path.abspath(os.path.join("data", relative_path))
            if safe_data_path(file_path) is None:
                raise ValueError("Reindex source is outside the data directory.")
            if not os.path.exists(file_path):
                # A basename match elsewhere in data/ may belong to another tenant.
                logger.warning("Exact source missing for document %s; retaining its chunks.", doc.document_id)
                reindex_progress["error"] = "An exact document source is missing; its existing chunks were retained."
                continue

            logger.info(f"Fast re-indexing document: {doc.title} from {file_path}")
            try:
                if safe_data_path(file_path) is None:
                    raise ValueError("Reindex source is outside the data directory.")
                extracted_pages = pipeline.extractor.extract(file_path)
                chunks = pipeline.splitter.split_pages(extracted_pages)
                if not chunks:
                    logger.warning(f"No text split from document: {doc.title}. Skipping.")
                    continue
                
                chunk_texts = [chunk.content for chunk in chunks]
                embeddings = await pipeline.embedding_provider.embed_documents(chunk_texts)
                
                db.query(DBChunk).filter(DBChunk.document_id == doc.document_id,
                    exact_value(DBChunk.tenant_id, tenant_id, db.bind.dialect.name)).delete()
                
                replacement_metadata = dict(doc.metadata_json or {})
                replacement_metadata.pop("summary_model_id", None)
                if pipeline.splitter.enrich_with_summary and getattr(pipeline.summary_provider, "profile", None):
                    replacement_metadata["summary_model_id"] = pipeline.summary_provider.profile.id
                    doc.metadata_json = replacement_metadata
                write_chunks(db, [{"document_id": doc.document_id, "chunk_index": chunk_idx,
                    "content": chunk.content, "embedding": embeddings[chunk_idx],
                    "language": doc.language, "section_title": chunk.section_title,
                    "page_number": chunk.page_number, "security_acl": doc.security_acl,
                    "metadata_json": replacement_metadata, "freshness_status": doc.freshness_status}
                    for chunk_idx, chunk in enumerate(chunks)], pipeline.embedding_provider.profile)
                
                db.commit()
                logger.info(f"Successfully fast-reindexed document: {doc.title}")
            except Exception as inner_e:
                db.rollback()
                logger.error(f"Failed to fast-reindex document {doc.title}: {inner_e}")
                reindex_progress["error"] = f"Failed for {doc.title}: {inner_e}"

        reindex_progress["status"] = "failed" if reindex_progress["error"] else "completed"
        reindex_progress["processed_files"] = len(docs)
        reindex_progress["current_file"] = None
        reindex_progress["phase"] = None

    except ModelError:
        raise
    except Exception as e:
        logger.error(f"Fast re-indexing failed: {e}")
        reindex_progress["status"] = "failed"
        reindex_progress["error"] = str(e)
    finally:
        db.close()
        logger.info("Background fast re-indexing finished.")


@router.post("/reindex-all", dependencies=[Depends(require_manager)])
async def reindex_all_endpoint(
    background_tasks: BackgroundTasks,
    selection: Optional[Dict[str, Optional[str]]] = None,
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(require_manager),
):
    """Trigger background fast re-indexing (re-chunking and embedding only) of all active documents."""
    for purpose in ("summary", "classification"):
        model_provider(db, principal.tenant_id, purpose, (selection or {}).get(purpose + "_model_id"), principal)
    background_tasks.add_task(run_reindex_all_task, principal.tenant_id, selection or {}, principal)
    return {"status": "success", "message": "Znovunačtení a reindexace všech dokumentů (chunky a embeddingy) byla spuštěna na pozadí."}


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(get_principal),
):
    """Retrieve all chunks belonging to a document, ordered by chunk_index, to show a chunking preview in the frontend."""
    import uuid
    from app.storage.models import DBChunk, DBDocument
    
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")
        
    doc = visible_document(db, doc_uuid, principal, full_document=False)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    chunks = (
        db.query(DBChunk)
        .join(DBDocument)
        .filter(DBChunk.document_id == doc_uuid,
                *eligibility_filters(access_context(principal), db.bind.dialect.name, metadata=False))
        .order_by(DBChunk.chunk_index.asc())
        .all()
    )
    
    return [
        {
            "chunk_id": str(c.chunk_id),
            "chunk_index": c.chunk_index,
            "content": c.content,
            "page_number": c.page_number,
            "section_title": c.section_title,
        }
        for c in chunks
    ]


@router.post("/preview-chunks")
async def preview_document_chunks(
    payload: Dict[str, Any],
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(get_principal),
):
    """Simulate and preview text segmentation into chunks using custom chunk_size and chunk_overlap without writing to DB."""
    import uuid
    import os
    from app.storage.models import DBDocument
    from app.ingestion.extraction import DocumentExtractor
    from app.ingestion.chunking import RecursiveCharacterTextSplitter
    
    document_id = payload.get("document_id")
    chunk_size = payload.get("chunk_size", 1500)
    chunk_overlap = payload.get("chunk_overlap", 250)
    chunk_cross_page = payload.get("chunk_cross_page", False)
    overlap_cross_page = payload.get("overlap_cross_page", False)
    chunk_splitter_type = payload.get("chunk_splitter_type", "recursive")
    chunking_strategy = payload.get("chunking_strategy", "standard")
    enrich_with_summary = payload.get("enrich_with_summary", False)
    summary_custom_prompt = payload.get("summary_custom_prompt", "")
    force_ai = payload.get("force_ai", False)
    semantic_params = payload.get("semantic_params")
    structure_params = payload.get("structure_params")
    token_params = payload.get("token_params")
    agentic_params = payload.get("agentic_params")
    
    llm_provider = model_provider(db, principal.tenant_id, "classification", principal=principal) if chunking_strategy == "agentic" and force_ai else None
    
    if not document_id:
        raise HTTPException(status_code=400, detail="Missing document_id")
        
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")
        
    doc = visible_document(db, doc_uuid, principal, full_document=True)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    # Resolve file path
    uri = doc.source_uri
    relative_path = uri
    if uri.startswith("file://"):
        relative_path = uri[7:]
    elif uri.startswith("azure://"):
        parts = uri.split("/", 3)
        if len(parts) > 3:
            relative_path = parts[3]
            
    file_path = safe_data_path(os.path.join("data", relative_path))
    if file_path is None:
        raise HTTPException(404, "Document source is outside the data directory.")
    if not os.path.exists(file_path):
        # Fallback search
        found_path = None
        data_dir = os.path.abspath("data")
        if os.path.exists(data_dir):
            basename = os.path.basename(relative_path)
            for root, dirs, files in os.walk(data_dir):
                if basename in files:
                    found_path = os.path.join(root, basename)
                    break
        if found_path:
            file_path = found_path
        else:
            raise HTTPException(status_code=404, detail=f"File not found on server.")
            
    if safe_data_path(file_path) is None:
        raise HTTPException(404, "Document source is outside the data directory.")
    # Extract pages and run custom splitter
    extractor = DocumentExtractor()
    pages = extractor.extract(file_path)
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunk_cross_page=chunk_cross_page,
        overlap_cross_page=overlap_cross_page,
        chunk_splitter_type=chunk_splitter_type,
        chunking_strategy=chunking_strategy,
        enrich_with_summary=enrich_with_summary,
        summary_custom_prompt=summary_custom_prompt,
        semantic_params=semantic_params,
        structure_params=structure_params,
        token_params=token_params,
        agentic_params=agentic_params,
        embedding_provider=active_embedding_provider(db, principal.tenant_id, fallback=embedding_provider),
        llm_provider=llm_provider,
        summary_provider=model_provider(db, principal.tenant_id, "summary", payload.get("summary_model_id"), principal) if enrich_with_summary else None,
        strict_summary=bool(force_ai and enrich_with_summary),
    )
    chunks = splitter.split_pages(pages, force_ai=force_ai)
    
    return [
        {
            "chunk_index": c.index,
            "content": c.content,
            "page_number": c.page_number,
            "section_title": c.section_title
        }
        for c in chunks
    ]



