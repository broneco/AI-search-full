from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class RetrievalResult(BaseModel):
    """Represents a single chunk retrieved from the storage/search layer."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    freshness_status: str
    title: str
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = {}


class QueryContext(BaseModel):
    """Contains query parameters, metadata filters, and security controls (ACL)."""

    query: str
    user_id: Optional[str] = None
    filters: Dict[str, Any] = {}
    acl_groups: List[str] = []


class BaseRetriever(ABC):
    """Abstract base class for search and retrieval logic.

    Acts as the entry point for retrieval pipelines. Concrete implementations
    should handle query enrichment, vector/keyword search, metadata filtering,
    ACL checking, and rank fusion.
    """

    @abstractmethod
    async def retrieve(
        self,
        context: QueryContext,
        limit: int = 10,
        **kwargs: Any,
    ) -> List[RetrievalResult]:
        """Perform hybrid or vector retrieval based on user query and context filters.

        Args:
            context: Query parameters including filters and security groups.
            limit: Maximum number of retrieval results to return.
            **kwargs: Extra operational arguments for fusion or ranking tuning.

        Returns:
            A list of RetrievalResult items matching user ACL constraints.
        """
        pass
