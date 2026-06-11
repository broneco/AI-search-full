import os
import json
import pytest
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import text
from unittest.mock import AsyncMock, patch

from app.main import app
from app.storage.db import SessionLocal, init_db, engine
from app.storage.models import DBDocument, DBChunk
from app.ingestion.tagger import MetadataTagger
from app.schemas.documents import RelationshipInfo, DocumentConfirmedIngestRequest

client = TestClient(app)


@pytest.fixture(scope="module")
def db_setup():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS chunks CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS documents CASCADE;"))


def test_scan_date_candidates():
    tagger = MetadataTagger()
    sample_text = (
        "Toto je úvodní text směrnice.\n"
        "Vydáno dne 15. 10. 2026 v Praze.\n"
        "Další věty, které nemají žádné datum.\n"
        "Účinnost od: 2026-11-01.\n"
        "Další nepodstatný text."
    )
    candidates = tagger.scan_date_candidates(sample_text)
    
    assert len(candidates) >= 2
    assert "15. 10. 2026" in candidates[0]
    assert "2026-11-01" in candidates[1]


@pytest.mark.anyio
@patch("app.providers.azure_openai.AzureOpenAIProvider.generate")
async def test_tagger_classification_and_date(mock_generate):
    # Setup mock returns
    # First call: date extraction, second call: category, third call: relationships
    mock_generate.side_effect = [
        "2026-06-15",  # date
        "HR",          # category
        '{"relationship_type": "none", "target_document_id": null, "target_document_title": null}' # relationship
    ]

    tagger = MetadataTagger()
    sample_text = "Náborový proces ve společnosti Dolphin Consulting.\nVytvořeno dne 15. června 2026."
    
    config = {
        "categories": [
            {"key": "HR", "label": "Personální", "description": "Lidské zdroje", "allowed_groups": ["HR"]}
        ],
        "analysis_rules": ""
    }
    
    date_str = await tagger.determine_release_date(sample_text, "dummy.pdf")
    category = await tagger.classify_category(sample_text, config)
    relationship = await tagger.detect_relationships(sample_text)
    
    assert date_str == "2026-06-15"
    assert category == "HR"
    assert relationship["relationship_type"] == "none"


def test_categories_api_endpoints():
    # 1. Test GET categories
    get_res = client.get("/api/documents/categories")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "categories" in data
    assert "analysis_rules" in data
    
    # Check that it contains standard categories
    keys = [cat["key"] for cat in data["categories"]]
    assert "Management" in keys
    assert "HR" in keys

    # 2. Test POST categories (editing)
    original_config = data
    edited_config = data.copy()
    edited_config["analysis_rules"] = "Custom test rules"
    
    post_res = client.post("/api/documents/categories", json=edited_config)
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "success"
    
    # Check that update actually stored it
    check_res = client.get("/api/documents/categories")
    assert check_res.json()["analysis_rules"] == "Custom test rules"

    # Restore original configuration
    client.post("/api/documents/categories", json=original_config)


@pytest.mark.anyio
@patch("app.providers.azure_openai.AzureOpenAIProvider.generate")
@patch("app.ingestion.extraction.DocumentExtractor.extract")
async def test_analyze_draft_api_endpoint(mock_extract, mock_generate, db_setup, tmp_path):
    from unittest.mock import MagicMock
    from app.ingestion.extraction import ExtractedPage

    mock_extract.return_value = [
        ExtractedPage(page_number=1, text="Směrnice Dolphin Consulting o bezpečnosti z 24. 12. 2026.")
    ]
    mock_generate.side_effect = [
        "2026-12-24", # Date
        "Management", # Category
        '{"relationship_type": "none", "target_document_id": null, "target_document_title": null}' # relationship
    ]

    # Create dummy pdf file path
    dummy_pdf = tmp_path / "test_policy.pdf"
    dummy_pdf.write_text("dummy pdf contents", encoding="utf-8")

    with open(dummy_pdf, "rb") as f:
        res = client.post(
            "/api/documents/analyze-draft",
            files={"file": ("test_policy.pdf", f, "application/pdf")}
        )
    
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "test_policy"
    assert data["suggested_date"] == "2026-12-24"
    assert data["suggested_category"] == "Management"
    assert "temp_file_path" in data
    
    # Cleanup temp file
    if os.path.exists(data["temp_file_path"]):
        os.remove(data["temp_file_path"])


