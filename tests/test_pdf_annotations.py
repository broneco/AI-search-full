import os
import pytest
import uuid
import fitz
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.main import app
from app.storage.db import engine, init_db, clear_db, SessionLocal
from app.storage.models import DBDocument, DBChunk

client = TestClient(app)
TEST_PDF_PATH = os.path.abspath("data/test_highlight.pdf")


@pytest.fixture(scope="module")
def pdf_setup():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
    except OperationalError as e:
        pytest.skip(f"Database connection not available: {e}")

    # 1. Ensure tables are initialized
    init_db()

    # 2. Programmatically compile a valid searchable 1-page PDF document
    os.makedirs(os.path.dirname(TEST_PDF_PATH), exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Dobrý den! Jaká jsou pravidla pro registr smluv v naší společnosti?")
    doc.save(TEST_PDF_PATH)
    doc.close()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up files
        if os.path.exists(TEST_PDF_PATH):
            os.remove(TEST_PDF_PATH)
        # Drop test tables
        clear_db()


def test_view_document_with_highlights(pdf_setup):
    db = pdf_setup

    # 1. Insert parent DBDocument row pointing to local mock PDF
    doc = DBDocument(
        source_type="local",
        source_uri=f"file://{os.path.basename(TEST_PDF_PATH)}",
        title="Test Highlight Document",
        document_type="policy",
        language="cs",
        checksum="mock_checksum_value",
        security_acl={"allowed_groups": ["Management", "User"]},
        freshness_status="current",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 2. Insert DBChunk row containing a text block from the PDF
    chunk = DBChunk(
        document_id=doc.document_id,
        chunk_index=0,
        content="Jaká jsou pravidla pro registr smluv",
        embedding=[0.1] * 1536,
        language="cs",
        page_number=1,
        security_acl={"allowed_groups": ["Management", "User"]},
        freshness_status="current",
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    # 3. Hit the view route with the highlight query parameter
    url = f"/api/documents/view/{doc.document_id}?highlight_chunk_id={chunk.chunk_id}"
    response = client.get(url)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    
    # 4. Open returned PDF bytes using PyMuPDF to verify highlight annotations exist
    pdf_in_memory = response.content
    pdf_doc = fitz.open(stream=pdf_in_memory, filetype="pdf")
    
    assert len(pdf_doc) == 1
    page = pdf_doc[0]
    
    # Extract annotations from the page
    annots = list(page.annots())
    assert len(annots) >= 1
    
    # Assert annotation type is Highlight (type 8 in PDF spec)
    highlight_annot = annots[0]
    assert highlight_annot.type[0] == 8
    
    pdf_doc.close()
