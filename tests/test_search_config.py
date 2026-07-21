import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.search_config import SearchConfigManager, SearchConfigSchema
from app.storage.db import engine, init_db, SessionLocal
from app.storage.models import DBDocument, DBChunk
from app.retrieval.vector import VectorRetriever
from app.retrieval.base import QueryContext, RetrievalResult


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


def test_search_config_validation():
    # Test valid configuration
    cfg = SearchConfigSchema(
        search_strategy="hybrid",
        hybrid_strategy="score_addition",
        vector_weight=0.7,
        keyword_weight=0.3,
        final_limit=6,
        context_expansion="siblings",
        context_expansion_size=2,
    )
    assert cfg.search_strategy == "hybrid"
    assert cfg.hybrid_strategy == "score_addition"
    assert cfg.vector_weight == 0.7
    assert cfg.keyword_weight == 0.3
    assert cfg.final_limit == 6
    assert cfg.context_expansion == "siblings"
    assert cfg.context_expansion_size == 2

    # Test invalid values (should fail validation)
    with pytest.raises(ValueError):
        SearchConfigSchema(search_strategy="invalid_strat")
    with pytest.raises(ValueError):
        SearchConfigSchema(vector_weight=1.5)  # must be <= 1.0
    with pytest.raises(ValueError):
        SearchConfigSchema(context_expansion_size=4)  # must be <= 3


def test_score_addition_fusion():
    # Mock some vector and keyword results
    r_v1 = RetrievalResult(
        chunk_id="c1",
        document_id="d1",
        content="Vector match 1",
        score=0.8,
        freshness_status="current",
        title="Doc 1",
    )
    r_v2 = RetrievalResult(
        chunk_id="c2",
        document_id="d1",
        content="Vector match 2",
        score=0.6,
        freshness_status="current",
        title="Doc 1",
    )
    r_k1 = RetrievalResult(
        chunk_id="c2",
        document_id="d1",
        content="Keyword match 2",
        score=0.0,
        freshness_status="current",
        title="Doc 1",
        metadata={"fts_rank": 0.5},
    )
    r_k2 = RetrievalResult(
        chunk_id="c3",
        document_id="d2",
        content="Keyword match 3",
        score=0.0,
        freshness_status="current",
        title="Doc 2",
        metadata={"fts_rank": 0.25},
    )

    retriever = VectorRetriever(None)
    # Perform score addition fusion
    # Max FTS is 0.5 (from r_k1). So r_k1 normalizes to 1.0 (0.5/0.5), r_k2 to 0.5 (0.25/0.5)
    # Combined scores:
    # c1 (only vector): 0.6 * 0.8 = 0.48
    # c2 (vector + keyword): 0.6 * 0.6 + 0.4 * 1.0 = 0.36 + 0.40 = 0.76
    # c3 (only keyword): 0.4 * 0.5 = 0.20
    # Expected ordering: c2, c1, c3
    fused = retriever._fuse_score_addition(
        vector_results=[r_v1, r_v2],
        keyword_results=[r_k1, r_k2],
        vector_weight=0.6,
        keyword_weight=0.4,
        limit=5,
    )

    assert len(fused) == 3
    assert fused[0].chunk_id == "c2"
    assert abs(fused[0].score - 0.76) < 0.001
    assert fused[1].chunk_id == "c1"
    assert abs(fused[1].score - 0.48) < 0.001
    assert fused[2].chunk_id == "c3"
    assert abs(fused[2].score - 0.20) < 0.001


def test_union_fusion():
    r_v1 = RetrievalResult(chunk_id="c1", document_id="d1", content="V1", score=0.9, freshness_status="current", title="D1")
    r_v2 = RetrievalResult(chunk_id="c2", document_id="d1", content="V2", score=0.8, freshness_status="current", title="D1")
    r_k1 = RetrievalResult(chunk_id="c2", document_id="d1", content="K1", score=0.0, freshness_status="current", title="D1")
    r_k2 = RetrievalResult(chunk_id="c3", document_id="d2", content="K2", score=0.0, freshness_status="current", title="D2")

    retriever = VectorRetriever(None)
    # Union limit: N=1 vector, M=2 keyword.
    # Expected: c1 (from vector), then c2, c3 (from keyword). c2 from keyword is duplicate of vector but not added because it is already seen.
    # So seen: {c1, c2, c3}
    union_results = retriever._fuse_union(
        vector_results=[r_v1, r_v2],
        keyword_results=[r_k1, r_k2],
        vector_final_limit=1,
        keyword_final_limit=2,
    )

    assert len(union_results) == 3
    assert [item.chunk_id for item in union_results] == ["c1", "c2", "c3"]


