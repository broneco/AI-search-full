from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    content: str
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    freshness_status: str
    score: float


class ChatMetadata(BaseModel):
    mode: str
    retrieval_strategy: str
    model_profile: str
    latency_ms: Optional[int] = None


class ChatRequest(BaseModel):
    query: str = Field(..., description="Conversational query or search question.")
    mode: str = Field("flash", description="Agent query mode: 'flash' or 'thinking'.")
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
