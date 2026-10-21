"""Idempotent university fixtures for the local development database only."""
from collections.abc import Callable
import hashlib
import logging
from pathlib import Path
import shutil
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.ingestion.extraction import DocumentExtractor
from app.providers.embeddings import EmbeddingProvider
from app.providers.factory import create_embedding_profile, create_embedding_provider
from app.core.embedding_selection import active_embedding_provider
from app.storage.vector_store import write_chunks, write_embeddings, provision_index, vector_table, index_profile, revision
from app.storage.models import DBSearchIndex
from sqlalchemy import select, func
from app.storage.models import DBChunk, DBDocument

logger = logging.getLogger(__name__)
FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "local-university"
FIXTURES = (
    ("studijni-rad.pdf", "Aurora: Organizace studia"),
    ("sluzby-studentum.pdf", "Aurora: Služby pro studenty"),
)
SEED_VERSION = "local-university-v1"


def _ready(doc: DBDocument | None, checksum: str, texts: list[str], profile_id: str, dimensions: int, session: Session) -> bool:
    if doc is None:
        return False
    if doc.tenant_id != settings.TENANT_ID or (doc.metadata_json or {}).get("local_demo") != SEED_VERSION:
        raise ValueError("Local demo ID belongs to a different document; refusing to overwrite it.")
    chunks = sorted(doc.chunks, key=lambda chunk: chunk.chunk_index)
    legacy_ready = doc.checksum == checksum and len(chunks) == len(texts) and all(
        chunk.content == content
        and chunk.tenant_id == settings.TENANT_ID
        for chunk, content in zip(chunks, texts)
    )
    if not legacy_ready:
        return False
    indexes = session.scalars(select(DBSearchIndex).where(
        DBSearchIndex.tenant_id == settings.TENANT_ID, DBSearchIndex.profile_id == profile_id)).all()
    for index in indexes:
        table = vector_table(index, index_profile(session, index))
        count = session.scalar(select(func.count()).select_from(DBChunk).join(table,
            table.c.chunk_id == DBChunk.chunk_id).where(DBChunk.document_id == doc.document_id,
            table.c.input_revision == DBChunk.content_hash))
        if count == len(chunks):
            return True
    return False


