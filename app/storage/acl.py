"""Maintain relational ACL grants in the same transaction as their owners."""
import uuid

from sqlalchemy import delete, event, insert, inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.storage.models import DBChunk, DBChunkACL, DBDocument, DBDocumentACL


def acl_groups(acl: dict | None) -> set[str]:
    """Legacy absent/empty ACL is public; malformed grants fail closed."""
    if acl is None or acl == {}:
        return {"User"}
    if not isinstance(acl, dict) or "allowed_groups" not in acl:
        return set()
    groups = acl["allowed_groups"]
    if not isinstance(groups, list) or any(
        not isinstance(group, str) or not group.strip() or len(group) > 255
        for group in groups
    ):
        return set()
    if not groups:
        return {"User"}
    return {"User" if group.strip() == "Public" else group.strip() for group in groups}


@event.listens_for(Session, "before_flush")
def maintain_acl_grants(session, flush_context, instances):
    new_documents = {}
    for owner in list(session.new):
        if isinstance(owner, DBDocument):
            owner.document_id = owner.document_id or uuid.uuid4()
            owner.tenant_id = owner.tenant_id or settings.TENANT_ID
            new_documents[owner.document_id] = owner

    for owner in list(session.new) + list(session.dirty):
        if not isinstance(owner, (DBDocument, DBChunk)) or owner in session.deleted:
            continue
        if isinstance(owner, DBChunk) and owner in session.new:
            owner.chunk_id = owner.chunk_id or uuid.uuid4()
            parent = owner.document or new_documents.get(owner.document_id)
            if parent is None:
                parent = session.get(DBDocument, owner.document_id)
            if parent is None:
                raise ValueError("Chunk must reference an existing document.")
            if owner.tenant_id and owner.tenant_id != parent.tenant_id:
                raise ValueError("Chunk and document tenant must agree.")
            owner.tenant_id = parent.tenant_id
        if owner not in session.new and not inspect(owner).attrs.security_acl.history.has_changes():
            continue
        grant_model = DBDocumentACL if isinstance(owner, DBDocument) else DBChunkACL
        existing = {grant.group_name: grant for grant in owner.acl_grants}
        owner.acl_grants = [
            existing.get(group) or grant_model(group_name=group)
            for group in sorted(acl_groups(owner.security_acl))
        ]


def insert_chunks(session: Session, mappings: list[dict]) -> None:
    """Bulk insert chunks and ACLs atomically, including their parent's tenant."""
    if not mappings:
        return
    parents = dict(session.execute(select(DBDocument.document_id, DBDocument.tenant_id).where(
        DBDocument.document_id.in_({item["document_id"] for item in mappings})
    )).all())
    chunk_rows, grants = [], []
    for mapping in mappings:
        row = dict(mapping)
        tenant = parents.get(row["document_id"])
        if tenant is None or row.get("tenant_id", tenant) != tenant:
            raise ValueError("Chunk and document tenant must agree.")
        row["tenant_id"] = tenant
        row["chunk_id"] = row.get("chunk_id") or uuid.uuid4()
        chunk_rows.append(row)
        grants.extend({"chunk_id": row["chunk_id"], "group_name": group}
                      for group in acl_groups(row.get("security_acl")))
    session.execute(insert(DBChunk), chunk_rows)
    if grants:
        session.execute(insert(DBChunkACL), grants)


def rebuild_acl_grants(session: Session, batch_size: int = 200) -> None:
    """Explicit migration/backfill; caller owns the transaction and schema DDL."""
    session.execute(delete(DBChunkACL))
    session.execute(delete(DBDocumentACL))
    for owner, grant, id_name in (
        (DBDocument, DBDocumentACL, "document_id"),
        (DBChunk, DBChunkACL, "chunk_id"),
    ):
        owner_id = getattr(owner, id_name)
        last_id = None
        while True:
            stmt = select(owner_id, owner.security_acl).order_by(owner_id).limit(batch_size)
            if last_id is not None:
                stmt = stmt.where(owner_id > last_id)
            batch = session.execute(stmt).all()
            if not batch:
                break
            grants = [{id_name: row[0], "group_name": group}
                      for row in batch for group in acl_groups(row[1])]
            if grants:
                session.execute(insert(grant), grants)
            last_id = batch[-1][0]