def test_context_expansion_siblings(db_setup):
    db = db_setup

    # 1. Create document
    doc = DBDocument(
        source_type="local",
        source_uri="file://test/context.txt",
        title="Context Test Doc",
        document_type="document",
        language="cs",
        security_acl={"allowed_groups": ["Public"]},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 2. Add sequential chunks
    c0 = DBChunk(document_id=doc.document_id, chunk_index=0, content="Prvni odstavec.", language="cs", security_acl={"allowed_groups": ["Public"]})
    c1 = DBChunk(document_id=doc.document_id, chunk_index=1, content="Druhy odstavec.", language="cs", security_acl={"allowed_groups": ["Public"]})
    c2 = DBChunk(document_id=doc.document_id, chunk_index=2, content="Treti odstavec.", language="cs", security_acl={"allowed_groups": ["Public"]})
    db.add_all([c0, c1, c2])
    db.commit()

    retriever = VectorRetriever(db)

    # Mock retrieved item matching c1
    matched_item = RetrievalResult(
        chunk_id=str(c1.chunk_id),
        document_id=str(doc.document_id),
        content="Druhy odstavec.",
        score=0.9,
        freshness_status="current",
        title="Context Test Doc",
        metadata={"chunk_index": 1},
    )

    # Expand context with N=1 (should return c0 + c1 + c2 joined, c1 wrapped in match tags)
    expanded = retriever._expand_context([matched_item], expansion_type="siblings", expansion_size=1)
    assert len(expanded) == 1
    assert expanded[0].content == "Prvni odstavec.\n[[MATCH_START]]Druhy odstavec.[[MATCH_END]]\nTreti odstavec."


def test_context_expansion_page_and_section(db_setup):
    db = db_setup

    # Retrieve existing or use document_id
    doc_id = db.query(DBDocument).first().document_id

    # Add chunk with page_number and section_title
    c_p1 = DBChunk(
        document_id=doc_id,
        chunk_index=10,
        content="Odstavec na strane 5.",
        page_number=5,
        section_title="Kapitola 1",
        language="cs",
        security_acl={"allowed_groups": ["Public"]},
    )
    c_p2 = DBChunk(
        document_id=doc_id,
        chunk_index=11,
        content="Dalsi odstavec na strane 5.",
        page_number=5,
        section_title="Kapitola 1",
        language="cs",
        security_acl={"allowed_groups": ["Public"]},
    )
    db.add_all([c_p1, c_p2])
    db.commit()

    retriever = VectorRetriever(db)

    matched_item = RetrievalResult(
        chunk_id=str(c_p1.chunk_id),
        document_id=str(doc_id),
        content="Odstavec na strane 5.",
        score=0.9,
        freshness_status="current",
        title="Page Test Doc",
        page_number=5,
        section_title="Kapitola 1",
        metadata={"chunk_index": 10},
    )

    # Page expansion (c_p1 is matched, should be wrapped)
    expanded_page = retriever._expand_context([matched_item], expansion_type="page", expansion_size=1)
    assert len(expanded_page) == 1
    assert expanded_page[0].content == "[[MATCH_START]]Odstavec na strane 5.[[MATCH_END]]\nDalsi odstavec na strane 5."

    # Section expansion (c_p1 is matched, should be wrapped)
    expanded_section = retriever._expand_context([matched_item], expansion_type="section", expansion_size=1)
    assert len(expanded_section) == 1
    assert expanded_section[0].content == "[[MATCH_START]]Odstavec na strane 5.[[MATCH_END]]\nDalsi odstavec na strane 5."
