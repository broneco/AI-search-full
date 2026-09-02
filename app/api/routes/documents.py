import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.dependencies import get_db_session
from app.api.routes.auth import decode_token
from app.core.config import settings
from app.providers.azure_openai import AzureOpenAIEmbeddingProvider
from app.schemas.documents import DocumentIngestRequest, DocumentIngestResponse, CategoryConfigRequest, DocumentConfirmedIngestRequest
from app.storage.models import DBDocument, DBChunk

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache or reuse provider instance
embedding_provider = AzureOpenAIEmbeddingProvider()

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
        user_groups_str = x_user_groups
        if not user_groups_str:
            auth_header = http_request.headers.get("Authorization") or http_request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    payload = decode_token(token)
                    groups_list = payload.get("groups", [])
                    if groups_list:
                        user_groups_str = ",".join(groups_list)
                except Exception as token_err:
                    logger.debug(f"Could not decode token for groups extraction: {token_err}")

        user_groups_str = user_groups_str or "User"
        acl_groups = [g.strip() for g in user_groups_str.split(",") if g.strip()]
        tenant_id = (settings.TENANT_ID or "dolphin").lower()
        tenant_base = tenant_id.split("-")[0]
        tenant_variants = list(set([tenant_id, tenant_base, f"{tenant_base}-dev", f"{tenant_base}-prod"]))

        docs = (
            db.query(DBDocument)
            .filter(DBDocument.tenant_id.in_(tenant_variants))
            .order_by(DBDocument.ingested_at.desc())
            .all()
        )
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
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "chunk_count": chunk_count,
                "security_acl": doc.security_acl,
                "metadata_json": doc.metadata_json,
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
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")

    try:
        doc = db.query(DBDocument).filter(DBDocument.document_id == doc_uuid).first()
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

            # Server-side Blob Cache check for ultra-fast serving
            import tempfile
            cache_dir = os.path.join(tempfile.gettempdir(), "dolphin_blob_cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f"{doc.document_id}.pdf")

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

            local_path = raw_uri_path
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
        from urllib.parse import quote
        safe_filename = quote(f"{doc.title}.pdf")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}"}
        )

    except Exception as e:
        logger.error(f"Failed to retrieve and serve document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories(db: Session = Depends(get_db_session)):
    """Read the dynamic classification configuration from Blob Storage or disk."""
    from app.ingestion.tagger import MetadataTagger
    tagger = MetadataTagger(db_session=db)
    return await tagger.load_config()


@router.post("/categories")
async def update_categories(request: CategoryConfigRequest, db: Session = Depends(get_db_session)):
    """Save the updated classification configuration to Blob Storage and disk, and execute migrations if any."""
    from app.ingestion.tagger import MetadataTagger
    tagger = MetadataTagger(db_session=db)
    
    # 1. Load the old config to detect group/role renames
    try:
        old_config = await tagger.load_config()
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
            documents_to_migrate = db.query(DBDocument).all()
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
        docs_to_update = db.query(DBDocument).all()
        updated_count = 0
        for doc in docs_to_update:
            if doc.metadata_json and doc.metadata_json.get("department") == cat.key:
                if doc.security_acl != security_acl_val:
                    doc.security_acl = security_acl_val
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(doc, "security_acl")
                    
                    db.query(DBChunk).filter(DBChunk.document_id == doc.document_id).update(
                        {"security_acl": security_acl_val}
                    )
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


@router.post("/update-metadata")
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
        doc = db.query(DBDocument).filter(DBDocument.document_id == doc_uuid).first()
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
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update document metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-draft")
async def analyze_draft(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session)
):
    """Save upload to temp location and run metadata auto-tagger LLM analysis."""
    import os
    import shutil
    import uuid
    from app.ingestion.tagger import MetadataTagger

    temp_dir = os.path.abspath("data/temp_drafts")
    os.makedirs(temp_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    temp_path = os.path.join(temp_dir, unique_filename)

    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        tagger = MetadataTagger(db_session=db)
        suggestions = await tagger.analyze_file(temp_path)
        
        # Restore original filename in the suggested title
        suggestions["title"] = os.path.splitext(file.filename)[0]
        
        # Append the temp file path for the confirmed ingest step
        suggestions["temp_file_path"] = temp_path
        
        return suggestions
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.error(f"Failed to analyze draft: {e}")
        raise HTTPException(status_code=500, detail=f"Chyba při analýze dokumentu: {str(e)}")


@router.post("/ingest-confirmed")
async def ingest_confirmed(
    request: DocumentConfirmedIngestRequest,
    db: Session = Depends(get_db_session)
):
    """Ingest the document with confirmed/edited metadata and apply replacement archival rules."""
    import os
    import datetime
    from app.ingestion.pipeline import IngestionPipeline
    from app.ingestion.tagger import MetadataTagger

    if not os.path.exists(request.temp_file_path):
        raise HTTPException(status_code=400, detail="Dočasný soubor nebyl nalezen. Nahrajte dokument znovu.")

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

        # Check and apply archival operations if it replaces an existing document
        target_doc = None
        if request.relationship.relationship_type == "replaces" and request.relationship.target_document_id:
            import uuid
            try:
                target_uuid = uuid.UUID(request.relationship.target_document_id)
                target_doc = db.query(DBDocument).filter(DBDocument.document_id == target_uuid).first()
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
            except Exception as e:
                logger.error(f"Error executing archival process for replaced document: {e}")
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Nepodařilo se archivovat původní dokument: {str(e)}")

        elif request.relationship.relationship_type == "modifies" and request.relationship.target_document_id:
            metadata["modifies_document_id"] = request.relationship.target_document_id
            metadata["modifies_document_title"] = request.relationship.target_document_title

        # 2. Run standard ingestion pipeline
        pipeline = IngestionPipeline(db)
        
        # We rename the temp file to the confirmed final title during ingestion to clean up filename
        _, ext = os.path.splitext(request.original_filename)
        cleaned_filename = f"{request.title}{ext}"
        
        # Safe character replacement to prevent file path injection
        cleaned_filename = "".join([c for c in cleaned_filename if c.isalnum() or c in (".", "_", "-")]).strip()
        if not cleaned_filename:
            cleaned_filename = request.original_filename
            
        confirmed_file_path = os.path.join(os.path.dirname(request.temp_file_path), cleaned_filename)
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

    except Exception as e:
        logger.error(f"Error in confirmed ingestion endpoint: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Chyba při dokončení ingestu: {str(e)}")
    finally:
        # Clean up original temp upload file if it still exists
        if os.path.exists(request.temp_file_path):
            os.remove(request.temp_file_path)


async def run_reindex_full_task():
    logger.info("Starting background full re-indexing of all documents...")
    import os
    import datetime
    from app.storage.db import SessionLocal, init_db, clear_document_data
    from app.ingestion.loaders.local import list_local_files
    from app.ingestion.pipeline import IngestionPipeline
    from app.ingestion.tagger import MetadataTagger
    from app.storage.models import DBDocument, DBChunk
    import uuid

    # Reset progress state
    reindex_progress["status"] = "running"
    reindex_progress["type"] = "reindex_full"
    reindex_progress["phase"] = "clearing_db"
    reindex_progress["total_files"] = 0
    reindex_progress["processed_files"] = 0
    reindex_progress["current_file"] = None
    reindex_progress["error"] = None

    # Use fresh db session context manager
    db = SessionLocal()
    try:
        # 1. Clear database
        try:
            clear_db()
        except Exception as e:
            logger.warning(f"Drop tables failed during re-indexing: {e}")

        # 2. Re-create tables
        init_db()

        tagger = MetadataTagger(db_session=db)
        config = await tagger.load_config()

        # 3. Scan data directories
        reindex_progress["phase"] = "scanning_files"
        tenant_id = settings.TENANT_ID.lower().split("-")[0]
        search_dirs = [
            os.path.abspath("data"),
            os.path.abspath(os.path.join("data - full backup", tenant_id)),
            os.path.abspath(os.path.join("data-full backup", tenant_id)),
            os.path.abspath(os.path.join("data", tenant_id)),
        ]
        files = []
        seen = set()
        for d in search_dirs:
            if os.path.exists(d):
                for f in list_local_files(d, extensions=[".pdf", ".txt"]):
                    if f not in seen:
                        seen.add(f)
                        files.append(f)

        if not files:
            logger.info("No documents found in data directories for re-indexing.")
            reindex_progress["status"] = "completed"
            reindex_progress["phase"] = None
            return

        reindex_progress["total_files"] = len(files)
        reindex_progress["phase"] = "analyzing"
        reindex_progress["processed_files"] = 0

        # 4. Phase A: Extract metadata for all files to sort them
        analyzed_docs = []
        for idx, file_path in enumerate(files):
            reindex_progress["current_file"] = os.path.basename(file_path)
            reindex_progress["processed_files"] = idx
            try:
                suggestions = await tagger.analyze_file(file_path)
                analyzed_docs.append({
                    "file_path": file_path,
                    "suggestions": suggestions
                })
            except Exception as e:
                logger.error(f"Failed to analyze file {file_path} during reindex phase A: {e}")

        # Helper key function to sort by date
        def get_sort_date(item):
            date_str = item["suggestions"].get("suggested_date")
            try:
                return datetime.datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                return datetime.datetime.min

        analyzed_docs.sort(key=get_sort_date)

        # 5. Phase B: Ingest in chronological order
        pipeline = IngestionPipeline(db)
        reindex_progress["phase"] = "ingesting"
        reindex_progress["processed_files"] = 0
        reindex_progress["total_files"] = len(analyzed_docs)

        for idx, item in enumerate(analyzed_docs):
            file_path = item["file_path"]
            sug = item["suggestions"]
            title = sug["title"]
            category_key = sug["suggested_category"]
            date_str = sug["suggested_date"]
            rel = sug["relationship"]

            reindex_progress["current_file"] = os.path.basename(file_path)
            reindex_progress["processed_files"] = idx

            logger.info(f"Re-indexing document in order: {title} (Date: {date_str})")

            # Resolve allowed groups
            category_item = None
            for cat in config.get("categories", []):
                if cat.get("key") == category_key:
                    category_item = cat
                    break

            if not category_item:
                allowed_groups = ["Management", "HR", "Finance", "User"]
            else:
                allowed_groups = category_item.get("allowed_groups", ["Management", "HR", "Finance", "User"])

            security_acl = {"allowed_groups": allowed_groups}

            # Parse date
            try:
                release_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                release_date = datetime.datetime.utcnow()

            # Metadata dict
            metadata = {
                "department": category_key,
                "year": release_date.year,
                "created_at": release_date.isoformat(),
                "freshness_status": "current",
                "relationship_type": rel.get("relationship_type", "none"),
            }

            # Calculate source folder relative to data_dir
            rel_dir = os.path.relpath(os.path.dirname(file_path), data_dir).replace("\\", "/")
            if rel_dir and rel_dir != ".":
                metadata["source_folder"] = rel_dir
                metadata["Zdroj dat"] = rel_dir

            # Check if replaces target
            rel_type = rel.get("relationship_type", "none")
            target_doc = None
            if rel_type == "replaces" and rel.get("target_document_id"):
                try:
                    target_uuid = uuid.UUID(rel.get("target_document_id"))
                    target_doc = db.query(DBDocument).filter(DBDocument.document_id == target_uuid).first()
                    if target_doc:
                        logger.info(f"Reindex: Archiving replaced document {target_doc.title}")
                        target_doc.freshness_status = "archived"
                        if not target_doc.metadata_json:
                            target_doc.metadata_json = {}
                        target_doc.metadata_json["replaced_by_document_title"] = title
                        
                        db.query(DBChunk).filter(DBChunk.document_id == target_uuid).update(
                            {"freshness_status": "archived"}
                        )
                        metadata["replaces_document_id"] = str(target_uuid)
                        metadata["replaces_document_title"] = target_doc.title
                        db.flush()
                except Exception as ex:
                    logger.error(f"Reindex relationship archival error: {ex}")

            elif rel_type == "modifies" and rel.get("target_document_id"):
                metadata["modifies_document_id"] = rel.get("target_document_id")
                metadata["modifies_document_title"] = rel.get("target_document_title")

            # Ingest
            try:
                doc = await pipeline.ingest_file(
                    file_path=file_path,
                    document_type="policy" if "policy" in file_path.lower() else "document",
                    security_acl=security_acl,
                    metadata_json=metadata,
                    language=sug.get("suggested_language", "cs"),
                )
                doc.title = title
                doc.created_at = release_date

                if target_doc:
                    target_doc.metadata_json["replaced_by_document_id"] = str(doc.document_id)
                    db.add(target_doc)

                db.commit()
                logger.info(f"Successfully reindexed file: {title} -> doc_id: {doc.document_id}")
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to ingest file {title} during reindex phase B: {e}")

        # Finalize success
        reindex_progress["status"] = "completed"
        reindex_progress["processed_files"] = len(analyzed_docs)
        reindex_progress["current_file"] = None
        reindex_progress["phase"] = None

    except Exception as e:
        logger.error(f"Re-indexing failed: {e}")
        reindex_progress["status"] = "failed"
        reindex_progress["error"] = str(e)
    finally:
        db.close()
        logger.info("Background re-indexing finished.")


@router.get("/reindex-progress")
async def get_reindex_progress():
    """Get the current progress of the background re-indexing task."""
    return reindex_progress


@router.post("/reindex-full")
async def reindex_full_endpoint(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """Trigger background full re-indexing of all local documents in the data folder (with LLM metadata analysis)."""
    background_tasks.add_task(run_reindex_full_task)
    return {"status": "success", "message": "Znovunačtení a reindexace všech dokumentů (s analýzou metadat) byla spuštěna na pozadí."}


async def run_reindex_all_task():
    logger.info("Starting background fast re-indexing (re-chunking) of all documents...")
    import os
    from app.storage.db import SessionLocal
    from app.storage.models import DBDocument, DBChunk
    from app.ingestion.pipeline import IngestionPipeline

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
        docs = db.execute(select(DBDocument)).scalars().all()
        
        if not docs:
            logger.info("No documents found in database for fast re-indexing.")
            reindex_progress["status"] = "completed"
            reindex_progress["phase"] = None
            return

        reindex_progress["total_files"] = len(docs)
        reindex_progress["phase"] = "ingesting"

        pipeline = IngestionPipeline(db)

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
            if not os.path.exists(file_path):
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
                    logger.warning(f"File not found for document {doc.title} at {file_path}. Skipping.")
                    continue

            logger.info(f"Fast re-indexing document: {doc.title} from {file_path}")
            try:
                extracted_pages = pipeline.extractor.extract(file_path)
                chunks = pipeline.splitter.split_pages(extracted_pages)
                if not chunks:
                    logger.warning(f"No text split from document: {doc.title}. Skipping.")
                    continue
                
                chunk_texts = [chunk.content for chunk in chunks]
                embeddings = await pipeline.embedding_provider.embed_documents(chunk_texts)
                
                db.query(DBChunk).filter(DBChunk.document_id == doc.document_id).delete()
                
                for chunk_idx, chunk in enumerate(chunks):
                    db_chunk = DBChunk(
                        document_id=doc.document_id,
                        chunk_index=chunk_idx,
                        content=chunk.content,
                        embedding=embeddings[chunk_idx],
                        language=doc.language,
                        section_title=chunk.section_title,
                        page_number=chunk.page_number,
                        security_acl=doc.security_acl,
                        metadata_json=doc.metadata_json,
                        freshness_status=doc.freshness_status
                    )
                    db.add(db_chunk)
                
                db.commit()
                logger.info(f"Successfully fast-reindexed document: {doc.title}")
            except Exception as inner_e:
                db.rollback()
                logger.error(f"Failed to fast-reindex document {doc.title}: {inner_e}")
                reindex_progress["error"] = f"Failed for {doc.title}: {inner_e}"

        reindex_progress["status"] = "completed"
        reindex_progress["processed_files"] = len(docs)
        reindex_progress["current_file"] = None
        reindex_progress["phase"] = None

    except Exception as e:
        logger.error(f"Fast re-indexing failed: {e}")
        reindex_progress["status"] = "failed"
        reindex_progress["error"] = str(e)
    finally:
        db.close()
        logger.info("Background fast re-indexing finished.")


@router.post("/reindex-all")
async def reindex_all_endpoint(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session)
):
    """Trigger background fast re-indexing (re-chunking and embedding only) of all active documents."""
    background_tasks.add_task(run_reindex_all_task)
    return {"status": "success", "message": "Znovunačtení a reindexace všech dokumentů (chunky a embeddingy) byla spuštěna na pozadí."}


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    db: Session = Depends(get_db_session)
):
    """Retrieve all chunks belonging to a document, ordered by chunk_index, to show a chunking preview in the frontend."""
    import uuid
    from app.storage.models import DBChunk, DBDocument
    
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")
        
    doc = db.query(DBDocument).filter(DBDocument.document_id == doc_uuid).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    chunks = (
        db.query(DBChunk)
        .filter(DBChunk.document_id == doc_uuid)
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
    db: Session = Depends(get_db_session)
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
    
    from app.providers.azure_openai import AzureOpenAIProvider
    llm_provider = AzureOpenAIProvider()
    
    if not document_id:
        raise HTTPException(status_code=400, detail="Missing document_id")
        
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")
        
    doc = db.query(DBDocument).filter(DBDocument.document_id == doc_uuid).first()
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
            
    file_path = os.path.abspath(os.path.join("data", relative_path))
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
        embedding_provider=embedding_provider,
        llm_provider=llm_provider
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



