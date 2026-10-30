"""Document metadata and authorized chunk counts in two bounded SQL reads."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.retrieval.base import QueryContext
from app.retrieval.filters import document_filters, eligibility_filters
from app.storage.models import DBChunk, DBDocument
from app.storage.sql_joins import InnerHashJoin


def authorized_document_rows(db: Session, context: QueryContext) -> list[tuple[DBDocument, int]]:
    dialect = db.bind.dialect.name
    documents = db.scalars(select(DBDocument).where(*document_filters(context, dialect))
                           .order_by(DBDocument.ingested_at.desc())).all()
    if not documents:
        return []
    counts = (select(DBChunk.document_id, func.count(DBChunk.chunk_id))
              .select_from(InnerHashJoin(DBChunk.__table__, DBDocument.__table__,
                                        DBChunk.document_id == DBDocument.document_id))
              .where(*eligibility_filters(context, dialect, metadata=False))
              .group_by(DBChunk.document_id))
    by_document = dict(db.execute(counts).tuples().all())
    return [(document, by_document.get(document.document_id, 0)) for document in documents]
