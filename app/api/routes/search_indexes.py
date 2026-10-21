"""Administrative index preparation and selection metadata; no global activation."""
import uuid

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
