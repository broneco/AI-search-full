import pytest
import uuid
import anyio
import os
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from fastapi.testclient import TestClient

from app.main import app
from app.storage.db import engine, init_db, SessionLocal
from app.storage.models import DBDocument, DBChunk
from app.api.routes.documents import run_reindex_all_task, reindex_progress
from app.core.search_config import SearchConfigManager



@pytest.fixture(scope="module")
def db_setup():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
    except OperationalError as e:
        pytest.skip(f"Database connection not available: {e}")

    # Set up tables and indices
    init_db()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS chunks CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS documents CASCADE;"))


def test_fast_reindex_task(db_setup):
    db = db_setup

    # 1. Clean previous records
    db.execute(text("DELETE FROM chunks;"))
    db.execute(text("DELETE FROM documents;"))
    db.commit()

    # 2. Create a mock document in the database
    # The document points to a local file that actually exists under data/ or we can create a temporary file!
    # Let's create a temporary txt file inside data/ to guarantee it is processed by PyPDF/txt extractor
    data_dir = os.path.abspath("data")
    os.makedirs(data_dir, exist_ok=True)
    temp_txt_path = os.path.join(data_dir, "temp_rechunk_test.txt")
    
    # 500 characters of text
    sample_text = "This is a long sample sentence for rechunking test. " * 10
    with open(temp_txt_path, "w", encoding="utf-8") as f:
        f.write(sample_text)

    doc_id = uuid.uuid4()
    doc = DBDocument(
        document_id=doc_id,
        title="Rechunk Test Document",
        source_type="local",
        source_uri="file://temp_rechunk_test.txt",
        document_type="policy",
        security_acl={"allowed_groups": ["User"]},
        freshness_status="current",
        created_at=datetime(2026, 1, 1),
    )
    
    # Seed one initial chunk of 1500 chars (representing the old chunking parameters)
    chunk = DBChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        chunk_index=0,
        content=sample_text,
        embedding=[0.1] * 1536,
        security_acl={"allowed_groups": ["User"]},
    )
    
    db.add(doc)
    db.add(chunk)
    db.commit()

    # 3. Modify Search Config dynamically to chunk size = 150 (meaning the 500 chars text should be split into multiple chunks!)
    config_mgr = SearchConfigManager()
    cfg = config_mgr.load_config_sync()
    original_size = cfg.get("chunk_size", 1500)
    original_overlap = cfg.get("chunk_overlap", 250)

    try:
        cfg["chunk_size"] = 150
        cfg["chunk_overlap"] = 0
        
        # Save temporary search config to disk so pipeline loads it
        import json
        with open(config_mgr.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        # 4. Trigger fast re-indexing task
        anyio.run(run_reindex_all_task, backend="asyncio")

        # 5. Verify progress state
        assert reindex_progress["status"] == "completed"
        assert reindex_progress["error"] is None

        # 6. Verify that chunks in the DB have been updated
        db.expire_all()
        updated_chunks = db.query(DBChunk).filter(DBChunk.document_id == doc_id).order_by(DBChunk.chunk_index).all()
        
        # Since text is ~520 chars, and chunk_size=150, it should have split into at least 3-4 chunks
        assert len(updated_chunks) > 1
        
        # Verify that all new chunks have embeddings populated
        for c in updated_chunks:
            assert c.embedding is not None
            assert len(c.embedding) == 1536

    finally:
        # Restore original config
        cfg["chunk_size"] = original_size
        cfg["chunk_overlap"] = original_overlap
        with open(config_mgr.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
            
        # Clean up temporary test file
        if os.path.exists(temp_txt_path):
            os.remove(temp_txt_path)


def test_preview_chunks_endpoint(db_setup):
    db = db_setup
    client = TestClient(app)

    # 1. Clean previous records
    db.execute(text("DELETE FROM chunks;"))
    db.execute(text("DELETE FROM documents;"))
    db.commit()

    # 2. Create a mock document in the database
    data_dir = os.path.abspath("data")
    os.makedirs(data_dir, exist_ok=True)
    temp_txt_path = os.path.join(data_dir, "temp_preview_test.txt")
    
    # 500 characters of text
    sample_text = "This is a sentence for testing interactive preview endpoint. " * 10
    with open(temp_txt_path, "w", encoding="utf-8") as f:
        f.write(sample_text)

    doc_id = uuid.uuid4()
    doc = DBDocument(
        document_id=doc_id,
        title="Preview Test Document",
        source_type="local",
        source_uri="file://temp_preview_test.txt",
        document_type="policy",
        security_acl={"allowed_groups": ["User"]},
        freshness_status="current",
        created_at=datetime(2026, 1, 1),
    )
    db.add(doc)
    db.commit()

    try:
        # 3. Call the preview-chunks endpoint with custom chunk_size = 200
        payload = {
            "document_id": str(doc_id),
            "chunk_size": 200,
            "chunk_overlap": 50
        }
        res = client.post("/api/documents/preview-chunks", json=payload)
        assert res.status_code == 200
        
        chunks = res.json()
        assert len(chunks) > 1
        
        # Verify content has been split
        for chunk in chunks:
            assert "chunk_index" in chunk
            assert "content" in chunk
            assert "page_number" in chunk
            assert "section_title" in chunk
            assert len(chunk["content"]) <= 200

    finally:
        # Clean up temporary test file
        if os.path.exists(temp_txt_path):
            os.remove(temp_txt_path)


def test_recursive_character_splitter_strategies():
    from app.ingestion.chunking import RecursiveCharacterTextSplitter, ExtractedPage
    
    pages = [
        ExtractedPage(page_number=1, text="This is first page sentence one. This is first page sentence two."),
        ExtractedPage(page_number=2, text="This is second page sentence three. This is second page sentence four.")
    ]
    
    # Strategy 1: Page-isolated, recursive (default)
    splitter_default = RecursiveCharacterTextSplitter(chunk_size=30, chunk_overlap=5, chunk_cross_page=False, chunk_splitter_type="recursive")
    chunks_default = splitter_default.split_pages(pages)
    
    # Assert that page boundaries are kept (chunks on page 1 only contain text from page 1)
    for c in chunks_default:
        if c.page_number == 1:
            assert "second" not in c.content
        if c.page_number == 2:
            assert "first" not in c.content

    # Strategy 2: Cross-page, recursive
    splitter_cross = RecursiveCharacterTextSplitter(chunk_size=30, chunk_overlap=5, chunk_cross_page=True, chunk_splitter_type="recursive")
    chunks_cross = splitter_cross.split_pages(pages)
    assert len(chunks_cross) > 0

    # Strategy 3: Page-isolated, character only
    splitter_char = RecursiveCharacterTextSplitter(chunk_size=20, chunk_overlap=0, chunk_cross_page=False, chunk_splitter_type="character")
    chunks_char = splitter_char.split_pages(pages)
    # Ensure chunks are exactly <= 20 characters
    for c in chunks_char:
        assert len(c.content) <= 20


def test_advanced_chunking_strategies():
    from app.ingestion.chunking import RecursiveCharacterTextSplitter, ExtractedPage
    
    pages = [
        ExtractedPage(page_number=1, text="This is first page sentence one. This is first page sentence two."),
        ExtractedPage(page_number=2, text="This is second page sentence three. This is second page sentence four.")
    ]
    
    # 1. Token-based Strategy
    splitter_token = RecursiveCharacterTextSplitter(
        chunking_strategy="token",
        token_params={"size_tokens": 10, "overlap_tokens": 2, "tokenizer_type": "cl100k_base"}
    )
    chunks_token = splitter_token.split_pages(pages)
    assert len(chunks_token) > 0
    
    # 2. Structure-based Strategy
    structure_text = "# Heading 1\nThis is paragraph one.\n## Heading 2\nThis is paragraph two."
    splitter_struct = RecursiveCharacterTextSplitter(
        chunking_strategy="structure",
        structure_params={"preserve_tables": True, "preserve_lists": True, "max_size": 100}
    )
    chunks_struct = splitter_struct.split_pages([ExtractedPage(page_number=1, text=structure_text)])
    assert len(chunks_struct) >= 2
    assert chunks_struct[0].content.startswith("# Heading 1")
    assert chunks_struct[1].content.startswith("## Heading 2")

    # 3. Agentic Strategy (true LLM splitting) & Universal Summary Enrichment
    class MockLLMProvider:
        async def generate(self, messages, model_profile="flash"):
            return "First chunk content===CHUNK_BREAK===Second chunk content"

    splitter_agentic = RecursiveCharacterTextSplitter(
        chunking_strategy="agentic",
        agentic_params={"custom_prompt": "Rozděl podle odseků", "model_name": "gpt-4o-mini", "max_context_chars": 4000},
        llm_provider=MockLLMProvider()
    )
    chunks_agentic = splitter_agentic.split_pages(pages, force_ai=True)
    assert len(chunks_agentic) >= 2
    assert "First chunk content" in chunks_agentic[0].content

    # 4. Universal AI Summary Enrichment Check
    splitter_summary = RecursiveCharacterTextSplitter(
        chunking_strategy="standard",
        enrich_with_summary=True,
        summary_custom_prompt="Shrnutí v angličtině prosím",
        llm_provider=MockLLMProvider()
    )
    chunks_summary = splitter_summary.split_pages(pages, force_ai=True)
    assert len(chunks_summary) > 0
    assert "[AI Shrnutí" in chunks_summary[0].content

    # 4. Semantic Strategy (with mock embedding provider)
    class MockEmbeddingProvider:
        async def embed_documents(self, texts):
            return [[0.1] * 1536 for _ in texts]
            
    splitter_semantic = RecursiveCharacterTextSplitter(
        chunking_strategy="semantic",
        semantic_params={
            "threshold_type": "percentile",
            "threshold_value": 90.0,
            "sentence_splitter": "simple_regex",
            "buffer_size": 1,
            "max_size": 1000
        },
        embedding_provider=MockEmbeddingProvider()
    )
    chunks_semantic = splitter_semantic.split_pages(pages)
    assert len(chunks_semantic) > 0

    # 5. Overlap Cross Page & No Pure-Overlap Duplicates Verification
    distinct_text = " ".join([f"UniqueWord{i}" for i in range(200)])
    splitter_no_dup = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=30, chunk_splitter_type="character")
    chunks_no_dup = splitter_no_dup.split_pages([ExtractedPage(page_number=1, text=distinct_text)])
    # Ensure no chunk is a duplicate substring of its predecessor
    for i in range(1, len(chunks_no_dup)):
        assert chunks_no_dup[i].content not in chunks_no_dup[i-1].content



