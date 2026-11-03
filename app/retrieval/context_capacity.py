"""Read one authorized indexed chunk and expose lengths only; never calls a model."""
from functools import lru_cache
import uuid
import tiktoken
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from app.api.identity import Principal
from app.core.model_config import ModelError
from app.core.local_model_registry import model_catalog
from app.core.model_selection import check_access
from app.core.model_limits import LOCAL_RESERVE
from app.core.search_index_selection import selected_index
from app.retrieval.access import access_context
from app.retrieval.filters import eligibility_filters
from app.storage.models import DBChunk, DBDocument
from app.storage.vector_store import vector_table, index_profile


@lru_cache(maxsize=1)
def reference_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("o200k_base")


def capacity_sample(db: Session, principal: Principal, index_id: uuid.UUID, model_id: str) -> dict:
    index = selected_index(db, principal.tenant_id, index_id)
    profile = next((p for p in model_catalog(db, principal.tenant_id).profiles
                    if p.id == model_id and "chat" in p.purposes), None)
    if profile is None:
        raise ModelError("model_unknown", "Vybraný model není dostupný pro odpovědi.", 422)
    check_access(db, principal, profile)
    vectors = vector_table(index, index_profile(db, index))
    context = access_context(principal).model_copy(update={"corpus_id": index.corpus_id})
    row = db.execute(select(DBChunk.chunk_id, DBChunk.content).join(DBDocument)
        .join(vectors, and_(vectors.c.chunk_id == DBChunk.chunk_id, vectors.c.input_revision == DBChunk.content_hash))
        .where(*eligibility_filters(context, db.bind.dialect.name, metadata=False))
        .order_by(DBChunk.chunk_id).limit(1)).first()
    sample = None
    if row is not None:
        try:
            count = len(reference_encoding().encode(row.content, disallowed_special=()))
        except Exception:
            raise ModelError("context_tokenizer_unavailable", "Počítání tokenů není dostupné. Obnovte odhad později.", 503) from None
        sample = dict(chunk_id=str(row.chunk_id), tokens=count, characters=len(row.content), utf8_bytes=len(row.content.encode("utf-8")))
    return dict(index_id=str(index_id), current_index_id=str(index.index_id), sample=sample,
        tokenizer="o200k_base", tokenization="reference",
        model=dict(id=profile.id, name=profile.name, context_tokens=profile.context_tokens,
            max_output_tokens=profile.max_output_tokens, max_input_chars=profile.max_input_chars,
            reserved_tokens=LOCAL_RESERVE if profile.context_tokens else 0,
            input_guard_bytes=max(0, profile.context_tokens-profile.max_output_tokens-LOCAL_RESERVE)
                if profile.context_tokens else None))
