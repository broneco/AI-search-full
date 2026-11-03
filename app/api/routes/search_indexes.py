"""Administrative index preparation and selection metadata; no global activation."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.identity import Principal, require_manager, get_principal
from app.core.model_config import ModelError
from app.ingestion.admin_indexes import list_indexes, prepare_index, available_query_indexes
from app.storage.vector_store import SearchIndexError
from app.ingestion.chunk_settings import ChunkingSettings

router = APIRouter()


class IndexJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    embedding_profile: str = Field(min_length=1, max_length=100)
    action: Literal["create", "backfill"]
    index_id: uuid.UUID | None = None
    chunking: ChunkingSettings | None = None
    name: str | None = Field(None, min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if value is not None and (not value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError("Name must be nonempty text.")
        return value.strip() if value is not None else None


class IndexRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    expected_revision: int = Field(ge=0)
    _name = field_validator("name")(IndexJobRequest.clean_name.__func__)


class IndexEditorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index_id: uuid.UUID | None = None
    expected_revision: int | None = Field(None, ge=0)
    embedding_profile: str | None = Field(None, max_length=100)
    name: str | None = Field(None, min_length=1, max_length=120)
    chunking: ChunkingSettings
    _name = field_validator("name")(IndexJobRequest.clean_name.__func__)


@router.post("/initialize-settings")
def initialize_settings(db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.ingestion.index_editor import initialize
    try:
        return {"initialized": initialize(db, principal)}
    except DBAPIError:
        db.rollback()
        raise ModelError("index_settings_unavailable", "Nastavení indexů se nepodařilo inicializovat.", 503) from None


@router.post("/editor", status_code=202)
def save_editor(request: IndexEditorRequest, db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.ingestion.index_editor import save
    try:
        return {"job": save(db, principal, chunking=request.chunking.model_dump(), name=request.name,
            profile_name=request.embedding_profile, index_id=request.index_id, expected_revision=request.expected_revision)}
    except DBAPIError:
        db.rollback()
        raise ModelError("index_job_unavailable", "Úpravu indexu se nepodařilo zahájit.", 503) from None


@router.post("/jobs", status_code=202)
def create_job(request: IndexJobRequest, db: Session = Depends(get_db_session),
               principal: Principal = Depends(require_manager)):
    from app.ingestion.index_jobs import submit
    try:
        return {"job": submit(db, principal, request.embedding_profile, request.action, request.index_id,
            chunking=request.chunking.model_dump() if request.chunking else None, name=request.name.strip() if request.name else None)}
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
    from app.storage.index_settings import corpus_filter
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
            .where(exact_value(DBChunk.tenant_id, principal.tenant_id, dialect), corpus_filter(index.corpus_id))
            .group_by(DBChunk.document_id)).all())
        valid_counts = dict(db.execute(select(DBChunk.document_id, func.count())
            .select_from(InnerHashJoin(DBChunk.__table__, vectors, and_(vectors.c.chunk_id == DBChunk.chunk_id,
                vectors.c.input_revision == DBChunk.content_hash)))
            .where(exact_value(DBChunk.tenant_id, principal.tenant_id, dialect), corpus_filter(index.corpus_id))
            .group_by(DBChunk.document_id)).all())
        from app.storage.models import DBIndexDocument
        from app.storage.index_settings import source_revision
        prepared = dict(db.execute(select(DBIndexDocument.document_id, DBIndexDocument.source_revision)
            .where(DBIndexDocument.index_id == index.index_id)).all()) if index.corpus_id != "tenant-chunks-v1" else None
        rows = db.scalars(select(DBDocument)
            .where(exact_value(DBDocument.tenant_id, principal.tenant_id, dialect))
            .order_by(DBDocument.title, DBDocument.document_id)).all()
        active = public(db, job)["state"] in {"running", "cancelling"}
        current_ids = (job.activity or {}).get("document_ids", []) if active else []
        return {"files": [{"id": str(ident), "name": title, "total": total or 0, "valid": valid or 0,
            "state": "running" if str(ident) in current_ids else "pending" if prepared is not None and prepared.get(ident) != source_revision(doc)
                else "empty" if not total else "completed" if valid == total else "pending"}
            for doc in rows for ident, title in [(doc.document_id, doc.title)] for total, valid in [(totals.get(ident, 0), valid_counts.get(ident, 0))]]}
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


@router.get("/{index_id}")
def get_settings(index_id: uuid.UUID, db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.core.search_index_selection import selected_index
    from app.ingestion.admin_indexes import index_description
    from app.core.local_model_registry import embedding_catalog
    from app.storage.models import DBActiveSearchIndex
    from app.storage.vector_store import tenant_key
    index = selected_index(db, principal.tenant_id, index_id, resolve=False)
    return {"index": index_description(db, index, embedding_catalog(db, principal.tenant_id).profiles,
        db.get(DBActiveSearchIndex, tenant_key(principal.tenant_id)))}


@router.get("/{index_id}/context-sample")
def context_sample(index_id: uuid.UUID, model_id: str = Query(..., min_length=1, max_length=100),
                   db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.retrieval.context_capacity import capacity_sample
    try:
        return capacity_sample(db, principal, index_id, model_id)
    except (DBAPIError, SearchIndexError):
        raise ModelError("context_sample_unavailable", "Vzorek indexu není dostupný. Obnovte přehled indexů.", 503) from None


@router.patch("/{index_id}")
def rename_index(index_id: uuid.UUID, request: IndexRenameRequest, db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.core.search_index_selection import selected_index
    from app.storage.index_settings import rename
    try:
        rename(db, selected_index(db, principal.tenant_id, index_id, resolve=False), request.name, request.expected_revision)
        return {"status": "renamed"}
    except DBAPIError:
        db.rollback()
        raise ModelError("index_settings_unavailable", "Název nebyl uložen; obnovte přehled.", 503) from None


@router.delete("/{index_id}")
def delete_index(index_id: uuid.UUID, expected_revision: int = Query(..., ge=0), db: Session = Depends(get_db_session), principal: Principal = Depends(require_manager)):
    from app.core.search_index_selection import selected_index
    from app.storage.index_settings import remove
    try:
        remove(db, selected_index(db, principal.tenant_id, index_id, resolve=False), expected_revision)
        return {"status": "deleted", "index_id": str(index_id)}
    except DBAPIError:
        db.rollback()
        raise ModelError("index_delete_unavailable", "Index nebyl smazán; obnovte přehled.", 503) from None
