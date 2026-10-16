"""Tenant and failure isolation of administrative refresh paths, without models/Azure."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.ingestion import refresh
from app.providers.embeddings import EmbeddingProfile
from app.storage.models import Base, DBDocument, DBChunk


@pytest.fixture
def maintenance(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def fk(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "TENANT_ID", "ju-prod")
    monkeypatch.setattr(settings, "DATABASE_BACKEND", "postgresql")
    monkeypatch.setattr(settings, "USE_AZURE_SQL", False)
    monkeypatch.setattr(refresh, "SessionLocal", factory)
    monkeypatch.setattr("app.storage.db.SessionLocal", factory)
    provider = SimpleNamespace(profile=EmbeddingProfile("audit", "1", 2),
        embed_documents=AsyncMock(side_effect=lambda texts: [[1., 0.] for _ in texts]))
    monkeypatch.setattr("app.ingestion.pipeline.create_embedding_provider", lambda: provider)
    monkeypatch.setattr("app.providers.blob_storage.BlobStorageProvider.is_configured", lambda self: False)
    for tenant, name in [("ju-prod", "current"), ("other-prod", "foreign")]:
        file = Path("data") / name / "doc.txt"
        file.parent.mkdir(parents=True)
        file.write_text(name + " unique content", encoding="utf-8")
        with factory() as db:
            doc = DBDocument(tenant_id=tenant, title=name, source_type="local",
                source_uri=f"file://{name}/doc.txt", document_type="test", checksum="old")
            db.add(doc)
            db.flush()
            db.add(DBChunk(document_id=doc.document_id, chunk_index=0, content="old-"+name,
                           embedding=[1., 0.], security_acl={"allowed_groups": ["User"]}))
            db.commit()
    tagger = SimpleNamespace(load_config=AsyncMock(return_value={"categories": [
        {"key": "User", "allowed_groups": ["User"]}]}), analyze_file=AsyncMock(return_value={
        "title": "replacement", "suggested_category": "User", "suggested_date": "2026-01-01", "suggested_language": "cs"}))
    monkeypatch.setattr(refresh, "MetadataTagger", lambda **kw: tagger)
    yield factory, provider, tagger
    engine.dispose()


def contents(factory):
    with factory() as db:
        return [(d.tenant_id, c.content) for d, c in db.execute(select(DBDocument, DBChunk).join(DBChunk)).all()]


def test_fast_reindex_cannot_process_foreign_tenant(maintenance):
    from app.api.routes.documents import run_reindex_all_task, reindex_progress
    factory, provider, tagger = maintenance
    asyncio.run(run_reindex_all_task("ju-prod"))
    assert reindex_progress["status"] == "completed"
    assert ("other-prod", "old-foreign") in contents(factory)
    assert all("foreign" not in text for call in provider.embed_documents.await_args_list for text in call.args[0])
    assert any(tenant == "ju-prod" and "unique content" in text for tenant, text in contents(factory))


def test_refresh_rejects_invalid_sources_without_writes(maintenance, tmp_path):
    factory, provider, tagger = maintenance
    before = contents(factory)
    with pytest.raises(FileNotFoundError):
        refresh.refresh_files("ju-prod", str(tmp_path/"missing"))
    empty = tmp_path/"empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no PDF/TXT"):
        refresh.refresh_files("ju-prod", str(empty))
    with pytest.raises(ValueError, match="exactly match"):
        refresh.refresh_files("ju", str(empty))
    assert contents(factory) == before
    provider.embed_documents.assert_not_called()


def test_fast_reindex_never_substitutes_a_foreign_file_with_same_name(maintenance):
    from app.api.routes.documents import run_reindex_all_task, reindex_progress
    factory, provider, tagger = maintenance
    before = contents(factory)
    Path("data/current/doc.txt").unlink()
    asyncio.run(run_reindex_all_task("ju-prod"))
    assert reindex_progress["status"] == "failed"
    assert contents(factory) == before
    provider.embed_documents.assert_not_called()


def test_refresh_failure_retains_entire_remaining_corpus(maintenance):
    factory, provider, tagger = maintenance
    provider.embed_documents.side_effect = RuntimeError("synthetic embedding failure")
    before = contents(factory)
    files = refresh.refresh_files("ju-prod", "data/current")
    with pytest.raises(RuntimeError, match="synthetic"):
        asyncio.run(refresh.refresh_documents("ju-prod", files))
    assert contents(factory) == before


def test_refresh_preserves_exact_tenant_and_foreign_documents(maintenance):
    factory, provider, tagger = maintenance
    files = refresh.refresh_files("ju-prod", "data/current")
    asyncio.run(refresh.refresh_documents("ju-prod", files))
    assert ("other-prod", "old-foreign") in contents(factory)
    assert any(tenant == "ju-prod" and "unique content" in text for tenant, text in contents(factory))
    assert not any(tenant == "ju" for tenant, text in contents(factory))


def test_full_refresh_cli_is_plan_only_without_apply(maintenance, monkeypatch, capsys):
    import full_refresh_ingest
    factory, provider, tagger = maintenance
    before = contents(factory)
    assert full_refresh_ingest.main(["--tenant", "ju-prod", "--data-dir", "data/current"]) == 0
    assert '"apply": false' in capsys.readouterr().out
    assert contents(factory) == before
    provider.embed_documents.assert_not_called()
    with pytest.raises(ValueError, match="expect-tenant"):
        full_refresh_ingest.main(["--tenant", "ju-prod", "--data-dir", "data/current", "--apply"])


def test_success_prunes_only_initial_stale_documents(maintenance):
    factory, provider, tagger = maintenance
    replacement = Path("data/replacement/new.txt")
    replacement.parent.mkdir()
    replacement.write_text("new source", encoding="utf-8")
    files = refresh.refresh_files("ju-prod", "data/replacement")
    asyncio.run(refresh.refresh_documents("ju-prod", files))
    rows = contents(factory)
    assert ("other-prod", "old-foreign") in rows
    assert ("ju-prod", "old-current") not in rows
    assert ("ju-prod", "new source") in rows


def test_late_model_failure_does_not_prune_remaining_documents(maintenance):
    factory, provider, tagger = maintenance
    Path("data/current/a-new.txt").write_text("new source", encoding="utf-8")
    provider.embed_documents.side_effect = [[[1., 0.]], RuntimeError("late model failure")]
    files = refresh.refresh_files("ju-prod", "data/current")
    with pytest.raises(RuntimeError, match="late"):
        asyncio.run(refresh.refresh_documents("ju-prod", files))
    assert ("ju-prod", "old-current") in contents(factory)
    assert ("other-prod", "old-foreign") in contents(factory)


def test_relationships_follow_replaced_document_ids(maintenance):
    factory, provider, tagger = maintenance
    with factory() as db:
        original_id = db.scalar(select(DBDocument.document_id).where(DBDocument.tenant_id == "ju-prod"))
    Path("data/current/new.txt").write_text("new version", encoding="utf-8")
    async def analyze(name):
        suggestion = {"title": Path(name).stem, "suggested_category": "User", "suggested_language": "cs",
                      "suggested_date": "2026-01-01" if Path(name).stem == "doc" else "2026-02-01"}
        if Path(name).stem == "new":
            suggestion["relationship"] = {"relationship_type": "replaces", "target_document_id": str(original_id)}
        return suggestion
    tagger.analyze_file.side_effect = analyze
    asyncio.run(refresh.refresh_documents("ju-prod", refresh.refresh_files("ju-prod", "data/current")))
    with factory() as db:
        docs = list(db.scalars(select(DBDocument).where(DBDocument.tenant_id == "ju-prod")))
        old = next(doc for doc in docs if doc.title == "doc")
        new = next(doc for doc in docs if doc.title == "new")
        assert old.freshness_status == "archived"
        assert new.metadata_json["replaces_document_id"] == str(old.document_id)
        assert old.metadata_json["replaced_by_document_id"] == str(new.document_id)


def test_relationship_model_never_receives_foreign_document_titles(maintenance):
    from app.ingestion.tagger import MetadataTagger
    factory, provider, fake_tagger = maintenance
    with factory() as db:
        tagger = MetadataTagger(db_session=db)
        generate = AsyncMock(return_value='{"relationship_type":"none"}')
        tagger.llm = SimpleNamespace(generate=generate)
        asyncio.run(tagger.detect_relationships("synthetic excerpt"))
        prompt = generate.await_args.args[0][0].content
        assert '"title": "current"' in prompt
        assert '"title": "foreign"' not in prompt
        foreign_id = db.scalar(select(DBDocument.document_id).where(DBDocument.tenant_id == "other-prod"))
        generate.return_value = '{"relationship_type":"replaces","target_document_id":"' + str(foreign_id) + '"}'
        relation = asyncio.run(tagger.detect_relationships("synthetic excerpt"))
        assert relation["relationship_type"] == "none"
        assert relation["target_document_id"] is None


def test_concurrent_upload_is_not_pruned(maintenance):
    factory, provider, tagger = maintenance
    original_analyze = tagger.analyze_file.return_value
    async def analyze(name):
        with factory() as db:
            db.add(DBDocument(tenant_id="ju-prod", source_type="local", source_uri="file://concurrent.txt",
                              title="concurrent", document_type="test", checksum="concurrent"))
            db.commit()
        return original_analyze
    tagger.analyze_file.side_effect = analyze
    asyncio.run(refresh.refresh_documents("ju-prod", refresh.refresh_files("ju-prod", "data/current")))
    with factory() as db:
        assert db.scalar(select(DBDocument).where(DBDocument.title == "concurrent")) is not None


def test_concurrently_changed_stale_document_cancels_cleanup(maintenance):
    factory, provider, tagger = maintenance
    replacement = Path("data/replacement/new.txt")
    replacement.parent.mkdir()
    replacement.write_text("new source", encoding="utf-8")
    original_analyze = tagger.analyze_file.return_value
    async def analyze(name):
        with factory() as db:
            current = db.scalar(select(DBDocument).where(DBDocument.tenant_id == "ju-prod"))
            current.checksum = "concurrent-edit"
            db.commit()
        return original_analyze
    tagger.analyze_file.side_effect = analyze
    with pytest.raises(ValueError, match="Corpus changed"):
        asyncio.run(refresh.refresh_documents("ju-prod", refresh.refresh_files("ju-prod", "data/replacement")))
    with factory() as db:
        assert db.scalar(select(DBDocument).where(DBDocument.checksum == "concurrent-edit")) is not None
    assert ("other-prod", "old-foreign") in contents(factory)
