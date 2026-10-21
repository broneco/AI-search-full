from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
import uuid


class ChatSource(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    content: str
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    freshness_status: str
    score: float
    allowed_groups: List[str] = []
    context_chunk_ids: List[str] = Field(default_factory=list)


class ChatMetadata(BaseModel):
    mode: str
    retrieval_strategy: str
    model_profile: str
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    model_location: Optional[str] = None
    generation_diagnostics: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[int] = None
    search_diagnostics: Dict[str, Any] = Field(default_factory=dict)
    embedding_profile_id: Optional[str] = None
    embedding_model: Optional[str] = None
    search_index_id: Optional[str] = None


class ChatRequest(BaseModel):
    query: str = Field(..., description="Conversational query or search question.")
    model_id: Optional[str] = Field(None, max_length=100)
    search_index_id: Optional[uuid.UUID] = None
    mode: Literal["flash", "thinking"] = Field("flash", description="Legacy query mode.")
    locale: str = Field("cs", description="Application locale and LLM response language ('cs' or 'en').")
    filters: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata filters to apply."
    )
    include_sources: bool = Field(
        default=True, description="Include citations in output response."
    )
    search_strategy: str = Field(
        default="hybrid", description="Retrieval search strategy: 'vector', 'keyword', or 'hybrid'."
    )
    freshness_filter: str = Field(
        default="all", description="Freshness filter constraint: 'all', 'this_year', or 'latest'."
    )
    thread_id: Optional[str] = Field(
        default=None, description="Optional thread UUID to continue multi-turn chat history."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Jaká pravidla musím dodržet co se týče péče o má laboratorní zvířata?",
                "mode": "flash",
                "filters": {},
                "include_sources": True,
                "search_strategy": "hybrid",
                "freshness_filter": "all"
            }
        }
    }


class ChatResponse(BaseModel):
    answer: str = Field(..., description="LLM-generated grounded answer.")
    sources: List[ChatSource] = Field(
        default_factory=list, description="Citations used in answer compilation."
    )
    metadata: ChatMetadata
    thread_id: Optional[str] = Field(None, description="Active thread ID for this conversation.")
