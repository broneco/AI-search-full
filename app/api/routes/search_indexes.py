"""Administrative index preparation and selection metadata; no global activation."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.identity import Principal, require_manager, get_principal
from app.core.model_config import ModelError
from app.ingestion.admin_indexes import list_indexes, prepare_index, available_query_indexes
from app.storage.vector_store import SearchIndexError

router = APIRouter()


class IndexJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    embedding_profile: str = Field(min_length=1, max_length=100)
    action: Literal["create", "backfill"]
    index_id: uuid.UUID | None = None


@router.post("/jobs", status_code=202)
def create_job(request: IndexJobRequest, db: Session = Depends(get_db_session),
               principal: Principal = Depends(require_manager)):
    from app.ingestion.index_jobs import submit
    try:
        return {"job": submit(db, principal, request.embedding_profile, request.action, request.index_id)}
    except DBAPIError:
        db.rollback()
        raise ModelError("index_job_unavailable", "Správa úloh není dostupná. Ověřte migraci.", 503) from None


@router.get("/jobs/current")
def get_job(db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.storage.index_jobs import require_schema, current, public
    try:
        require_schema(db)
        return {"job": public(db, current(db, principal.tenant_id))}
    except DBAPIError:
        raise ModelError("index_job_unavailable", "Stav úlohy není dostupný.", 503) from None


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: uuid.UUID, db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.storage.index_jobs import require_schema, cancel
    try:
        require_schema(db)
        return {"job": cancel(db, principal.tenant_id, job_id)}
    except DBAPIError:
        db.rollback()
        raise ModelError("index_job_unavailable", "Úlohu se nepodařilo zastavit. Obnovte její stav.", 503) from None


@router.get("/jobs/{job_id}/files")
def job_files(job_id: uuid.UUID, db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    """Current per-document coverage, without reading vector contents or document text."""
    from sqlalchemy import select, func, and_
    from app.storage.index_jobs import require_schema, current, public
    from app.storage.models import DBDocument, DBChunk, DBSearchIndex
    from app.storage.vector_store import index_profile, vector_table
    from app.storage.sql_joins import InnerHashJoin
    from app.retrieval.filters import exact_value
    try:
        require_schema(db)
        job = current(db, principal.tenant_id)
        if job is None or job.job_id != job_id:
            raise ModelError("index_job_not_found", "Úloha byla nahrazena jinou. Obnovte přehled.", 404)
        if job.index_id is None:
            return {"files": []}
        index = db.get(DBSearchIndex, job.index_id)
        if index is None or index.tenant_id != principal.tenant_id:
            raise ModelError("search_index_not_found", "Index není dostupný.", 404)
        vectors = vector_table(index, index_profile(db, index))
        dialect = db.bind.dialect.name
        # Separate grouped counts avoid Azure SQL's slow nested outer-join plan.
        # The hint applies only to this vector/chunk join, never ACL/JSON filters.
        totals = dict(db.execute(select(DBChunk.document_id, func.count())
            .where(exact_value(DBChunk.tenant_id, principal.tenant_id, dialect))
            .group_by(DBChunk.document_id)).all())
        valid_counts = dict(db.execute(select(DBChunk.document_id, func.count())
            .select_from(InnerHashJoin(DBChunk.__table__, vectors, and_(vectors.c.chunk_id == DBChunk.chunk_id,
                vectors.c.input_revision == DBChunk.content_hash)))
            .where(exact_value(DBChunk.tenant_id, principal.tenant_id, dialect))
            .group_by(DBChunk.document_id)).all())
        rows = db.execute(select(DBDocument.document_id, DBDocument.title)
            .where(exact_value(DBDocument.tenant_id, principal.tenant_id, dialect))
            .order_by(DBDocument.title, DBDocument.document_id)).all()
        active = public(db, job)["state"] in {"running", "cancelling"}
        current_ids = (job.activity or {}).get("document_ids", []) if active else []
        return {"files": [{"id": str(ident), "name": title, "total": total or 0, "valid": valid or 0,
            "state": "empty" if not total else "completed" if valid == total else "running" if str(ident) in current_ids else "pending"}
            for ident, title in rows for total, valid in [(totals.get(ident, 0), valid_counts.get(ident, 0))]]}
    except DBAPIError:
        raise ModelError("index_job_unavailable", "Přehled souborů není dostupný.", 503) from None


@router.get("/available")
def available_indexes(db: Session = Depends(get_db_session), principal: Principal = Depends(get_principal)):
    try:
        return available_query_indexes(db, principal)
    except (DBAPIError, SearchIndexError):
        raise ModelError("index_catalog_unavailable", "Katalog indexů není dostupný. Ověřte migraci.") from None


class PrepareIndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    embedding_profile: str = Field(min_length=1, max_length=100)
    index_id: uuid.UUID | None = None


@router.get("")
def get_indexes(db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    try:
        return list_indexes(db, principal.tenant_id)
    except (DBAPIError, SearchIndexError):
        raise ModelError("index_catalog_unavailable", "Katalog indexů není dostupný. Ověřte databázovou migraci.") from None


@router.post("/prepare")
async def prepare(request: PrepareIndexRequest, db: Session = Depends(get_db_session),
                  principal: Principal = Depends(require_manager)):
    try:
        return await prepare_index(db, principal, request.embedding_profile, request.index_id)
    except ModelError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise ModelError("index_preparation_failed", "Příprava indexu selhala. Existující dokumenty zůstávají zachované; index lze doplnit znovu.", 503) from None
