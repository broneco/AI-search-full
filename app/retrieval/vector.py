from typing import Any, List, Optional
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.retrieval.base import BaseRetriever, RetrievalResult, QueryContext
from app.storage.models import DBChunk, DBDocument


class VectorRetriever(BaseRetriever):
    """Retrieve relevant document chunks using vector similarity (pgvector), lexical FTS, or hybrid RRF fusion."""

    def __init__(self, db_session: Session) -> None:
        """Initialize the retriever with a database session."""
        self.db = db_session

    async def retrieve(
        self,
        context: QueryContext,
        limit: int = 10,
        **kwargs: Any,
    ) -> List[RetrievalResult]:
        """Perform document chunk retrieval based on the chosen strategy.

        Supported strategies in kwargs: 'vector', 'keyword', 'hybrid' (Weighted RRF).
        """
        strategy = kwargs.get("search_strategy", "hybrid").lower()
        query_embedding: Optional[List[float]] = kwargs.get("query_embedding")

        if strategy in ("vector", "hybrid") and not query_embedding:
            raise ValueError(
                f"query_embedding is required for '{strategy}' search strategy."
            )

        # 1. Fetch Candidates from Vector Search if selected
        vector_results = []
        if strategy in ("vector", "hybrid") and query_embedding:
            vector_results = self._get_vector_candidates(query_embedding, limit=max(limit * 3, 50))

        # 2. Fetch Candidates from Keyword (FTS) Search if selected
        keyword_results = []
        if strategy in ("keyword", "hybrid"):
            keyword_results = self._get_fts_candidates(context.query, limit=max(limit * 3, 50))

        # 3. Apply ACL and Metadata Filters to each candidate set
        filtered_vector = self._apply_filters(vector_results, context, query_embedding)
        filtered_keyword = self._apply_filters(keyword_results, context, query_embedding)

        # 4. Return results based on selected strategy
        if strategy == "vector":
            return filtered_vector[:limit]
        elif strategy == "keyword":
            return filtered_keyword[:limit]
        else:
            # Execute Weighted Reciprocal Rank Fusion (RRF)
            return self._fuse_rrf(filtered_vector, filtered_keyword, limit)

    def _get_vector_candidates(self, query_embedding: List[float], limit: int) -> List[Any]:
        """Execute pgvector select query to retrieve closest semantic chunks."""
        stmt = (
            select(DBChunk, DBDocument)
            .join(DBDocument, DBChunk.document_id == DBDocument.document_id)
            .order_by(DBChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        return self.db.execute(stmt).all()

    def _get_fts_config(self) -> str:
        """Check if Czech language configuration exists in database catalogs safely."""
        try:
            # Query pg_ts_config safely to avoid SQL syntax exceptions
            stmt = text("SELECT EXISTS(SELECT 1 FROM pg_ts_config WHERE cfgname = 'cs');")
            exists = self.db.scalar(stmt)
            return "cs" if exists else "simple"
        except Exception:
            return "simple"

    def _get_fts_candidates(self, query_text: str, limit: int) -> List[Any]:
        """Execute PostgreSQL Full-Text Search query with Czech/simple configurations proactively."""
        # Clean punctuation and split into individual search keywords
        clean_text = query_text
        for char in "?.,!;:()[]{}":
            clean_text = clean_text.replace(char, " ")

        words = [w.strip() for w in clean_text.split() if w.strip()]
        if not words:
            return []

        # Formulate a high-recall OR FTS query (e.g. 'word1 | word2 | word3')
        # This returns chunks containing ANY of the search terms, ranked by density
        fts_query = " | ".join(words)

        cfg = self._get_fts_config()
        stmt = (
            select(DBChunk, DBDocument)
            .join(DBDocument, DBChunk.document_id == DBDocument.document_id)
            .where(
                text(f"to_tsvector('{cfg}', chunks.content) @@ to_tsquery('{cfg}', :q)")
            )
            .order_by(
                text(f"ts_rank_cd(to_tsvector('{cfg}', chunks.content), to_tsquery('{cfg}', :q)) DESC")
            )
            .limit(limit)
        )
        return self.db.execute(stmt, {"q": fts_query}).all()

    def _apply_filters(
        self,
        raw_db_results: List[Any],
        context: QueryContext,
        query_embedding: Optional[List[float]],
    ) -> List[RetrievalResult]:
        """Apply security ACL checks and metadata filters, returning populated RetrievalResults."""
        filtered_results = []
        for chunk, doc in raw_db_results:
            # Apply document-level ACL filtering
            if doc.security_acl:
                allowed_groups = doc.security_acl.get("allowed_groups", [])
                if allowed_groups and not any(
                    g in context.acl_groups for g in allowed_groups
                ):
                    continue

            # Apply chunk-level ACL filtering
            if chunk.security_acl:
                chunk_allowed_groups = chunk.security_acl.get("allowed_groups", [])
                if chunk_allowed_groups and not any(
                    g in context.acl_groups for g in chunk_allowed_groups
                ):
                    continue

            # Apply metadata filters
            is_filtered = False
            for k, v in context.filters.items():
                doc_meta = doc.metadata_json or {}
                chunk_meta = chunk.metadata_json or {}
                if doc_meta.get(k) != v and chunk_meta.get(k) != v:
                    is_filtered = True
                    break
            if is_filtered:
                continue

            # Calculate cosine score if vector embedding is supplied
            score = 0.0
            if query_embedding is not None and chunk.embedding is not None:
                # Calculate cosine similarity in Python to avoid expensive sequential database roundtrips
                try:
                    v1 = query_embedding
                    v2 = chunk.embedding
                    dot_product = sum(x * y for x, y in zip(v1, v2))
                    norm1 = sum(x * x for x in v1) ** 0.5
                    norm2 = sum(x * x for x in v2) ** 0.5
                    if norm1 > 0.0 and norm2 > 0.0:
                        score = dot_product / (norm1 * norm2)
                    else:
                        score = 0.0
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Error calculating cosine similarity in Python: {e}. Falling back to 0.0."
                    )
                    score = 0.0

            filtered_results.append(
                RetrievalResult(
                    chunk_id=str(chunk.chunk_id),
                    document_id=str(chunk.document_id),
                    content=chunk.content,
                    score=score,
                    freshness_status=chunk.freshness_status,
                    title=doc.title,
                    section_title=chunk.section_title,
                    page_number=chunk.page_number,
                    metadata={
                        **(doc.metadata_json or {}),
                        **(chunk.metadata_json or {}),
                    },
                )
            )
        return filtered_results

    def _fuse_rrf(
        self,
        vector_results: List[RetrievalResult],
        keyword_results: List[RetrievalResult],
        limit: int,
    ) -> List[RetrievalResult]:
        """Perform Weighted Reciprocal Rank Fusion (Weighted RRF) on candidate sets."""
        w_vector = settings.RRF_WEIGHT_VECTOR
        w_keyword = settings.RRF_WEIGHT_KEYWORD
        k = 60

        rrf_scores = {}
        chunk_map = {}  # chunk_id -> (RetrievalResult, float)

        # 1. Index vector matches
        for rank, item in enumerate(vector_results, start=1):
            cid = item.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + w_vector * (1.0 / (k + rank))
            chunk_map[cid] = (item, item.score)

        # 2. Index keyword FTS matches
        for rank, item in enumerate(keyword_results, start=1):
            cid = item.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + w_keyword * (1.0 / (k + rank))
            if cid not in chunk_map:
                chunk_map[cid] = (item, 0.0)  # default vector score to 0.0 if only found in FTS

        # 3. Sort by aggregated RRF score descending
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        final_results = []
        for cid in sorted_ids[:limit]:
            item, original_vector_score = chunk_map[cid]
            # Set combined RRF score and save individual component scores in metadata
            item.score = rrf_scores[cid]
            item.metadata["rrf_score"] = rrf_scores[cid]
            item.metadata["vector_score"] = original_vector_score
            final_results.append(item)

        return final_results
