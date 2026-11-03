"""Per-index chunk preparation from authorized exact originals; shared chunks stay intact."""
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session
from collections.abc import Callable
from app.api.identity import Principal
from app.providers.embeddings import EmbeddingProvider
from app.core.model_config import ModelError
from app.ingestion.chunk_settings import splitter_for
from app.ingestion.extraction import DocumentExtractor
from app.ingestion.sources import document_source
from app.retrieval.filters import exact_value
from app.storage.acl import insert_chunks
from app.storage.models import DBDocument, DBChunk, DBIndexDocument, DBSearchIndex
from app.storage.index_settings import metadata, source_revision, compatible_source_acls
from app.storage.vector_store import revision


def prepare_corpus(db: Session, index: DBSearchIndex, principal: Principal, provider: EmbeddingProvider,
                   check: Callable[[], None], activity: Callable[[str, list[str]], None]) -> None:
    spec = metadata(db, index)
    if spec is None or not spec.chunking:
        raise ModelError("index_settings_missing", "Index nemá uložené nastavení chunkování.", 409)
    snapshot = dict(spec.chunking)
    ids = list(db.scalars(select(DBDocument.document_id).where(
        exact_value(DBDocument.tenant_id, index.tenant_id, db.bind.dialect.name)).order_by(DBDocument.document_id)))
    for ident in ids:
        check()
        doc = db.get(DBDocument, ident, populate_existing=True)
        if doc is None or doc.tenant_id != index.tenant_id:
            raise ModelError("index_corpus_changed", "Dokumenty se během přípravy změnily.", 409)
        if ident not in compatible_source_acls(db, [doc]):
            raise ModelError("chunk_acl_mapping_required", "Dokument má odlišná oprávnění jednotlivých pasáží; nové dělení vyžaduje explicitní mapování oprávnění.", 409)
        expected = source_revision(doc)
        prepared = db.get(DBIndexDocument, (index.index_id, ident))
        count = db.scalar(select(func.count()).select_from(DBChunk).where(DBChunk.document_id == ident,
            DBChunk.corpus_id == index.corpus_id, exact_value(DBChunk.tenant_id, index.tenant_id, db.bind.dialect.name)))
        if prepared is not None and prepared.source_revision == expected and prepared.chunk_count == count:
            db.commit()  # allow heartbeat/cancellation even for already prepared documents
            continue
        # Work on a detached source snapshot, never an open fencing transaction during I/O/model calls.
        from types import SimpleNamespace
        original = SimpleNamespace(source_uri=doc.source_uri, checksum=doc.checksum)
        db.commit()
        activity("extracting", [str(ident)])
        with document_source(original) as path:
            pages = DocumentExtractor().extract(path)
        activity("splitting", [str(ident)])
        splitter = splitter_for(db, principal, snapshot, embedding_provider=provider, force_ai=True)
        db.commit()
        chunks = splitter.split_pages(pages, force_ai=True)
        check()
        current = db.scalar(select(DBDocument).where(DBDocument.document_id == ident)
            .with_hint(DBDocument, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql").execution_options(populate_existing=True))
        if current is None or current.tenant_id != index.tenant_id or source_revision(current) != expected:
            raise ModelError("index_corpus_changed", "Originál se během chunkování změnil; opakujte přípravu.", 409)
        if ident not in compatible_source_acls(db, [current]):
            raise ModelError("chunk_acl_mapping_required", "Oprávnění pasáží se změnila; příprava byla zastavena.", 409)
        db.execute(delete(DBChunk).where(DBChunk.document_id == ident, DBChunk.corpus_id == index.corpus_id,
            exact_value(DBChunk.tenant_id, index.tenant_id, db.bind.dialect.name)))
        insert_chunks(db, [{"document_id": ident, "corpus_id": index.corpus_id, "chunk_index": c.index,
            "content": c.content, "content_hash": revision(c.content), "embedding": None,
            "language": current.language, "section_title": c.section_title, "page_number": c.page_number,
            "security_acl": current.security_acl, "metadata_json": current.metadata_json,
            "freshness_status": current.freshness_status} for c in chunks])
        prepared = db.get(DBIndexDocument, (index.index_id, ident))
        if prepared is None:
            db.add(DBIndexDocument(index_id=index.index_id, document_id=ident, source_revision=expected, chunk_count=len(chunks)))
        else:
            prepared.source_revision = expected; prepared.chunk_count = len(chunks)
        db.commit()
    activity("scanning", [])
