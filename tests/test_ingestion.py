import os
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.storage.db import engine, init_db, clear_db, SessionLocal
from app.ingestion.loaders.local import list_local_files
from app.ingestion.extraction import DocumentExtractor
from app.ingestion.chunking import RecursiveCharacterTextSplitter
from app.ingestion.pipeline import IngestionPipeline


@pytest.fixture(scope="module")
def db_setup():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
    except OperationalError as e:
        pytest.skip(f"Database connection offline: {e}")

    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        clear_db()


def test_pdf_extraction_and_chunking(tmp_path):
    # 1. Create a dummy text file to test extraction and chunking layers
    dummy_file = tmp_path / "test_extract.txt"
    dummy_text = (
        "Hello World. This is paragraph one containing some nice sentences.\n\n"
        "This is paragraph two detailing important specifications about coding systems."
    )
    dummy_file.write_text(dummy_text, encoding="utf-8")

    # 2. Test loader
    files = list_local_files(str(tmp_path), extensions=[".txt"])
    assert len(files) == 1
    assert files[0] == os.path.abspath(dummy_file)

    # 3. Test extractor
    extractor = DocumentExtractor()
    extracted_pages = extractor.extract(files[0])
    assert len(extracted_pages) == 1
    assert "paragraph two" in extracted_pages[0].text

    # 4. Test splitter chunker
    splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=20)
    chunks = splitter.split_pages(extracted_pages)
    assert len(chunks) >= 2
    assert chunks[0].page_number == 1
    assert chunks[1].index == 1


def test_pipeline_ingestion(db_setup, tmp_path):
    db = db_setup

    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
        pytest.skip("Azure OpenAI credentials are not configured.")

    # Create dummy text file to run through the full pipeline
    dummy_file = tmp_path / "test_pipeline.txt"
    dummy_file.write_text("Dolphin annual leave protocol allows 25 days of vacation.", encoding="utf-8")

    pipeline = IngestionPipeline(db)
    
    # Process file through pipeline
    import anyio

    async def run_pipeline():
        return await pipeline.ingest_file(
            file_path=str(dummy_file),
            document_type="policy",
            security_acl={"allowed_groups": ["HR"]},
        )

    doc = anyio.run(run_pipeline, backend="asyncio")
    
    assert doc.title == "test_pipeline"
    assert doc.source_type in ("local", "azure_blob")

    # Query DB to assert records are created
    from sqlalchemy import select
    from app.storage.models import DBChunk

    chunks_stmt = select(DBChunk).where(DBChunk.document_id == doc.document_id)
    db_chunks = db.execute(chunks_stmt).scalars().all()
    assert len(db_chunks) >= 1
    assert "Dolphin annual" in db_chunks[0].content
