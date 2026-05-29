import logging
import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.providers.azure_openai import AzureOpenAIProvider, AzureOpenAIEmbeddingProvider
from app.providers.llm import ChatMessage
from app.retrieval.vector import VectorRetriever
from app.retrieval.base import QueryContext
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource, ChatMetadata

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize providers
llm_provider = AzureOpenAIProvider()
embedding_provider = AzureOpenAIEmbeddingProvider()


@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse)
async def chat_interaction(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db_session),
) -> ChatResponse:
    """End-to-end grounded RAG chat endpoint.

    Uses real Azure OpenAI model deployments to answer queries grounded in PostgreSQL evidence.
    """
    start_time = time.time()

    # 1. Embed query
    try:
        logger.info(f"Generating vector embedding for query: {request.query}")
        query_embedding = await embedding_provider.embed_query(request.query)
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Azure OpenAI Query Embedding generation failed: {str(e)}",
        )

    # 2. Retrieve grounded evidence using VectorRetriever
    try:
        retriever = VectorRetriever(db)
        
        # Extract security headers dynamically (Entra ID Auth Skeleton)
        user_id = http_request.headers.get("X-User-Id", "local_user")
        user_groups_str = http_request.headers.get("X-User-Groups", "User")
        acl_groups = [g.strip() for g in user_groups_str.split(",") if g.strip()]

        # Propagate freshness filter
        filters = dict(request.filters or {})
        filters["freshness_filter"] = request.freshness_filter

        context = QueryContext(
            query=request.query,
            user_id=user_id,
            filters=filters,
            acl_groups=acl_groups,
        )

        logger.info(f"Executing hybrid retrieval with strategy: {request.search_strategy}")
        retrieved_items = await retriever.retrieve(
            context,
            limit=5,
            query_embedding=query_embedding,
            search_strategy=request.search_strategy,
        )
    except Exception as e:
        logger.error(f"Database vector retrieval failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database vector retrieval failed: {str(e)}",
        )

    # 3. Formulate system prompt grounded in retrieved context
    if not retrieved_items:
        # Grounded safety constraint fallback
        answer = "I'm sorry, I could not find any relevant information in corporate knowledge files to answer your question."
        sources = []
    else:
        # Pack evidence context
        context_blocks = []
        sources = []
        for idx, item in enumerate(retrieved_items):
            context_blocks.append(
                f"[Source {idx+1}] - Title: {item.title}\n"
                f"Section: {item.section_title or 'N/A'}\n"
                f"Content: {item.content}\n"
            )
            sources.append(
                ChatSource(
                    document_id=item.document_id,
                    chunk_id=item.chunk_id,
                    title=item.title,
                    content=item.content,
                    section_title=item.section_title,
                    page_number=item.page_number,
                    freshness_status=item.freshness_status,
                    score=item.score,
                )
            )

        context_str = "\n---\n".join(context_blocks)
        system_message = (
            "You are a helpful, enterprise AI Search Assistant.\n"
            "Your task is to answer user queries using ONLY the retrieved corporate documents supplied below.\n"
            "Groundedness constraints:\n"
            "- Rely ONLY on the provided context evidence. Do not extrapolate.\n"
            "- If the context does not contain enough information to formulate a complete answer, state that explicitly.\n"
            "- Cite your sources using bracketed annotations, e.g. [Source 1], [Source 2] matching the numbers.\n\n"
            f"=== RETRIEVED corporate documents ===\n{context_str}\n"
        )

        messages = [
            ChatMessage(role="system", content=system_message),
            ChatMessage(role="user", content=request.query),
        ]

        # 4. Generate grounded LLM response using real Azure OpenAI GPT deployment
        try:
            logger.info("Generating grounded response via Azure OpenAI...")
            answer = await llm_provider.generate(
                messages=messages,
                model_profile=request.mode,
                temperature=0.0,
            )
        except Exception as e:
            logger.error(f"Azure OpenAI generation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Azure OpenAI Completion failed: {str(e)}",
            )

    latency_ms = int((time.time() - start_time) * 1000)

    # Map strategies to backward-compatible, descriptive metadata names
    if request.search_strategy == "vector":
        retrieval_strategy = "vector_pgvector"
    elif request.search_strategy == "keyword":
        retrieval_strategy = "keyword_fts"
    else:
        retrieval_strategy = "hybrid_rrf"

    metadata = ChatMetadata(
        mode=request.mode,
        retrieval_strategy=retrieval_strategy,
        model_profile=request.mode,
        latency_ms=latency_ms,
    )

    return ChatResponse(
        answer=answer,
        sources=sources if request.include_sources else [],
        metadata=metadata,
    )
