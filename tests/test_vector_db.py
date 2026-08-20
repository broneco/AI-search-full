import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.storage.db import engine, init_db, clear_db, SessionLocal
from app.storage.models import DBDocument, DBChunk
from app.retrieval.vector import VectorRetriever
from app.retrieval.base import QueryContext


# Define a pytest fixture that checks database availability and sets up tables.
@pytest.fixture(scope="module")
def db_setup():
    # Attempt to connect to the database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
    except OperationalError as e:
        pytest.skip(
            f"Local PostgreSQL database is not available: {e}. "
            "Please ensure docker compose up -d has run successfully."
        )

    # Initialize tables and extensions
    init_db()

    # Yield session
    db = SessionLocal()
    try:
        yield db
    finally:
        # Clean up database tables after tests run to keep dev clean
        db.close()
        clear_db()


def test_vector_similarity_search(db_setup):
    db = db_setup

    # 1. Create a dummy document
    doc = DBDocument(
        source_type="local",
        source_uri="file://policies/abc.txt",
        title="ABC policy",
        document_type="policy",
        language="en",
        security_acl={"allowed_groups": ["HR", "Finance"]},
        metadata_json={"department": "HR"},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 2. Add two chunks with specific embeddings
    # We will use simple 1536-dimensional vectors where:
    # chunk_1 represents something close to query_vector
    # chunk_2 represents something far from query_vector
    emb_1 = [1.0] + [0.0] * 1535
    emb_2 = [0.0, 1.0] + [0.0] * 1534

    chunk_1 = DBChunk(
        document_id=doc.document_id,
        chunk_index=0,
        content="This is the HR document about Account Based Collaboration guidelines.",
        embedding=emb_1,
        language="en",
        section_title="Account Based Collaboration",
        page_number=1,
        security_acl={"allowed_groups": ["HR"]},
        metadata_json={"tags": ["HR", "collaboration"]},
    )

    chunk_2 = DBChunk(
        document_id=doc.document_id,
        chunk_index=1,
        content="This is unrelated content about Azure Billing center details.",
        embedding=emb_2,
        language="en",
        section_title="Azure Billing",
        page_number=2,
        security_acl={"allowed_groups": ["Finance"]},
        metadata_json={"tags": ["billing"]},
    )

    db.add_all([chunk_1, chunk_2])
    db.commit()

    # 3. Create VectorRetriever
    retriever = VectorRetriever(db)

    # 4. Perform vector search matching chunk_1
    # query_vector is identical to chunk_1's embedding
    query_vector = [1.0] + [0.0] * 1535
    context = QueryContext(
        query="Account Based Collaboration",
        user_id="user_1",
        acl_groups=["HR"],
    )

    # Pytest is running in standard synchronous mode, so we run the async retriever method using anyio
    import anyio

    async def retrieve_1():
        return await retriever.retrieve(context, limit=5, query_embedding=query_vector, search_strategy="vector")

    results = anyio.run(retrieve_1, backend="asyncio")

    # Assertions
    assert len(results) >= 1
    clean_res_content = results[0].content.replace("[[MATCH_START]]", "").replace("[[MATCH_END]]", "").split("\n")[0]
    assert clean_res_content == chunk_1.content
    assert results[0].score >= 1.0
    assert results[0].title == doc.title
    assert "HR" in results[0].metadata["tags"]

    # 5. Perform vector search where user lacks ACL access
    # query matches chunk_2 (embedding matches emb_2), but user is only in HR group, not Finance
    context_no_acl = QueryContext(
        query="Azure Billing",
        user_id="user_1",
        acl_groups=["HR"],  # Lacks Finance access
    )
    async def retrieve_2():
        return await retriever.retrieve(context_no_acl, limit=5, query_embedding=emb_2, search_strategy="vector")

    results_no_acl = anyio.run(retrieve_2, backend="asyncio")
    # Since chunk_2 requires "Finance" group and user only has "HR", it should filter out chunk_2,
    # meaning chunk_2 is NOT in the results, even though it matches the query embedding emb_2 perfectly.
    assert not any(r.chunk_id == str(chunk_2.chunk_id) for r in results_no_acl)

    # 6. Perform vector search with metadata filter
    context_filter = QueryContext(
        query="Account Based Collaboration",
        user_id="user_1",
        acl_groups=["HR"],
        filters={"tags": ["HR", "collaboration"]},  # matches chunk_1 tags list
    )
    async def retrieve_3():
        return await retriever.retrieve(context_filter, limit=5, query_embedding=emb_1, search_strategy="vector")

    results_filter = anyio.run(retrieve_3, backend="asyncio")
    # Check that it filters correctly (for list parameters, tags check list matches)
    assert len(results_filter) == 1
    assert results_filter[0].chunk_id == str(chunk_1.chunk_id)
