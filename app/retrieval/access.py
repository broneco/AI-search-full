"""Apply the search access policy to document previews and saved evidence."""
import uuid
import os

from sqlalchemy import and_, select

from app.retrieval.base import QueryContext
from app.retrieval.filters import document_filters, eligibility_filters
from app.storage.models import DBChunk, DBDocument

ACCESS_POLICY = "sql-prefilter-v1"


def safe_data_path(path):
    """HTTP document routes may only read local files from the data directory."""
    root = os.path.realpath("data")
    try:
        lexical = os.path.abspath(path)
        if os.path.normcase(os.path.commonpath([root, lexical])) != os.path.normcase(root):
            return None
        resolved = os.path.realpath(lexical)
        return resolved if os.path.normcase(os.path.commonpath([root, resolved])) == os.path.normcase(root) else None
    except (ValueError, OSError):
        return None


def access_context(principal):
    return QueryContext(query="", tenant_id=principal.tenant_id,
                        user_id=str(principal.user_id), acl_groups=list(principal.groups))


def visible_document(db, document_id, principal, *, full_document=False):
    context = access_context(principal)
    doc = db.scalar(select(DBDocument).where(
        DBDocument.document_id == document_id,
        *document_filters(context, db.bind.dialect.name),
    ))
    if doc is None:
        return None
    if full_document:
        # Raw PDF/re-chunk preview contains every chunk, so partial chunk access
        # is insufficient. Do not hand hidden chunks to extraction or an LLM.
        forbidden = db.scalar(select(DBChunk.chunk_id).join(DBDocument).where(
            DBChunk.document_id == document_id,
            ~and_(*eligibility_filters(context, db.bind.dialect.name, metadata=False)),
        ).limit(1))
        if forbidden is not None:
            return None
    return doc


def history_references(message):
    if message.role != "assistant":
        return set()
    evidence = message.sources
    if not isinstance(evidence, dict) or evidence.get("access_policy") != ACCESS_POLICY:
        return None
    try:
        return {(uuid.UUID(ref["chunk_id"]), uuid.UUID(ref["document_id"]))
                for ref in evidence["access_refs"]}
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def authorized_history(db, messages, principal):
    """Validate a batch once, including transitive evidence from prior turns."""
    references = [(message, history_references(message)) for message in messages]
    expected = set().union(*(refs for _, refs in references if refs is not None))
    context = access_context(principal)
    visible = set()
    ids = list({key[0] for key in expected})
    for start in range(0, len(ids), 500):
        visible.update(db.execute(select(DBChunk.chunk_id, DBChunk.document_id).join(DBDocument).where(
            DBChunk.chunk_id.in_(ids[start:start + 500]),
            *eligibility_filters(context, db.bind.dialect.name, metadata=False),
        )).all())
    return [message for message, refs in references if refs is not None and refs <= visible]


def history_is_visible(db, message, principal):
    return bool(authorized_history(db, [message], principal))


def saved_citations(message):
    if isinstance(message.sources, dict):
        return message.sources.get("citations", [])
    return []
