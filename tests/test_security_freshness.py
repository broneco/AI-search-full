import pytest
import datetime
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

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

    # Initialize schemas and tables
    init_db()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        clear_db()


def test_security_roles_authorizations(db_setup):
    db = db_setup

    # 1. Create a parent test document
    doc = DBDocument(
        source_type="local",
        source_uri="file://test/security_rules.txt",
        title="Security Test Doc",
        document_type="document",
        language="cs",
        security_acl={"allowed_groups": ["Management", "HR", "Finance", "User"]},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 2. Add chunks with different security group ACL permissions
    # Chunk 1: Restricted to HR & Management
    chunk_hr = DBChunk(
        document_id=doc.document_id,
        chunk_index=0,
        content="Personalni evidence a nastupy zamestnancu na oddeleni HR.",
        embedding=[0.1] * 1536,
        language="cs",
        security_acl={"allowed_groups": ["Management", "HR"]},
    )
    # Chunk 2: Restricted to Finance & Management
    chunk_finance = DBChunk(
        document_id=doc.document_id,
        chunk_index=1,
        content="Vypocet rocniho rozpoctu a financnich rezerv.",
        embedding=[0.2] * 1536,
        language="cs",
        security_acl={"allowed_groups": ["Management", "Finance"]},
    )
    # Chunk 3: Public (User role has access)
    chunk_public = DBChunk(
        document_id=doc.document_id,
        chunk_index=2,
        content="Obecne informace o provozu akvarijni mistnosti.",
        embedding=[0.3] * 1536,
        language="cs",
        security_acl={"allowed_groups": ["Management", "HR", "Finance", "User"]},
    )
    db.add_all([chunk_hr, chunk_finance, chunk_public])
    db.commit()

    retriever = VectorRetriever(db)

    # A: Test Management bypass (has access to EVERYTHING)
    context_mgt = QueryContext(
        query="akvarijni rozpoctu evidence",
        user_id="mgt_user",
        filters={},
        acl_groups=["Management"],
    )
    results_mgt = retriever._apply_filters(
        raw_db_results=[(chunk_hr, doc), (chunk_finance, doc), (chunk_public, doc)],
        context=context_mgt,
        query_embedding=[0.1] * 1536,
    )
    assert len(results_mgt) == 3

    # B: Test HR Specialist access (has access only to HR + User public, blocks Finance)
    context_hr = QueryContext(
        query="akvarijni rozpoctu evidence",
        user_id="hr_user",
        filters={},
        acl_groups=["HR"],
    )
    results_hr = retriever._apply_filters(
        raw_db_results=[(chunk_hr, doc), (chunk_finance, doc), (chunk_public, doc)],
        context=context_hr,
        query_embedding=[0.1] * 1536,
    )
    assert len(results_hr) == 2
    retrieved_contents_hr = [item.content for item in results_hr]
    assert not any("Vypocet rocniho rozpoctu" in content for content in retrieved_contents_hr)
    assert any("Personalni evidence" in content for content in retrieved_contents_hr)
    assert any("Obecne informace" in content for content in retrieved_contents_hr)

    # C: Test Finance Auditor access (has access only to Finance + User public, blocks HR)
    context_fin = QueryContext(
        query="akvarijni rozpoctu evidence",
        user_id="fin_user",
        filters={},
        acl_groups=["Finance"],
    )
    results_fin = retriever._apply_filters(
        raw_db_results=[(chunk_hr, doc), (chunk_finance, doc), (chunk_public, doc)],
        context=context_fin,
        query_embedding=[0.2] * 1536,
    )
    assert len(results_fin) == 2
    retrieved_contents_fin = [item.content for item in results_fin]
    assert not any("Personalni evidence" in content for content in retrieved_contents_fin)
    assert any("Vypocet rocniho rozpoctu" in content for content in retrieved_contents_fin)

    # D: Test Standard User access (has access ONLY to public/User, blocks both HR and Finance)
    context_usr = QueryContext(
        query="akvarijni rozpoctu evidence",
        user_id="std_user",
        filters={},
        acl_groups=["User"],
    )
    results_usr = retriever._apply_filters(
        raw_db_results=[(chunk_hr, doc), (chunk_finance, doc), (chunk_public, doc)],
        context=context_usr,
        query_embedding=[0.3] * 1536,
    )
    assert len(results_usr) == 1
    assert results_usr[0].content.startswith("Obecne informace")


def test_freshness_filters(db_setup):
    db = db_setup

    # 1. Document A: Platný (current) & Created in 2026 (this year)
    doc_a = DBDocument(
        source_type="local",
        source_uri="file://test/doc_a.txt",
        title="Document A Current 2026",
        document_type="document",
        language="cs",
        security_acl={"allowed_groups": ["Management"]},
        freshness_status="current",
        created_at=datetime.datetime(2026, 4, 15),
    )
    # 2. Document B: Archivovaný (archived) & Created in 2024
    doc_b = DBDocument(
        source_type="local",
        source_uri="file://test/doc_b.txt",
        title="Document B Archived 2024",
        document_type="document",
        language="cs",
        security_acl={"allowed_groups": ["Management"]},
        freshness_status="archived",
        created_at=datetime.datetime(2024, 5, 10),
    )
    # 3. Document C: Platný (current) & Created in 2025
    doc_c = DBDocument(
        source_type="local",
        source_uri="file://test/doc_c.txt",
        title="Document C Current 2025",
        document_type="document",
        language="cs",
        security_acl={"allowed_groups": ["Management"]},
        freshness_status="current",
        created_at=datetime.datetime(2025, 8, 20),
    )
    db.add_all([doc_a, doc_b, doc_c])
    db.commit()

    chunk_a = DBChunk(document_id=doc_a.document_id, chunk_index=0, content="A text", embedding=[0.1]*1536)
    chunk_b = DBChunk(document_id=doc_b.document_id, chunk_index=0, content="B text", embedding=[0.1]*1536)
    chunk_c = DBChunk(document_id=doc_c.document_id, chunk_index=0, content="C text", embedding=[0.1]*1536)
    db.add_all([chunk_a, chunk_b, chunk_c])
    db.commit()

    retriever = VectorRetriever(db)

    # Context with "all" freshness filter
    ctx_all = QueryContext(
        query="text", user_id="test", filters={"freshness_filter": "all"}, acl_groups=["Management"]
    )
    res_all = retriever._apply_filters(
        raw_db_results=[(chunk_a, doc_a), (chunk_b, doc_b), (chunk_c, doc_c)],
        context=ctx_all,
        query_embedding=[0.1]*1536,
    )
    assert len(res_all) == 3

    # Context with "latest" freshness filter (only Platné / current)
    ctx_latest = QueryContext(
        query="text", user_id="test", filters={"freshness_filter": "latest"}, acl_groups=["Management"]
    )
    res_latest = retriever._apply_filters(
        raw_db_results=[(chunk_a, doc_a), (chunk_b, doc_b), (chunk_c, doc_c)],
        context=ctx_latest,
        query_embedding=[0.1]*1536,
    )
    assert len(res_latest) == 2
    retrieved_titles = [item.title for item in res_latest]
    assert "Document A Current 2026" in retrieved_titles
    assert "Document C Current 2025" in retrieved_titles
    assert "Document B Archived 2024" not in retrieved_titles

    # Context with "this_year" freshness filter (only year 2026)
    ctx_year = QueryContext(
        query="text", user_id="test", filters={"freshness_filter": "this_year"}, acl_groups=["Management"]
    )
    res_year = retriever._apply_filters(
        raw_db_results=[(chunk_a, doc_a), (chunk_b, doc_b), (chunk_c, doc_c)],
        context=ctx_year,
        query_embedding=[0.1]*1536,
    )
    assert len(res_year) == 1
    assert res_year[0].title == "Document A Current 2026"