@pytest.mark.anyio
@patch("app.providers.azure_openai.AzureOpenAIEmbeddingProvider.embed_documents")
async def test_ingest_confirmed_with_archival(mock_embed, db_setup, tmp_path):
    db = db_setup
    mock_embed.return_value = [[0.1] * 1536]

    # 1. Create a dummy base document to be replaced
    old_doc = DBDocument(
        source_type="local",
        source_uri="file://old_doc.pdf",
        title="Old Document v1",
        document_type="policy",
        freshness_status="current",
        security_acl={"allowed_groups": ["HR"]},
        created_at=datetime.datetime(2026, 1, 1),
    )
    db.add(old_doc)
    db.commit()
    db.refresh(old_doc)
    
    old_chunk = DBChunk(
        document_id=old_doc.document_id,
        chunk_index=0,
        content="This is the old HR policy details.",
        embedding=[0.0] * 1536,
        freshness_status="current",
        security_acl={"allowed_groups": ["HR"]}
    )
    db.add(old_chunk)
    db.commit()

    # 2. Create the temp upload file to be ingested
    temp_file = tmp_path / "temp_confirmed.txt"
    temp_file.write_text("Tato nova smernice nahrazuje puvodni HR dokument.", encoding="utf-8")

    # Ingestion confirmed request
    req = {
        "title": "New Document v2",
        "date": "2026-06-11",
        "category": "HR",
        "relationship": {
            "relationship_type": "replaces",
            "target_document_id": str(old_doc.document_id),
            "target_document_title": old_doc.title
        },
        "temp_file_path": str(temp_file),
        "original_filename": "temp_confirmed.txt"
    }

    res = client.post("/api/documents/ingest-confirmed", json=req)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Refresh sessions
    db.expire_all()

    # 3. Assert old document is archived
    updated_old_doc = db.query(DBDocument).filter(DBDocument.document_id == old_doc.document_id).first()
    assert updated_old_doc.freshness_status == "archived"
    assert updated_old_doc.metadata_json["replaced_by_document_title"] == "New Document v2"
    
    # Assert old chunks are archived
    updated_old_chunk = db.query(DBChunk).filter(DBChunk.document_id == old_doc.document_id).first()
    assert updated_old_chunk.freshness_status == "archived"

    # 4. Assert new document is current and links back to old document
    new_doc = db.query(DBDocument).filter(DBDocument.title == "New Document v2").first()
    assert new_doc is not None
    assert new_doc.freshness_status == "current"
    assert new_doc.metadata_json["replaces_document_id"] == str(old_doc.document_id)
    assert new_doc.metadata_json["replaces_document_title"] == "Old Document v1"
    
    # Assert new document's allowed groups match Category HR from config (Management + HR)
    assert "HR" in new_doc.security_acl["allowed_groups"]
    assert "Management" in new_doc.security_acl["allowed_groups"]
    assert "User" not in new_doc.security_acl["allowed_groups"]


@pytest.mark.anyio
async def test_category_migration_api_endpoint(db_setup):
    db = db_setup

    # 1. Fetch current config to restore it later
    get_res = client.get("/api/documents/categories")
    assert get_res.status_code == 200
    original_config = get_res.json()

    # 2. Seed a document and chunk in the deleted category
    doc = DBDocument(
        source_type="local",
        source_uri="file://test_migrated.pdf",
        title="Migrated Document",
        document_type="policy",
        freshness_status="current",
        security_acl={"allowed_groups": ["SecretGroup"]},
        metadata_json={"department": "DELETED_CAT_UUID"},
        created_at=datetime.datetime.utcnow(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    chunk = DBChunk(
        document_id=doc.document_id,
        chunk_index=0,
        content="Migrated chunk content.",
        embedding=[0.0] * 1536,
        freshness_status="current",
        security_acl={"allowed_groups": ["SecretGroup"]}
    )
    db.add(chunk)
    db.commit()

    # 3. Request categories configuration update with migrations
    new_categories = [
        {
            "key": "REPLACEMENT_CAT_UUID",
            "label": "Replacement Cat",
            "description": "Allowed group for replacements",
            "allowed_groups": ["ReplacementGroup"],
            "role_name": "ReplacementRole"
        }
    ]
    payload = {
        "categories": new_categories,
        "analysis_rules": "Test migration rules",
        "category_migrations": {
            "DELETED_CAT_UUID": "REPLACEMENT_CAT_UUID"
        }
    }

    try:
        res = client.post("/api/documents/categories", json=payload)
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        # Refresh session
        db.expire_all()

        # 4. Verify document was migrated
        migrated_doc = db.query(DBDocument).filter(DBDocument.document_id == doc.document_id).first()
        assert migrated_doc.metadata_json["department"] == "REPLACEMENT_CAT_UUID"
        assert migrated_doc.security_acl["allowed_groups"] == ["ReplacementGroup"]

        # Verify chunk was migrated
        migrated_chunk = db.query(DBChunk).filter(DBChunk.document_id == doc.document_id).first()
        assert migrated_chunk.security_acl["allowed_groups"] == ["ReplacementGroup"]

    finally:
        # Restore original configuration
        client.post("/api/documents/categories", json=original_config)
        # Clean up database records
        db.delete(chunk)
        db.delete(doc)
        db.commit()
