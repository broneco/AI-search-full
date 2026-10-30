"""Profile-isolated vector repositories; native exact SQL and local reference."""
from dataclasses import asdict
import hashlib
import heapq
import json
import math
import uuid

from sqlalchemy import Column, Integer, String, Text, Table, MetaData, ForeignKey, Identity
from sqlalchemy import bindparam, cast, delete, func, insert, select, event, inspect, literal_column
from sqlalchemy.orm import Session
from sqlalchemy.types import UserDefinedType
from sqlalchemy.exc import DBAPIError
from sqlalchemy.dialects.mssql import NVARCHAR

from app.core.config import settings
from app.providers.embeddings import EmbeddingProfile
from app.retrieval.filters import exact_value, eligibility_filters
from app.storage.models import DBActiveSearchIndex, DBChunk, DBDocument, DBEmbeddingProfile, DBSearchIndex
from app.storage.sql_joins import InnerHashJoin


class SearchIndexError(ValueError):
    """Explicit setup/profile failure; never retry with another vector space."""


class NativeVector(UserDefinedType):
    cache_ok = True
    def __init__(self, dimensions: int):
        if type(dimensions) is not int or not 1 <= dimensions <= 1998:
            raise SearchIndexError("Native float32 VECTOR supports 1..1998 dimensions; no truncation is allowed.")
        self.dimensions = dimensions

    def get_col_spec(self, **kwargs):
        return f"VECTOR({self.dimensions})"


def _native_vector_cast(value, dimensions: int):
    # ODBC can bind long JSON as legacy NTEXT, which cannot cast directly to VECTOR.
    return cast(cast(value, NVARCHAR(None)), NativeVector(dimensions))