async def seed_local_demo(
    session_factory: Callable[[], Session], *, provider: EmbeddingProvider | None = None,
    data_root: Path | None = None,
) -> int:
    """Embed missing/changed fixtures in document mode; retain user documents.

    Return the number of documents indexed. No database/model access is made
    outside the local profile, loopback SQL Server and ai_search_local target.
    The injectable session/provider allow isolated database tests.
    """
    if settings.APP_ENV != "local":
        return 0
    if (settings.DATABASE_BACKEND != "sqlserver"
        or settings.AZURE_SQL_HOST not in {"localhost", "127.0.0.1", "::1"}
        or settings.AZURE_SQL_DB != "ai_search_local"):
        raise ValueError("Local demo seeding requires loopback SQL Server / ai_search_local.")

    with session_factory() as session:
        selected_provider = active_embedding_provider(session, settings.TENANT_ID,
                                                       fallback=create_embedding_provider())
    profile = selected_provider.profile
    if provider is not None and provider.profile != profile:
        raise ValueError("Local demo provider does not match the configured embedding profile.")
    target_root = (data_root or Path("data")) / "local-demo" / hashlib.sha256(
        settings.TENANT_ID.encode("utf-8")
    ).hexdigest()[:16]
    fixtures = []
    extractor = DocumentExtractor()
    for filename, title in FIXTURES:
        original = FIXTURE_ROOT / filename
        checksum = hashlib.sha256(original.read_bytes()).hexdigest()
        pages = extractor.extract(str(original))
        texts = [page.text for page in pages]
        if len(pages) != 1 or not texts[0].strip():
            raise ValueError("Each local demo fixture must contain one non-empty text page.")
        document_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{SEED_VERSION}/{settings.TENANT_ID}/{filename}")
        destination = target_root / f"{original.stem}-{checksum[:12]}.pdf"
        fixtures.append((document_id, original, destination, title, checksum, texts))

    # End the read transaction before the network call; keep SQL locks brief.
    with session_factory() as session:
        pending = [fixture for fixture in fixtures if not _ready(
            session.get(DBDocument, fixture[0]), fixture[4], fixture[5], profile.profile_id, profile.dimensions, session
        )]
    if pending:
        if provider is None:
            if (profile == create_embedding_profile()
                and not (settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY)):
                logger.warning("Lokální demo čeká na AZURE_OPENAI_ENDPOINT a AZURE_OPENAI_API_KEY "
                               "v .env.local. Doplň nastavení a restartuj backend; náhodné vektory se nevytvářejí.")
                return 0
            provider = selected_provider
        texts = [content for fixture in pending for content in fixture[5]]
        vectors = await provider.embed_documents(texts)
        if len(vectors) != len(texts):
            raise ValueError("Local demo embedding batch is incomplete.")
        profile.validate_vectors(vectors)

        # Sources have content-addressed names, so an SQL rollback cannot replace
        # the PDF referred to by a previously valid document.
        target_root.mkdir(parents=True, exist_ok=True)
        for fixture in pending:
            shutil.copyfile(fixture[1], fixture[2])
        with session_factory() as session, session.begin():
            offset = 0
            for doc_id, original, destination, title, checksum, contents in pending:
                doc = session.get(DBDocument, doc_id)
                # A new embedding experiment must retain the same chunk IDs/text/ACL
                # and all existing vectors. Only changed source text is re-chunked.
                if (doc is not None and doc.checksum == checksum
                        and len(doc.chunks) == len(contents) and all(
                            c.content == text and c.tenant_id == settings.TENANT_ID
                            for c, text in zip(sorted(doc.chunks, key=lambda c: c.chunk_index), contents))):
                    indexes = session.scalars(select(DBSearchIndex).where(
                        DBSearchIndex.tenant_id == settings.TENANT_ID,
                        DBSearchIndex.profile_id == profile.profile_id)).all()
                    if not indexes:
                        indexes = [provision_index(session, settings.TENANT_ID, profile, native=False)]
                    chunks = sorted(doc.chunks, key=lambda c: c.chunk_index)
                    for index in indexes:
                        write_embeddings(session, index, profile, [
                            {"chunk_id": chunk.chunk_id, "input_revision": chunk.content_hash,
                             "embedding": vectors[offset + i]} for i, chunk in enumerate(chunks)])
                    offset += len(contents)
                    continue
                if doc is None:
                    doc = DBDocument(document_id=doc_id, tenant_id=settings.TENANT_ID)
                    session.add(doc)
                else:
                    _ready(doc, checksum, contents, profile.profile_id, profile.dimensions, session)
                    for chunk in list(doc.chunks):
                        session.delete(chunk)
                metadata = {"local_demo": SEED_VERSION, "source_label": "Lokální demo Aurora",
                            "embedding_profile_id": profile.profile_id}
                doc.source_type, doc.source_uri = "local", str(destination.resolve())
                doc.title, doc.document_type, doc.language = title, "local_demo", "cs"
                doc.checksum, doc.version, doc.freshness_status = checksum, "1", "current"
                doc.security_acl, doc.metadata_json = {"allowed_groups": ["User"]}, metadata
                session.flush()
                write_chunks(session, [
                    {"document_id": doc_id, "chunk_index": index, "page_number": index + 1,
                     "content": content, "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                     "embedding": vectors[offset + index], "language": "cs",
                     "security_acl": {"allowed_groups": ["User"]}, "metadata_json": metadata}
                    for index, content in enumerate(contents)
                ], profile)
                offset += len(contents)

    # Restore a missing local PDF without regenerating valid embeddings.
    for fixture in fixtures:
        if not fixture[2].exists():
            target_root.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixture[1], fixture[2])
    logger.info("Lokální demo Aurora: 2 dokumenty připravené, %s nově indexováno.", len(pending))
    return len(pending)
