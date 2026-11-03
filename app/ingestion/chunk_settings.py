"""One validated immutable chunking snapshot for previews and index preparation."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.core.search_config import SemanticChunkingParams, StructureChunkingParams, TokenChunkingParams, AgenticChunkingParams
from typing import Literal
from sqlalchemy.orm import Session
from app.api.identity import Principal
from app.providers.embeddings import EmbeddingProvider
from app.ingestion.chunking import RecursiveCharacterTextSplitter


class ChunkingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    chunk_size: int = Field(1500, ge=200, le=5000)
    chunk_overlap: int = Field(250, ge=0, le=1000)
    chunk_cross_page: bool = False
    overlap_cross_page: bool = False
    chunk_splitter_type: Literal["recursive", "character"] = "recursive"
    chunking_strategy: Literal["standard", "semantic", "structure", "token", "agentic"] = "standard"
    enrich_with_summary: bool = False
    summary_custom_prompt: str = Field("", max_length=30000)
    semantic_params: SemanticChunkingParams = Field(default_factory=SemanticChunkingParams)
    structure_params: StructureChunkingParams = Field(default_factory=StructureChunkingParams)
    token_params: TokenChunkingParams = Field(default_factory=TokenChunkingParams)
    agentic_params: AgenticChunkingParams = Field(default_factory=AgenticChunkingParams)
    summary_model_id: str | None = Field(None, max_length=100)
    classification_model_id: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def overlaps(self):
        if self.chunk_overlap >= self.chunk_size or self.token_params.overlap_tokens >= self.token_params.size_tokens:
            raise ValueError("Překryv musí být menší než velikost chunku.")
        return self


def splitter_for(db: Session, principal: Principal, snapshot: dict, *,
                 embedding_provider: EmbeddingProvider | None, force_ai: bool) -> RecursiveCharacterTextSplitter:
    from app.core.model_selection import model_provider
    value = ChunkingSettings.model_validate(snapshot).model_dump()
    value.pop("schema_version")
    summary_id = value.pop("summary_model_id")
    classification_id = value.pop("classification_model_id")
    llm = model_provider(db, principal.tenant_id, "classification", classification_id, principal) if force_ai and value["chunking_strategy"] == "agentic" else None
    summary = model_provider(db, principal.tenant_id, "summary", summary_id, principal) if force_ai and value["enrich_with_summary"] else None
    return RecursiveCharacterTextSplitter(**value, embedding_provider=embedding_provider, llm_provider=llm,
        summary_provider=summary, strict_summary=bool(force_ai and value["enrich_with_summary"]), strict_processing=True)
