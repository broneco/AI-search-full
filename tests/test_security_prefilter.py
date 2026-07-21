import pytest
import uuid
from datetime import datetime
import anyio
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.storage.db import engine, init_db, SessionLocal
from app.storage.models import DBDocument, DBChunk
from app.retrieval.vector import VectorRetriever
from app.retrieval.base import QueryContext


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


def test_sql_acl_prefiltering(db_setup):
    db = db_setup

    # Clean previous records
    db.execute(text("DELETE FROM chunks;"))
    db.execute(text("DELETE FROM documents;"))
    db.commit()

    # 1. Create HR document and chunk
    doc_hr_id = uuid.uuid4()
    doc_hr = DBDocument(
        document_id=doc_hr_id,
        title="HR Policy",
        source_type="local",
        source_uri="/path/hr.pdf",
        document_type="policy",
        security_acl={"allowed_groups": ["HR"]},
        freshness_status="current",
        created_at=datetime(2026, 1, 1),
    )
    chunk_hr = DBChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_hr_id,
        chunk_index=0,
        content="This is sensitive HR recruitment guidelines.",
        embedding=[0.1] * 1536,
        security_acl={"allowed_groups": ["HR"]},
    )

    # 2. Create IT document and chunk
    doc_it_id = uuid.uuid4()
    doc_it = DBDocument(
        document_id=doc_it_id,
        title="IT Policy",
        source_type="local",
        source_uri="/path/it.pdf",
        document_type="policy",
        security_acl={"allowed_groups": ["IT"]},
        freshness_status="current",
        created_at=datetime(2026, 1, 1),
    )
    chunk_it = DBChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_it_id,
        chunk_index=0,
        content="This is IT security and firewall setup guidelines.",
        embedding=[0.1] * 1536,
        security_acl={"allowed_groups": ["IT"]},
    )

    db.add(doc_hr)
    db.add(chunk_hr)
    db.add(doc_it)
    db.add(chunk_it)
    db.commit()

    retriever = VectorRetriever(db)

    # A. Search as HR user (only HR document should be returned)
    ctx_hr = QueryContext(
        query="guidelines",
        acl_groups={"HR"},
        filters={},
    )
    
    async def get_hr():
        return await retriever.retrieve(ctx_hr, query_embedding=[0.1] * 1536)
        
    results_hr = anyio.run(get_hr, backend="asyncio")
    assert len(results_hr) == 1
    assert results_hr[0].title == "HR Policy"

    # B. Search as IT user (only IT document should be returned)
    ctx_it = QueryContext(
        query="guidelines",
        acl_groups={"IT"},
        filters={},
    )
    
    async def get_it():
        return await retriever.retrieve(ctx_it, query_embedding=[0.1] * 1536)
        
    results_it = anyio.run(get_it, backend="asyncio")
    assert len(results_it) == 1
    assert results_it[0].title == "IT Policy"

    # C. Search as Management (bypasses ACL, sees both)
    ctx_mgmt = QueryContext(
        query="guidelines",
        acl_groups={"Management"},
        filters={},
    )
    
    async def get_mgmt():
        return await retriever.retrieve(ctx_mgmt, query_embedding=[0.1] * 1536)
        
    results_mgmt = anyio.run(get_mgmt, backend="asyncio")
    assert len(results_mgmt) == 2


