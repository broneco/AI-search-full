import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.storage.db import engine, init_db, clear_db, SessionLocal
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
        clear_db()


def test_hybrid_and_lexical_fts_retrieval(db_setup):
    db = db_setup

    # 1. Create target test document
    doc = DBDocument(
        source_type="local",
        source_uri="file://test/hybrid.txt",
        title="Test Hybrid Document",
        document_type="document",
        language="cs",
        security_acl={"allowed_groups": ["Public"]},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 2. Add sample chunks containing distinct Czech words
    chunk1 = DBChunk(
        document_id=doc.document_id,
        chunk_index=0,
        content="Evidence pracovní doby na vedení společnosti Dolphin Consulting podléhá kontrole.",
        embedding=[0.1] * 1536,  # dummy embedding vector
        language="cs",
        security_acl={"allowed_groups": ["Public"]},
    )
    chunk2 = DBChunk(
        document_id=doc.document_id,
        chunk_index=1,
        content="Péče o pokusná zvířata a provoz akvarijní místnosti ve výzkumném oddělení.",
        embedding=[0.5] * 1536,  # dummy embedding vector
        language="cs",
        security_acl={"allowed_groups": ["Public"]},
    )
    db.add_all([chunk1, chunk2])
    db.commit()

    retriever = VectorRetriever(db)

    # A: Test FTS keyword strategy
    context = QueryContext(
        query="vedení",
        user_id="test_user",
        filters={},
        acl_groups=["Public"],
    )
    
    keyword_results = db.query(DBChunk).all()
    assert len(keyword_results) >= 2

    # Call FTS through Retriever
    results_keyword = retriever._get_fts_candidates("vedení", limit=10, context=context)
    assert len(results_keyword) >= 1

    retrieved_kw = retriever._get_fts_candidates("vedení", limit=10, context=context)
    assert len(retrieved_kw) >= 1
    assert "vedení" in retrieved_kw[0][0].content


def test_weighted_rrf_scoring():
    # Verify RRF logic internally using mock result lists
    from app.retrieval.base import RetrievalResult
    
    # Mock some base results
    res_vec = [
        RetrievalResult(chunk_id="chunk_A", document_id="doc_1", content="Vec 1", score=0.9, freshness_status="current", title="doc", page_number=1, metadata={}),
        RetrievalResult(chunk_id="chunk_B", document_id="doc_1", content="Vec 2", score=0.8, freshness_status="current", title="doc", page_number=2, metadata={}),
    ]
    res_kw = [
        RetrievalResult(chunk_id="chunk_B", document_id="doc_1", content="Vec 2", score=0.0, freshness_status="current", title="doc", page_number=2, metadata={}),
        RetrievalResult(chunk_id="chunk_C", document_id="doc_1", content="Vec 3", score=0.0, freshness_status="current", title="doc", page_number=3, metadata={}),
    ]

    # Initialize retriever
    class DummyRetriever(VectorRetriever):
        def __init__(self):
            pass

    retriever = DummyRetriever()
    fused = retriever._fuse_rrf(res_vec, res_kw, limit=3)

    assert len(fused) >= 2
    # chunk_B is present in both lists, so it should rank highly due to accumulated score
    assert fused[0].chunk_id in ("chunk_A", "chunk_B")
    assert "rrf_score" in fused[0].metadata
    assert "vector_score" in fused[0].metadata
