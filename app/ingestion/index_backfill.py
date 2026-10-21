"""Explicit backfill from current chunk text or proven legacy provenance."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session, defer

from app.providers.embeddings import EmbeddingProvider
from app.retrieval.filters import exact_value
from app.storage.models import DBChunk, DBDocument, DBSearchIndex
from app.storage.vector_store import index_profile, revision, vector_table, write_embeddings, SearchIndexError


async def backfill_index(session: Session, index: DBSearchIndex, *, provider: EmbeddingProvider | None = None,
                         proven_legacy: bool = False, batch_size: int = 32, authorize=None) -> int:
    """Each batch commits atomically; retries skip current revisions.

    proven_legacy requires per-chunk profile_id AND content_hash evidence.
    Supplying a provider explicitly re-embeds current text, retaining legacy
    JSON vectors. No extraction, chunking or LLM enrichment is performed.
    Run with ingestion stopped for a deterministic activation snapshot.
    """
    profile = index_profile(session, index)
    if not 1 <= batch_size <= 200:
        raise ValueError("Backfill batch size must be 1..200.")
    if provider is not None and provider.profile != profile:
        raise SearchIndexError("Backfill provider differs from index profile.")
    if provider is None and not proven_legacy:
        raise SearchIndexError("Backfill requires a provider or proven per-chunk legacy provenance.")
    table = vector_table(index, profile)
    completed = 0
    last_id = None
    while True:
        if authorize:
            authorize()
        stmt = (select(DBChunk).join(DBDocument).where(
            exact_value(DBChunk.tenant_id, index.tenant_id, session.bind.dialect.name),
            exact_value(DBDocument.tenant_id, index.tenant_id, session.bind.dialect.name))
            .order_by(DBChunk.chunk_id).limit(batch_size))
        if provider is not None:
            stmt = stmt.options(defer(DBChunk.embedding))
        if last_id is not None:
            stmt = stmt.where(DBChunk.chunk_id > last_id)
        chunks = session.scalars(stmt).all()
        if not chunks:
            break
        last_id = chunks[-1].chunk_id
        stored = dict(session.execute(select(table.c.chunk_id, table.c.input_revision).where(
            table.c.chunk_id.in_([chunk.chunk_id for chunk in chunks]))).all())
        pending = [chunk for chunk in chunks if stored.get(chunk.chunk_id) != revision(chunk.content)
                   or chunk.content_hash != revision(chunk.content)]
        if not pending:
            continue
        snapshots = [(chunk.chunk_id, chunk.content, revision(chunk.content), chunk.embedding if provider is None else None,
                      dict(chunk.metadata_json or {}), chunk.content_hash) for chunk in pending]
        session.commit()  # release read transaction before the model call
        if provider is not None:
            vectors = await provider.embed_documents([item[1] for item in snapshots])
        else:
            if any(item[4].get("embedding_profile_id") != profile.profile_id or item[5] != item[2]
                   for item in snapshots):
                raise SearchIndexError("Legacy vector provenance/revision is unproven; use explicit reembedding.")
            vectors = [json.loads(item[3]) if isinstance(item[3], str) else item[3] for item in snapshots]
        if len(vectors) != len(snapshots):
            raise SearchIndexError("Incomplete backfill embedding batch.")
        profile.validate_vectors(vectors)
        try:
            if authorize:
                authorize()
            rows = []
            # Recheck the complete batch once after the model call. Scalar get()
            # per chunk also autoflushed the previous update on every iteration.
            refreshed = session.scalars(select(DBChunk).where(
                DBChunk.chunk_id.in_([item[0] for item in snapshots]))
                .options(defer(DBChunk.embedding)).execution_options(populate_existing=True)
                .with_hint(DBChunk, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")).all()
            by_id = {chunk.chunk_id: chunk for chunk in refreshed}
            for (cid, content, digest, _, _, _), vector in zip(snapshots, vectors):
                chunk = by_id.get(cid)
                if chunk is None or chunk.content != content or chunk.tenant_id != index.tenant_id:
                    raise SearchIndexError("Chunk changed during backfill; retry with ingestion stopped.")
                chunk.content_hash = digest
                rows.append({"chunk_id": cid, "input_revision": digest, "embedding": vector})
            session.flush()
            write_embeddings(session, index, profile, rows)
            session.commit()
        except Exception:
            session.rollback()
            raise
        completed += len(rows)
    return completed