def test_sql_freshness_prefiltering(db_setup):
    db = db_setup

    # Clean previous records
    db.execute(text("DELETE FROM chunks;"))
    db.execute(text("DELETE FROM documents;"))
    db.commit()

    # 1. Create Active 2026 Doc
    doc_new_id = uuid.uuid4()
    doc_new = DBDocument(
        document_id=doc_new_id,
        title="Valid 2026 Doc",
        source_type="local",
        source_uri="/path/new.pdf",
        document_type="policy",
        security_acl={"allowed_groups": ["User"]},
        freshness_status="current",
        created_at=datetime(2026, 1, 1),
    )
    chunk_new = DBChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_new_id,
        chunk_index=0,
        content="Current 2026 guidelines.",
        embedding=[0.1] * 1536,
        security_acl={"allowed_groups": ["User"]},
    )

    # 2. Create Archived Doc from 2024
    doc_old_id = uuid.uuid4()
    doc_old = DBDocument(
        document_id=doc_old_id,
        title="Archived 2024 Doc",
        source_type="local",
        source_uri="/path/old.pdf",
        document_type="policy",
        security_acl={"allowed_groups": ["User"]},
        freshness_status="archived",
        created_at=datetime(2024, 1, 1),
    )
    chunk_old = DBChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_old_id,
        chunk_index=0,
        content="Outdated 2024 firewall setup guidelines.",
        embedding=[0.1] * 1536,
        security_acl={"allowed_groups": ["User"]},
    )

    db.add(doc_new)
    db.add(chunk_new)
    db.add(doc_old)
    db.add(chunk_old)
    db.commit()

    retriever = VectorRetriever(db)

    # A. Retrieve with "latest" filter
    ctx_latest = QueryContext(
        query="guidelines",
        acl_groups={"User"},
        filters={"freshness_filter": "latest"},
    )
    
    async def get_latest():
        return await retriever.retrieve(ctx_latest, query_embedding=[0.1] * 1536)
        
    results_latest = anyio.run(get_latest, backend="asyncio")
    assert len(results_latest) == 1
    assert results_latest[0].title == "Valid 2026 Doc"

    # B. Retrieve with "this_year" filter
    ctx_year = QueryContext(
        query="guidelines",
        acl_groups={"User"},
        filters={"freshness_filter": "this_year"},
    )
    
    async def get_year():
        return await retriever.retrieve(ctx_year, query_embedding=[0.1] * 1536)
        
    results_year = anyio.run(get_year, backend="asyncio")
    assert len(results_year) == 1
    assert results_year[0].title == "Valid 2026 Doc"

    # C. Retrieve all (default)
    ctx_all = QueryContext(
        query="guidelines",
        acl_groups={"User"},
        filters={"freshness_filter": "all"},
    )
    
    async def get_all():
        return await retriever.retrieve(ctx_all, query_embedding=[0.1] * 1536)
        
    results_all = anyio.run(get_all, backend="asyncio")
    assert len(results_all) == 2


def test_token_budget_context_expansion(db_setup):
    db = db_setup

    db.execute(text("DELETE FROM chunks;"))
    db.execute(text("DELETE FROM documents;"))
    db.commit()

    # Create document with multiple sequential chunks
    doc_id = uuid.uuid4()
    doc = DBDocument(
        document_id=doc_id,
        title="Sequential Document",
        source_type="local",
        source_uri="/path/seq.pdf",
        document_type="policy",
        security_acl={"allowed_groups": ["User"]},
        freshness_status="current",
        created_at=datetime(2026, 1, 1),
    )
    
    # We will create 5 chunks of 300 characters each.
    # 300 characters is approx 100 tokens.
    chunks = []
    for i in range(5):
        chunk = DBChunk(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            chunk_index=i,
            content=f"Chunk index {i} content. " + ("word " * 40) + f" End of chunk {i}.",
            embedding=[0.1] * 1536,
            security_acl={"allowed_groups": ["User"]},
        )
        chunks.append(chunk)

    db.add(doc)
    for c in chunks:
        db.add(c)
    db.commit()

    retriever = VectorRetriever(db)

    # Search for Chunk 2 specifically (middle chunk) using keyword (FTS) strategy
    ctx = QueryContext(
        query="2",
        acl_groups={"User"},
        filters={"search_strategy": "keyword", "context_expansion": "siblings", "context_expansion_size": 2},
    )
    
    # Setup custom search configuration with token limit
    custom_cfg = {
        "search_strategy": "keyword",
        "context_expansion": "siblings",
        "context_expansion_size": 2,
        "context_max_tokens": 200,  # 200 * 3 = 600 characters budget
    }
    
    async def get_expansion():
        return await retriever.retrieve(
            ctx, 
            query_embedding=[0.1] * 1536,
            search_config=custom_cfg
        )
        
    results = anyio.run(get_expansion, backend="asyncio")
    
    assert len(results) == 1
    expanded_content = results[0].content
    
    # Must contain matched Chunk index 2
    assert "Chunk index 2 content" in expanded_content
    
    # Verify length of content is within token budget (approx 600 chars)
    assert len(expanded_content) <= 600
    
    # Verify it does NOT contain all 5 chunks (since that would be ~1250 characters)
    assert "Chunk index 0 content" not in expanded_content or "Chunk index 4 content" not in expanded_content