def revision(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def tenant_key(tenant: str) -> str:
    return revision(tenant)


def index_profile(session: Session, index: DBSearchIndex) -> EmbeddingProfile:
    stored = session.get(DBEmbeddingProfile, index.profile_id)
    if stored is None:
        raise SearchIndexError("Index profile is missing.")
    try:
        profile = EmbeddingProfile(**stored.definition)
    except (TypeError, ValueError, AttributeError) as error:
        raise SearchIndexError("Stored embedding profile is invalid.") from error
    if profile.profile_id != index.profile_id:
        raise SearchIndexError("Stored embedding profile was changed; create a new profile instead.")
    return profile


def vector_table(index: DBSearchIndex, profile: EmbeddingProfile) -> Table:
    # Even a corrupted catalog cannot inject identifiers or select a different table.
    if index.profile_id != profile.profile_id:
        raise SearchIndexError("Vector table profile mismatch.")
    expected = f"chunk_vectors_{index.index_id.hex}"
    if index.table_name != expected or index.storage_kind not in {"native", "local_json"}:
        raise SearchIndexError("Invalid server index catalog entry.")
    if index.storage_kind == "native":
        NativeVector(profile.dimensions)
    return Table(expected, MetaData(),
        Column("vector_id", Integer, Identity(), primary_key=True, autoincrement=True),
        Column("chunk_id", DBChunk.chunk_id.type, ForeignKey(DBChunk.chunk_id, ondelete="CASCADE"), nullable=False, unique=True),
        Column("input_revision", String(64), nullable=False),
        # JSON parameter transport; native DDL overrides just this column type.
        Column("embedding", Text, nullable=False),
        schema="dbo" if index.storage_kind == "native" else None,
    )


def provision_index(session: Session, tenant: str, profile: EmbeddingProfile, *, native: bool) -> DBSearchIndex:
    """Explicit provisioning, never called by cloud runtime writes."""
    if native:
        NativeVector(profile.dimensions)
    existing = session.get(DBEmbeddingProfile, profile.profile_id)
    if existing is None:
        session.add(DBEmbeddingProfile(profile_id=profile.profile_id, definition=asdict(profile)))
    elif existing.definition != asdict(profile):
        raise SearchIndexError("Immutable profile definition mismatch.")
    ident = uuid.uuid4()
    index = DBSearchIndex(index_id=ident, tenant_id=tenant, profile_id=profile.profile_id,
                          table_name=f"chunk_vectors_{ident.hex}", storage_kind="native" if native else "local_json",
                          corpus_id="tenant-chunks-v1")
    session.add(index)
    session.flush()
    table = vector_table(index, profile)
    if native:
        table.c.embedding.type = NativeVector(profile.dimensions)
    table.create(session.connection())
    return index


def active_index(session: Session, tenant: str, profile: EmbeddingProfile) -> DBSearchIndex:
    try:
        active = session.get(DBActiveSearchIndex, tenant_key(tenant))
    except DBAPIError as error:
        raise SearchIndexError("Search catalog is unavailable; complete the database migration before search.") from error
    if active is None or active.tenant_id != tenant:
        raise SearchIndexError("No active search index. Provision, backfill and activate an index first.")
    index = session.get(DBSearchIndex, active.index_id)
    if index is None or index.tenant_id != tenant or index.corpus_id != "tenant-chunks-v1":
        raise SearchIndexError("Active index does not belong to this tenant/corpus.")
    if index_profile(session, index) != profile:
        raise SearchIndexError("Query provider profile differs from the active index profile.")
    if settings.DATABASE_BACKEND == "azure_sql" and index.storage_kind != "native":
        raise SearchIndexError("Azure exact search requires native storage; local JSON is not a cloud fallback.")
    return index


def coverage(session: Session, index: DBSearchIndex) -> tuple[int, int]:
    profile = index_profile(session, index)
    vectors = vector_table(index, profile)
    tenant_filter = exact_value(DBChunk.tenant_id, index.tenant_id, session.bind.dialect.name)
    stmt = select(func.count()).select_from(DBChunk).join(DBDocument).where(
        tenant_filter, exact_value(DBDocument.tenant_id, index.tenant_id, session.bind.dialect.name))
    total = session.scalar(stmt)
    valid = session.scalar(stmt.join(vectors, vectors.c.chunk_id == DBChunk.chunk_id).where(
        vectors.c.input_revision == DBChunk.content_hash, DBChunk.content_hash.is_not(None)))
    return valid, total


def activate_index(session: Session, index: DBSearchIndex) -> None:
    """Caller stops writes during activation; coverage must be complete."""
    if settings.DATABASE_BACKEND == "azure_sql" and index.storage_kind != "native":
        raise SearchIndexError("A local JSON index cannot be activated for Azure SQL.")
    valid, total = coverage(session, index)
    if valid != total:
        raise SearchIndexError(f"Incomplete index coverage: {valid}/{total} current chunks.")
    key = tenant_key(index.tenant_id)
    active = session.get(DBActiveSearchIndex, key)
    if active is None:
        session.add(DBActiveSearchIndex(tenant_key=key, tenant_id=index.tenant_id, index_id=index.index_id))
    else:
        active.index_id = index.index_id
    session.flush()


def write_embeddings(session: Session, index: DBSearchIndex, profile: EmbeddingProfile, rows: list[dict]) -> None:
    """Write known-profile vectors; chunk revisions/tenants are verified first."""
    if index_profile(session, index) != profile:
        raise SearchIndexError("Embedding profile mismatch.")
    profile.validate_vectors([row["embedding"] for row in rows])
    if any(not any(value != 0 for value in row["embedding"]) for row in rows):
        raise SearchIndexError("Cosine search requires non-zero vectors.")
    table = vector_table(index, profile)
    for start in range(0, len(rows), 200):
        batch = rows[start:start + 200]
        chunks = dict(session.execute(select(DBChunk.chunk_id, DBChunk).where(
            DBChunk.chunk_id.in_([row["chunk_id"] for row in batch]))).all())
        parameters = []
        for row in batch:
            chunk = chunks.get(row["chunk_id"])
            if chunk is None or chunk.tenant_id != index.tenant_id or chunk.content_hash != row["input_revision"]:
                raise SearchIndexError("Embedding input revision/tenant mismatch.")
            parameters.append({"chunk_id": chunk.chunk_id, "input_revision": chunk.content_hash,
                               "vector_json": json.dumps(row["embedding"], allow_nan=False)})
        if not parameters:
            continue
        session.execute(delete(table).where(table.c.chunk_id.in_([row["chunk_id"] for row in batch])))
        value = bindparam("vector_json", type_=Text)
        if index.storage_kind == "native":
            value = _native_vector_cast(value, profile.dimensions)
        session.execute(insert(table).values(embedding=value), parameters)


def write_chunks(session: Session, mappings: list[dict], profile: EmbeddingProfile) -> None:
    """Shared transactional chunk + ACL + explicit-profile embedding write."""
    from app.storage.acl import insert_chunks
    if not mappings:
        return
    profile.validate_vectors([row["embedding"] for row in mappings])
    rows = [{**row, "chunk_id": row.get("chunk_id") or uuid.uuid4(), "content_hash": revision(row["content"])}
            for row in mappings]
    for row in rows:
        row["metadata_json"] = {**(row.get("metadata_json") or {}), "embedding_profile_id": profile.profile_id}
    insert_chunks(session, rows)
    parents = dict(session.execute(select(DBDocument.document_id, DBDocument.tenant_id).where(
        DBDocument.document_id.in_({row["document_id"] for row in rows}))).all())
    for tenant in set(parents.values()):
        indexes = session.scalars(select(DBSearchIndex).where(
            exact_value(DBSearchIndex.tenant_id, tenant, session.bind.dialect.name),
            DBSearchIndex.profile_id == profile.profile_id)).all()
        if not indexes:
            if settings.DATABASE_BACKEND == "azure_sql":
                raise SearchIndexError("Provision a native index for this profile before ingestion.")
            indexes = [provision_index(session, tenant, profile, native=False)]
        subset = [{"chunk_id": row["chunk_id"], "embedding": row["embedding"],
                   "input_revision": row["content_hash"]} for row in rows if parents[row["document_id"]] == tenant]
        for index in indexes:
            write_embeddings(session, index, profile, subset)


def activate_local_ready_index(session: Session, profile: EmbeddingProfile) -> None:
    """Only a fresh local corpus may auto-activate its one complete index."""
    if settings.APP_ENV != "local" or settings.DATABASE_BACKEND != "sqlserver":
        return
    if session.get(DBActiveSearchIndex, tenant_key(settings.TENANT_ID)) is not None:
        return
    indexes = session.scalars(select(DBSearchIndex).where(
        exact_value(DBSearchIndex.tenant_id, settings.TENANT_ID, session.bind.dialect.name),
        DBSearchIndex.profile_id == profile.profile_id)).all()
    if len(indexes) != 1:
        raise SearchIndexError("Choose and activate one local index with migrate_search_vectors.py.")
    activate_index(session, indexes[0])


@event.listens_for(Session, "before_flush")
def invalidate_changed_inputs(session, flush_context, instances):
    for owner in session.dirty:
        if isinstance(owner, DBEmbeddingProfile) and inspect(owner).attrs.definition.history.has_changes():
            raise SearchIndexError("Embedding profiles are immutable; create a new profile.")
        if isinstance(owner, DBSearchIndex) and any(inspect(owner).attrs[name].history.has_changes()
            for name in ("profile_id", "tenant_id", "corpus_id", "table_name", "storage_kind")):
            raise SearchIndexError("Search index identity is immutable; create a new index.")
    changed = []
    for chunk in list(session.new) + list(session.dirty):
        if not isinstance(chunk, DBChunk) or chunk in session.deleted:
            continue
        if chunk in session.new or inspect(chunk).attrs.content.history.has_changes():
            chunk.content_hash = revision(chunk.content)
            if chunk not in session.new:
                changed.append(chunk.chunk_id)
    session.info.setdefault("changed_vector_inputs", set()).update(changed)


@event.listens_for(Session, "after_flush_postexec")
def remove_stale_embeddings(session, flush_context):
    ids = session.info.pop("changed_vector_inputs", set())
    if not ids:
        return
    for index in session.scalars(select(DBSearchIndex)).all():
        table = vector_table(index, index_profile(session, index))
        for start in range(0, len(ids), 200):
            session.execute(delete(table).where(table.c.chunk_id.in_(list(ids)[start:start + 200])))


@event.listens_for(Session, "after_rollback")
def clear_pending_invalidations(session):
    session.info.pop("changed_vector_inputs", None)


def exact_statement(index: DBSearchIndex, profile: EmbeddingProfile, context, query: list[float], limit: int):
    """Native SQL applies all eligibility predicates before ordered TOP K."""
    vectors = vector_table(index, profile)
    distance = func.VECTOR_DISTANCE(literal_column("'cosine'"),
        _native_vector_cast(bindparam("query_json", json.dumps(query), type_=Text), profile.dimensions),
        vectors.c.embedding)
    return (select(DBChunk, DBDocument, (1.0 - distance).label("vector_score"))
            .select_from(InnerHashJoin(
                InnerHashJoin(DBChunk.__table__, DBDocument.__table__,
                              DBChunk.document_id == DBDocument.document_id),
                vectors, vectors.c.chunk_id == DBChunk.chunk_id))
            .where(*eligibility_filters(context, "mssql"), vectors.c.input_revision == DBChunk.content_hash)
            .order_by(distance, vectors.c.vector_id).limit(limit))


def exact_candidates(session: Session, context, query: list[float], profile: EmbeddingProfile, limit: int,
                     *, index: DBSearchIndex | None = None):
    if limit < 1:
        raise SearchIndexError("Exact search limit must be greater than zero.")
    profile.validate_vector(query)
    if not any(value != 0 for value in query):
        raise SearchIndexError("Query cosine vector must be non-zero.")
    index = index or active_index(session, context.tenant_id, profile)
    if index.tenant_id != context.tenant_id or index.profile_id != profile.profile_id:
        raise SearchIndexError("Selected exact index tenant/profile mismatch.")
    if settings.DATABASE_BACKEND == "azure_sql" and index.storage_kind != "native":
        raise SearchIndexError("Azure exact search requires native storage.")
    if index.storage_kind == "native":
        from sqlalchemy.orm import defer
        rows = session.execute(exact_statement(index, profile, context, query, limit).options(defer(DBChunk.embedding))).all()
        return [(row[0], row[1], 0.0, float(row[2])) for row in rows]

    # Local SQL Server 2022 / SQLite reference: stream ALL eligible vectors,
    # keep only K scores, and close the cursor before fetching text (no MARS).
    table = vector_table(index, profile)
    stmt = (select(DBChunk.chunk_id, table.c.embedding, table.c.vector_id).join(DBDocument).join(table, table.c.chunk_id == DBChunk.chunk_id)
            .where(*eligibility_filters(context, session.bind.dialect.name), table.c.input_revision == DBChunk.content_hash))
    norm = math.sqrt(sum(value * value for value in query))
    heap = []
    cursor = session.execute(stmt)
    try:
        for batch in cursor.partitions(200):
            for cid, encoded, vector_id in batch:
                vector = json.loads(encoded)
                profile.validate_vector(vector)
                vector_norm = math.sqrt(sum(value * value for value in vector))
                score = sum(a * b for a, b in zip(query, vector)) / (norm * vector_norm)
                candidate = (score, -vector_id, cid)
                if len(heap) < limit:
                    heapq.heappush(heap, candidate)
                elif candidate > heap[0]:
                    heapq.heapreplace(heap, candidate)
    finally:
        cursor.close()
    if not heap:
        return []
    winners = sorted(heap, reverse=True)
    rows = session.execute(select(DBChunk, DBDocument).join(DBDocument).where(
        DBChunk.chunk_id.in_([item[2] for item in winners]), *eligibility_filters(context, session.bind.dialect.name))).all()
    by_id = {row[0].chunk_id: row for row in rows}
    return [(by_id[cid][0], by_id[cid][1], 0.0, score) for score, _, cid in winners if cid in by_id]
