"""Index metadata, corpus boundaries and guarded lifecycle operations."""
import hashlib
import json
from sqlalchemy import select, delete, inspect, or_, func
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from app.core.model_config import ModelError
from app.retrieval.filters import exact_value
from app.storage.models import DBIndexSettings, DBIndexDocument, DBSearchIndex, DBActiveSearchIndex, DBChunk, DBDocument

BASE_CORPUS = "tenant-chunks-v1"


def corpus_filter(corpus: str = BASE_CORPUS) -> ColumnElement[bool]:
    return or_(DBChunk.corpus_id.is_(None), DBChunk.corpus_id == BASE_CORPUS) if corpus == BASE_CORPUS else DBChunk.corpus_id == corpus


def available(db: Session) -> bool:
    connection = db.connection()
    transaction = db.get_transaction()
    if db.info.get("index_settings_schema_verified") is transaction:
        return True
    schema = inspect(connection)
    present = (schema.has_table("index_settings") and schema.has_table("index_documents")
            and "corpus_id" in {c["name"] for c in schema.get_columns("chunks")}
            and {"current_index_id", "owner_index_id", "base_revision", "settings_origin"}
                <= {c["name"] for c in schema.get_columns("index_settings")})
    if present:
        db.info["index_settings_schema_verified"] = transaction
    return present


def logical_index(db: Session, index: DBSearchIndex) -> DBSearchIndex:
    spec = metadata(db, index)
    if spec is None or spec.owner_index_id is None:
        return index
    owner = db.get(DBSearchIndex, spec.owner_index_id)
    if owner is None or owner.tenant_id != index.tenant_id or owner.profile_id != index.profile_id:
        raise ModelError("search_index_unavailable", "Neplatná verze indexu.", 409)
    return owner


def current_index(db: Session, index: DBSearchIndex) -> DBSearchIndex:
    spec = metadata(db, index)
    if spec is None or spec.current_index_id is None:
        return index
    current = db.get(DBSearchIndex, spec.current_index_id)
    child = metadata(db, current) if current is not None else None
    if (current is None or current.tenant_id != index.tenant_id or current.profile_id != index.profile_id
            or child is None or child.owner_index_id != index.index_id):
        raise ModelError("search_index_unavailable", "Neplatná aktuální verze indexu.", 409)
    return current


