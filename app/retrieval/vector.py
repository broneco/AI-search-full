import json
import numpy as np
from typing import Any, List, Optional
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.search_config import SearchConfigManager
from app.retrieval.base import BaseRetriever, RetrievalResult, QueryContext
from app.storage.models import DBChunk, DBDocument


class VectorRetriever(BaseRetriever):
    """Retrieve relevant document chunks using vector similarity (pgvector), lexical FTS, or hybrid RRF/Score Addition/Union fusion."""

    def __init__(self, db_session: Session) -> None:
        """Initialize the retriever with a database session."""
        self.db = db_session

    async def retrieve(
        self,
        context: QueryContext,
        limit: int = 10,
        **kwargs: Any,
    ) -> List[RetrievalResult]:
        """Perform document chunk retrieval based on the chosen strategy and dynamic search config."""
        # Load dynamic search settings
        search_config = kwargs.get("search_config")
        if not search_config:
            search_config = SearchConfigManager().load_config_sync()

        # Extract parameters
        strategy = kwargs.get("search_strategy", search_config.get("search_strategy", "hybrid")).lower()
        hybrid_strategy = search_config.get("hybrid_strategy", "rrf").lower()
        vector_weight = search_config.get("vector_weight", 0.6)
        keyword_weight = search_config.get("keyword_weight", 0.4)
        rrf_k = search_config.get("rrf_k", 60)
        vector_limit = search_config.get("vector_limit", 50)
        keyword_limit = search_config.get("keyword_limit", 50)
        
        # Respect explicitly passed query limit, otherwise fallback to configured final_limit
        final_limit = limit if limit != 10 else search_config.get("final_limit", 8)
        vector_final_limit = search_config.get("vector_final_limit", 5)
        keyword_final_limit = search_config.get("keyword_final_limit", 5)
        score_threshold = search_config.get("score_threshold", 0.0)
        freshness_boost = search_config.get("freshness_boost", 0.0)
        context_expansion = search_config.get("context_expansion", "none").lower()
        context_expansion_size = search_config.get("context_expansion_size", 1)

        query_embedding: Optional[List[float]] = kwargs.get("query_embedding")

        if strategy in ("vector", "hybrid") and not query_embedding:
            raise ValueError(
                f"query_embedding is required for '{strategy}' search strategy."
            )

        # 1. Fetch Candidates from Vector Search if selected (passing context for SQL pre-filtering)
        vector_results = []
        if strategy in ("vector", "hybrid") and query_embedding:
            vector_results = self._get_vector_candidates(query_embedding, limit=vector_limit, context=context)

        # 2. Fetch Candidates from Keyword (FTS) Search if selected (passing context for SQL pre-filtering)
        keyword_results = []
        if strategy in ("keyword", "hybrid"):
            keyword_results = self._get_fts_candidates(context.query, limit=keyword_limit, context=context)

        # 3. Apply ACL, Freshness, Metadata filters (secondary validation) and calculate scores
        filtered_vector = self._apply_filters(vector_results, context, query_embedding, freshness_boost)
        filtered_keyword = self._apply_filters(keyword_results, context, query_embedding, freshness_boost)

        # 4. Return results based on selected strategy
        final_results = []
        if strategy == "vector":
            final_results = filtered_vector[:final_limit]
            # Apply score threshold filter for vector only
            if score_threshold > 0.0:
                final_results = [r for r in final_results if r.score >= score_threshold]
        elif strategy == "keyword":
            final_results = filtered_keyword[:final_limit]
        else:
            # Execute Hybrid Fusion
            if hybrid_strategy == "rrf":
                final_results = self._fuse_rrf(filtered_vector, filtered_keyword, rrf_k, vector_weight, keyword_weight, final_limit)
            elif hybrid_strategy == "score_addition":
                final_results = self._fuse_score_addition(filtered_vector, filtered_keyword, vector_weight, keyword_weight, final_limit)
                # Apply score threshold filter for score addition
                if score_threshold > 0.0:
                    final_results = [r for r in final_results if r.score >= score_threshold]
            elif hybrid_strategy == "union":
                final_results = self._fuse_union(filtered_vector, filtered_keyword, vector_final_limit, keyword_final_limit)

        # 5. Apply Context Expansion if enabled (passing context_max_tokens limit)
        if context_expansion != "none":
            context_max_tokens = search_config.get("context_max_tokens", 4000)
            final_results = self._expand_context(
                final_results, 
                context_expansion, 
                context_expansion_size,
                max_tokens=context_max_tokens
            )

        return final_results

    def _build_sql_filters(self, context: QueryContext) -> List[Any]:
        """Build SQLAlchemy expression filters for ACL, freshness, and tenant isolation."""
        tenant_base = settings.TENANT_ID.split("-")[0]
        filters = [DBDocument.tenant_id.in_([settings.TENANT_ID, tenant_base])]
        
        # 1. ACL pre-filtering
        if "Management" not in context.acl_groups:
            if not settings.USE_AZURE_SQL and self.db.bind.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import ARRAY
                from sqlalchemy import String, cast
                user_groups_list = list(context.acl_groups) + ["User"]
                user_groups_array = cast(user_groups_list, ARRAY(String))
                
                # Require both document and chunk to allow access
                filters.append(DBDocument.security_acl.isnot(None))
                filters.append(DBDocument.security_acl.has_key('allowed_groups'))
                filters.append(DBDocument.security_acl['allowed_groups'].op('?|')(user_groups_array))
                
                filters.append(DBChunk.security_acl.isnot(None))
                filters.append(DBChunk.security_acl.has_key('allowed_groups'))
                filters.append(DBChunk.security_acl['allowed_groups'].op('?|')(user_groups_array))

        # 2. Freshness pre-filtering
        freshness = context.filters.get("freshness_filter", "all")
        if freshness == "this_year":
            from sqlalchemy import extract
            filters.append(extract('year', DBDocument.created_at) == 2026)
        elif freshness == "latest":
            filters.append(DBDocument.freshness_status == "current")
            
        return filters

    def _get_vector_candidates(self, query_embedding: List[float], limit: int, context: QueryContext) -> List[Any]:
        """Execute vector select query to retrieve closest semantic chunks."""
        filters = self._build_sql_filters(context)

        if settings.USE_AZURE_SQL or self.db.bind.dialect.name != "postgresql":
            # For Azure SQL / non-pgvector databases:
            # 1. Pre-fetch candidate chunk IDs and JSON embeddings with candidate limit
            candidate_limit = max(limit * 20, 300)
            stmt = (
                select(DBChunk.chunk_id, DBChunk.document_id, DBChunk.embedding)
                .join(DBDocument, DBChunk.document_id == DBDocument.document_id)
            )
            if filters:
                stmt = stmt.where(*filters)
            stmt = stmt.limit(candidate_limit)

            raw_rows = self.db.execute(stmt).all()
            if not raw_rows:
                return []

            # 2. Extract vectors and compute Cosine similarity via NumPy SIMD matrix operations
            query_vec = np.asarray(query_embedding, dtype=np.float32)
            query_norm = np.linalg.norm(query_vec)
            if query_norm > 0:
                query_vec = query_vec / query_norm

            valid_items = []
            embs = []
            for r in raw_rows:
                cid, doc_id, emb_data = r[0], r[1], r[2]
                if isinstance(emb_data, str):
                    try:
                        emb_data = json.loads(emb_data)
                    except Exception:
                        emb_data = None
                if emb_data and isinstance(emb_data, list) and len(emb_data) == len(query_embedding):
                    valid_items.append((cid, doc_id))
                    embs.append(emb_data)

            if not valid_items:
                return []

            mat = np.array(embs, dtype=np.float32)
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            norm_mat = mat / norms

            sims = np.dot(norm_mat, query_vec)
            dists = 1.0 - sims
            top_indices = np.argsort(dists)[:limit]

            top_chunk_ids = [valid_items[idx][0] for idx in top_indices]

            # 3. Fetch full ORM models ONLY for the Top-N winning chunks
            final_stmt = (
                select(DBChunk, DBDocument)
                .join(DBDocument, DBChunk.document_id == DBDocument.document_id)
                .where(DBChunk.chunk_id.in_(top_chunk_ids))
            )
            model_rows = self.db.execute(final_stmt).all()

            # Preserve score order
            model_map = {row[0].chunk_id: row for row in model_rows}
            ordered_results = []
            for cid in top_chunk_ids:
                if cid in model_map:
                    ordered_results.append(model_map[cid])
            return ordered_results
        else:
            stmt = (
                select(DBChunk, DBDocument)
                .join(DBDocument, DBChunk.document_id == DBDocument.document_id)
            )
            if filters:
                stmt = stmt.where(*filters)
            stmt = stmt.order_by(DBChunk.embedding.cosine_distance(query_embedding)).limit(limit)
            return self.db.execute(stmt).all()

    def _get_fts_config(self) -> str:
        """Check if Czech language configuration exists in database catalogs safely."""
        try:
            stmt = text("SELECT EXISTS(SELECT 1 FROM pg_ts_config WHERE cfgname = 'cs');")
            exists = self.db.scalar(stmt)
            return "cs" if exists else "simple"
        except Exception:
            return "simple"

    def _get_fts_candidates(self, query_text: str, limit: int, context: QueryContext) -> List[Any]:
        """Execute Full-Text Search query and select rank value as a column."""
        # Clean punctuation and split into individual search keywords
        clean_text = query_text
        for char in "?.,!;:()[]{}":
            clean_text = clean_text.replace(char, " ")

        words = [w.strip() for w in clean_text.split() if w.strip()]
        if not words:
            return []

        if settings.USE_AZURE_SQL or self.db.bind.dialect.name != "postgresql":
            # Azure SQL / MS SQL keyword search using ILIKE / LIKE matching
            from sqlalchemy import or_
            like_filters = [DBChunk.content.ilike(f"%{w}%") for w in words]
            filters = self._build_sql_filters(context)
            stmt = (
                select(DBChunk, DBDocument)
                .join(DBDocument, DBChunk.document_id == DBDocument.document_id)
                .where(or_(*like_filters))
            )
            if filters:
                stmt = stmt.where(*filters)
            
            rows = self.db.execute(stmt).all()
            scored_rows = []
            for row in rows:
                chunk = row[0]
                doc = row[1]
                content_lower = chunk.content.lower()
                matches = sum(content_lower.count(w.lower()) for w in words)
                scored_rows.append((chunk, doc, float(matches)))
            scored_rows.sort(key=lambda x: x[2], reverse=True)
            return scored_rows[:limit]
        else:
            fts_query = " | ".join(words)
            cfg = self._get_fts_config()
            
            # Select rank explicitly as a column so we can use it in score_addition
            rank_expression = f"ts_rank_cd(to_tsvector('{cfg}', chunks.content), to_tsquery('{cfg}', :q))"
            filters = self._build_sql_filters(context)
            
            stmt = (
                select(
                    DBChunk, 
                    DBDocument, 
                    text(f"{rank_expression} as fts_rank")
                )
                .join(DBDocument, DBChunk.document_id == DBDocument.document_id)
                .where(
                    text(f"to_tsvector('{cfg}', chunks.content) @@ to_tsquery('{cfg}', :q)")
                )
            )
            if filters:
                stmt = stmt.where(*filters)
                
            stmt = stmt.order_by(
                text(f"{rank_expression} DESC")
            ).limit(limit)
            return self.db.execute(stmt, {"q": fts_query}).all()

    def _apply_filters(
        self,
        raw_db_results: List[Any],
        context: QueryContext,
        query_embedding: Optional[List[float]],
        freshness_boost: float = 0.0,
    ) -> List[RetrievalResult]:
        """Apply security ACL checks, freshness constraints, metadata filters and optional freshness boosts."""
        filtered_results = []
        for row in raw_db_results:
            chunk = row[0]
            doc = row[1]
            fts_rank = row[2] if len(row) > 2 else 0.0

            # 1. Apply document-level ACL filtering
            if doc.security_acl:
                allowed_groups = doc.security_acl.get("allowed_groups", [])
                if "Management" not in context.acl_groups:
                    if "User" not in allowed_groups:
                        if allowed_groups and not any(
                            g in context.acl_groups for g in allowed_groups
                        ):
                            continue

            # 2. Apply chunk-level ACL filtering
            if chunk.security_acl:
                chunk_allowed_groups = chunk.security_acl.get("allowed_groups", [])
                if "Management" not in context.acl_groups:
                    if "User" not in chunk_allowed_groups:
                        if chunk_allowed_groups and not any(
                            g in context.acl_groups for g in chunk_allowed_groups
                        ):
                            continue

            # 3. Apply freshness filtering constraints
            freshness_filter = context.filters.get("freshness_filter", "all")
            if freshness_filter == "this_year":
                if doc.created_at.year != 2026:
                    continue
            elif freshness_filter == "latest":
                if doc.freshness_status != "current":
                    continue

            # 4. Apply standard metadata filters (ignoring search configuration parameters)
            is_filtered = False
            search_config_keys = {
                "freshness_filter", "search_strategy", "hybrid_strategy", "vector_weight", "keyword_weight",
                "rrf_k", "vector_limit", "keyword_limit", "final_limit", "vector_final_limit", 
                "keyword_final_limit", "score_threshold", "freshness_boost", "context_expansion", 
                "context_expansion_size", "chunk_size", "chunk_overlap", "context_max_tokens"
            }
            for k, v in context.filters.items():
                if k in search_config_keys:
                    continue
                
                doc_attr = getattr(doc, k, None)
                chunk_attr = getattr(chunk, k, None)
                doc_meta = doc.metadata_json or {}
                chunk_meta = chunk.metadata_json or {}
                
                matches = False
                if doc_attr == v or chunk_attr == v:
                    matches = True
                elif doc_meta.get(k) == v or chunk_meta.get(k) == v:
                    matches = True
                    
                if not matches:
                    is_filtered = True
                    break
            if is_filtered:
                continue

            # Calculate cosine score if vector embedding is supplied
            score = 0.0
            if query_embedding is not None and chunk.embedding is not None:
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

            # 5. Apply freshness boost if document is released in current year (2026)
            if freshness_boost > 0.0 and doc.created_at.year == 2026:
                score += freshness_boost

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
                        "chunk_index": chunk.chunk_index,
                        "fts_rank": fts_rank,
                        "allowed_groups": doc.security_acl.get("allowed_groups", []) if doc.security_acl else [],
                    },
                )
            )
        return filtered_results

    def _fuse_rrf(
        self,
        vector_results: List[RetrievalResult],
        keyword_results: List[RetrievalResult],
        rrf_k: int = 60,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
        limit: int = 5,
    ) -> List[RetrievalResult]:
        """Perform Weighted Reciprocal Rank Fusion (Weighted RRF) on candidate sets."""
        rrf_scores = {}
        chunk_map = {}

        # 1. Index vector matches
        for rank, item in enumerate(vector_results, start=1):
            cid = item.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + vector_weight * (1.0 / (rrf_k + rank))
            chunk_map[cid] = (item, item.score)

        # 2. Index keyword FTS matches
        for rank, item in enumerate(keyword_results, start=1):
            cid = item.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + keyword_weight * (1.0 / (rrf_k + rank))
            if cid not in chunk_map:
                chunk_map[cid] = (item, 0.0)

        # 3. Sort by aggregated RRF score descending with chunk text deduplication
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        final_results = []
        seen_texts = set()
        for cid in sorted_ids:
            item, original_vector_score = chunk_map[cid]
            # Deduplicate near-identical chunk text to maximize prompt diversity
            normalized_text = " ".join(item.content.strip().split())[:120].lower()
            if normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)
            item.score = rrf_scores[cid]
            item.metadata["rrf_score"] = rrf_scores[cid]
            item.metadata["vector_score"] = original_vector_score
            final_results.append(item)
            if len(final_results) >= limit:
                break

        return final_results

    def _fuse_score_addition(
        self,
        vector_results: List[RetrievalResult],
        keyword_results: List[RetrievalResult],
        vector_weight: float,
        keyword_weight: float,
        limit: int,
    ) -> List[RetrievalResult]:
        """Perform Weighted Score Addition on candidate sets by normalizing FTS scores."""
        # Find maximum keyword FTS rank in current keyword candidate set to normalize
        max_fts = 0.0001
        for item in keyword_results:
            rank = item.metadata.get("fts_rank", 0.0)
            if rank > max_fts:
                max_fts = rank
        
        # Prevent low-score inflation by setting a minimum normalization baseline
        max_fts = max(max_fts, 0.1)

        combined_scores = {}
        chunk_map = {}

        # 1. Add vector scores (cosine similarity is bounded between -1 and 1)
        for item in vector_results:
            cid = item.chunk_id
            v_score = max(0.0, item.score)  # avoid negative contributions
            combined_scores[cid] = combined_scores.get(cid, 0.0) + vector_weight * v_score
            chunk_map[cid] = (item, item.score)

        # 2. Add keyword scores (normalized FTS rank)
        for item in keyword_results:
            cid = item.chunk_id
            fts_rank = item.metadata.get("fts_rank", 0.0)
            normalized_fts = fts_rank / max_fts
            combined_scores[cid] = combined_scores.get(cid, 0.0) + keyword_weight * normalized_fts
            if cid not in chunk_map:
                chunk_map[cid] = (item, 0.0)

        # 3. Sort by aggregated combined score descending with chunk text deduplication
        sorted_ids = sorted(combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True)

        final_results = []
        seen_texts = set()
        for cid in sorted_ids:
            item, original_vector_score = chunk_map[cid]
            normalized_text = " ".join(item.content.strip().split())[:120].lower()
            if normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)
            item.score = combined_scores[cid]
            item.metadata["combined_score"] = combined_scores[cid]
            item.metadata["vector_score"] = original_vector_score
            final_results.append(item)
            if len(final_results) >= limit:
                break

        return final_results

    def _fuse_union(
        self,
        vector_results: List[RetrievalResult],
        keyword_results: List[RetrievalResult],
        vector_final_limit: int,
        keyword_final_limit: int,
    ) -> List[RetrievalResult]:
        """Combine top N vector results and top M keyword results, deduplicating by chunk_id and content text."""
        final_results = []
        seen_chunk_ids = set()
        seen_texts = set()

        # Add top N vector results
        for item in vector_results:
            normalized_text = " ".join(item.content.strip().split())[:120].lower()
            if item.chunk_id not in seen_chunk_ids and normalized_text not in seen_texts:
                seen_chunk_ids.add(item.chunk_id)
                seen_texts.add(normalized_text)
                final_results.append(item)
                if len(final_results) >= vector_final_limit:
                    break

        # Add top M keyword results
        for item in keyword_results:
            normalized_text = " ".join(item.content.strip().split())[:120].lower()
            if item.chunk_id not in seen_chunk_ids and normalized_text not in seen_texts:
                seen_chunk_ids.add(item.chunk_id)
                seen_texts.add(normalized_text)
                final_results.append(item)
                if len(final_results) >= (vector_final_limit + keyword_final_limit):
                    break

        return final_results

    def _expand_context(
        self, 
        results: List[RetrievalResult], 
        expansion_type: str, 
        expansion_size: int,
        max_tokens: int = 4000
    ) -> List[RetrievalResult]:
        """Load surrounding sibling, page or section chunks to expand context passed to the LLM."""
        if not results or expansion_type == "none":
            return results

        expanded_results = []
        for item in results:
            doc_id = item.document_id
            chunk_idx = item.metadata.get("chunk_index")
            page_no = item.page_number
            sect_title = item.section_title

            if chunk_idx is None:
                expanded_results.append(item)
                continue

            stmt = None
            if expansion_type == "siblings":
                min_idx = max(0, chunk_idx - expansion_size)
                max_idx = chunk_idx + expansion_size
                stmt = (
                    select(DBChunk.content, DBChunk.chunk_index)
                    .where(DBChunk.document_id == doc_id)
                    .where(DBChunk.chunk_index >= min_idx)
                    .where(DBChunk.chunk_index <= max_idx)
                    .order_by(DBChunk.chunk_index.asc())
                )
            elif expansion_type == "page" and page_no is not None:
                stmt = (
                    select(DBChunk.content, DBChunk.chunk_index)
                    .where(DBChunk.document_id == doc_id)
                    .where(DBChunk.page_number == page_no)
                    .order_by(DBChunk.chunk_index.asc())
                )
            elif expansion_type == "section" and sect_title:
                stmt = (
                    select(DBChunk.content, DBChunk.chunk_index)
                    .where(DBChunk.document_id == doc_id)
                    .where(DBChunk.section_title == sect_title)
                    .order_by(DBChunk.chunk_index.asc())
                )

            if stmt is not None:
                try:
                    rows = self.db.execute(stmt).all()
                    if rows:
                        # 1. Find the index of the matched chunk in the retrieved rows
                        matched_row_idx = -1
                        for i, row in enumerate(rows):
                            if row[1] == chunk_idx:
                                matched_row_idx = i
                                break
                                
                        if matched_row_idx == -1:
                            selected_rows = rows
                        else:
                            # 2. Outward token budget expansion (alternating left and right)
                            # 1 token ≈ 3 characters in Czech
                            char_budget = max_tokens * 3
                            selected_indices = {matched_row_idx}
                            current_char_len = len(rows[matched_row_idx][0])
                            
                            left = matched_row_idx - 1
                            right = matched_row_idx + 1
                            
                            while (left >= 0 or right < len(rows)) and current_char_len < char_budget:
                                if right < len(rows):
                                    next_len = len(rows[right][0])
                                    if current_char_len + next_len <= char_budget:
                                        selected_indices.add(right)
                                        current_char_len += next_len
                                        right += 1
                                    else:
                                        right = len(rows) # stop right expansion
                                if left >= 0:
                                    next_len = len(rows[left][0])
                                    if current_char_len + next_len <= char_budget:
                                        selected_indices.add(left)
                                        current_char_len += next_len
                                        left -= 1
                                    else:
                                        left = -1 # stop left expansion
                                        
                            selected_rows = [rows[i] for i in sorted(selected_indices)]

                        expanded_content = self._merge_chunks_with_highlight(selected_rows, chunk_idx)
                        expanded_item = item.model_copy()
                        expanded_item.content = expanded_content
                        expanded_results.append(expanded_item)
                        continue
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to expand context: {e}")

            expanded_results.append(item)

        return expanded_results

    def _merge_chunks_with_highlight(self, chunks: List[Any], matched_idx: int) -> str:
        """Merge a list of chunks, resolving overlaps, and wrap the matched chunk in highlight tags."""
        if not chunks:
            return ""

        merged_text = ""
        match_start_char = -1
        match_end_char = -1

        for row in chunks:
            content = row[0]
            idx = row[1]
            
            if not merged_text:
                merged_text = content
                if idx == matched_idx:
                    match_start_char = 0
                    match_end_char = len(merged_text)
            else:
                s1_clean = merged_text.rstrip()
                s2_clean = content.lstrip()
                max_overlap = min(len(s1_clean), len(s2_clean), 300)
                
                overlap_len = 0
                for i in range(max_overlap, 0, -1):
                    if s1_clean.endswith(s2_clean[:i]):
                        overlap_len = i
                        break
                
                if overlap_len > 0:
                    new_part = s2_clean[overlap_len:]
                    
                    if idx == matched_idx:
                        match_start_char = len(s1_clean) - overlap_len
                        match_end_char = match_start_char + len(s2_clean)
                        
                    merged_text = s1_clean + new_part
                else:
                    if idx == matched_idx:
                        match_start_char = len(merged_text) + 1
                        match_end_char = match_start_char + len(content)
                        
                    merged_text += "\n" + content

        # If matching chunk was found and indexed, wrap it in tags
        if match_start_char != -1 and match_end_char != -1:
            return (
                merged_text[:match_start_char] + 
                "[[MATCH_START]]" + 
                merged_text[match_start_char:match_end_char] + 
                "[[MATCH_END]]" + 
                merged_text[match_end_char:]
            )
        return merged_text