def publish_version(db: Session, index: DBSearchIndex) -> None:
    """Switch a logical index only after a fenced worker completed the new corpus."""
    child = metadata(db, index)
    if child is None or child.owner_index_id is None:
        return
    root = logical_index(db, index)
    spec = db.scalar(select(DBIndexSettings).where(DBIndexSettings.index_id == root.index_id)
        .with_hint(DBIndexSettings, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
        .execution_options(populate_existing=True))
    if spec.current_index_id == index.index_id:
        return
    if spec.revision != child.base_revision:
        raise ModelError("index_settings_conflict", "Index se mezitím změnil; obnovte editor.", 409)
    if not corpus_ready(db, index):
        raise ModelError("search_index_incomplete", "Nová verze indexu není úplná.", 409)
    spec.current_index_id = index.index_id
    spec.name = child.name
    spec.revision += 1


def default_query_corpus(db: Session, tenant: str) -> str:
    from app.storage.vector_store import tenant_key
    active = db.get(DBActiveSearchIndex, tenant_key(tenant))
    root = db.get(DBSearchIndex, active.index_id) if active and active.tenant_id == tenant else None
    if root is None or root.tenant_id != tenant:
        return BASE_CORPUS
    head = current_index(db, root)
    if not corpus_ready(db, head):
        raise ModelError("search_index_incomplete", "Výchozí index vyžaduje doplnění dokumentů.", 409)
    return head.corpus_id


def initialize_legacy(db: Session, tenant: str, snapshot: dict) -> int:
    """Explicit user-approved assumption, insert/update only still-unknown snapshots."""
    from sqlalchemy import update
    count = 0
    indexes = db.scalars(select(DBSearchIndex).where(exact_value(DBSearchIndex.tenant_id, tenant, db.bind.dialect.name))).all()
    for index in indexes:
        spec = metadata(db, index)
        if spec is None:
            from app.storage.vector_store import index_profile
            db.add(DBIndexSettings(index_id=index.index_id, tenant_id=tenant,
                name=f"{index_profile(db, index).model_id[:103]} · {str(index.index_id)[:8]}",
                chunking=snapshot, settings_origin="assumed"))
            count += 1
        elif spec.chunking is None:
            result = db.execute(update(DBIndexSettings).where(DBIndexSettings.index_id == index.index_id,
                DBIndexSettings.revision == spec.revision).values(chunking=snapshot, settings_origin="assumed", revision=spec.revision+1)
                .execution_options(synchronize_session=False))
            count += result.rowcount
    db.commit()
    return count


def metadata(db: Session, index: DBSearchIndex) -> DBIndexSettings | None:
    row = db.get(DBIndexSettings, index.index_id) if available(db) else None
    if row is not None and row.tenant_id != index.tenant_id:
        raise ModelError("search_index_unavailable", "Index není dostupný.", 404)
    return row


def source_revision(doc: DBDocument) -> str:
    value = [str(doc.document_id), doc.source_uri, doc.checksum, doc.updated_at.isoformat() if doc.updated_at else None]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def compatible_source_acls(db: Session, docs: list[DBDocument]) -> set:
    """A new segmentation cannot infer how partial chunk grants map to raw text."""
    from app.storage.acl import acl_groups
    expected = {doc.document_id: acl_groups(doc.security_acl) for doc in docs}
    valid = set(expected)
    if not expected:
        return valid
    tenant = docs[0].tenant_id
    ids = list(expected)
    for offset in range(0, len(ids), 500):
        rows = db.execute(select(DBChunk.document_id, DBChunk.security_acl).where(
            DBChunk.document_id.in_(ids[offset:offset+500]),
            exact_value(DBChunk.tenant_id, tenant, db.bind.dialect.name), corpus_filter())).all()
        for ident, acl in rows:
            if acl_groups(acl) != expected[ident]:
                valid.discard(ident)
    return valid


def corpus_ready(db: Session, index: DBSearchIndex) -> bool:
    if index.corpus_id == BASE_CORPUS:
        return True
    if index.corpus_id != "index-" + index.index_id.hex or not available(db):
        return False
    spec = metadata(db, index)
    if spec is None or not spec.chunking:
        return False
    rows = {ident: (rev, count) for ident, rev, count in db.execute(select(
        DBIndexDocument.document_id, DBIndexDocument.source_revision, DBIndexDocument.chunk_count)
        .where(DBIndexDocument.index_id == index.index_id)).all()}
    counts = dict(db.execute(select(DBChunk.document_id, func.count()).where(
        exact_value(DBChunk.tenant_id, index.tenant_id, db.bind.dialect.name),
        corpus_filter(index.corpus_id)).group_by(DBChunk.document_id)).all())
    docs = db.scalars(select(DBDocument).where(exact_value(DBDocument.tenant_id, index.tenant_id, db.bind.dialect.name))).all()
    return (bool(docs) and len(docs) == len(rows)
            and len(compatible_source_acls(db, docs)) == len(docs)
            and all(rows.get(doc.document_id) == (source_revision(doc), counts.get(doc.document_id, 0)) for doc in docs))


def rename(db: Session, index: DBSearchIndex, name: str, expected_revision: int) -> None:
    from app.storage.models import DBIndexPreparationJob
    from app.storage.index_jobs import available as jobs_available, public
    from app.storage.vector_store import tenant_key
    if not available(db):
        raise ModelError("index_settings_migration_required", "Správa nastavení indexů vyžaduje migraci.", 503)
    if jobs_available(db):
        job = db.scalar(select(DBIndexPreparationJob).where(DBIndexPreparationJob.tenant_key==tenant_key(index.tenant_id))
            .with_hint(DBIndexPreparationJob,"WITH (UPDLOCK, HOLDLOCK)",dialect_name="mssql"))
        if job is not None and public(db, job)["state"] in {"queued","running","cancelling"}:
            raise ModelError("index_preparation_busy", "Během přepočtu nelze přejmenovat index.", 409)
    row = db.scalar(select(DBIndexSettings).where(DBIndexSettings.index_id == index.index_id)
        .with_hint(DBIndexSettings, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql").execution_options(populate_existing=True))
    actual = row.revision if row else 0
    if row is not None and row.owner_index_id is not None:
        raise ModelError("index_version_internal", "Verze se spravuje přes původní index.", 409)
    if actual != expected_revision:
        raise ModelError("index_settings_conflict", "Název se mezitím změnil; obnovte přehled.", 409)
    if row is None:
        row = DBIndexSettings(index_id=index.index_id, tenant_id=index.tenant_id, name=name, chunking=None)
        db.add(row)
    else:
        row.name = name; row.revision += 1
    db.commit()


def remove(db: Session, index: DBSearchIndex, expected_revision: int) -> None:
    from app.storage.models import DBIndexPreparationJob
    from app.storage.index_jobs import public
    from app.storage.vector_store import tenant_key, vector_table, index_profile
    if not available(db):
        raise ModelError("index_settings_migration_required", "Správa indexů vyžaduje migraci.", 503)
    # Workers fence on the tenant job before reading/writing a corpus. Use the same lock order.
    job = db.scalar(select(DBIndexPreparationJob).where(DBIndexPreparationJob.tenant_key == tenant_key(index.tenant_id))
        .with_hint(DBIndexPreparationJob, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql"))
    if job is not None and public(db, job)["state"] in {"queued", "running", "cancelling"}:
        raise ModelError("index_preparation_busy", "Nejdříve dokončete nebo zastavte probíhající indexovou úlohu.", 409)
    index = db.scalar(select(DBSearchIndex).where(DBSearchIndex.index_id == index.index_id)
        .with_hint(DBSearchIndex, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql"))
    if index is None:
        raise ModelError("search_index_not_found", "Index již není dostupný.", 404)
    active = db.get(DBActiveSearchIndex, tenant_key(index.tenant_id))
    if active is not None and active.index_id == index.index_id:
        raise ModelError("index_ingestion_default_protected", "Výchozí index nelze smazat.", 409)
    row = metadata(db, index)
    if row is not None and row.owner_index_id is not None:
        raise ModelError("index_version_internal", "Verze se spravuje přes původní index.", 409)
    if (row.revision if row else 0) != expected_revision:
        raise ModelError("index_settings_conflict", "Stav indexu se změnil; obnovte přehled.", 409)
    # Keep source chunks (including old citations); their corpus stays isolated.
    versions = db.scalars(select(DBSearchIndex).join(DBIndexSettings).where(
        DBIndexSettings.owner_index_id == index.index_id,
        exact_value(DBSearchIndex.tenant_id, index.tenant_id, db.bind.dialect.name))).all()
    ids = [index.index_id] + [child.index_id for child in versions]
    for item in versions + [index]:
        vector_table(item, index_profile(db, item)).drop(db.connection())
    if job is not None and job.index_id in ids:
        db.delete(job)
    if available(db):
        db.execute(delete(DBIndexDocument).where(DBIndexDocument.index_id.in_(ids)))
        db.execute(delete(DBIndexSettings).where(DBIndexSettings.index_id.in_(ids)))
    for item in versions + [index]:
        db.delete(item)
    db.commit()
