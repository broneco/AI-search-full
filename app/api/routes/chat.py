import logging
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.core.search_config import SearchConfigManager, SearchConfigSchema
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


@router.get("/config", response_model=SearchConfigSchema)
async def get_search_config():
    """Read the dynamic search retrieval configuration from Blob Storage or disk."""
    manager = SearchConfigManager()
    config = await manager.load_config()
    return config


@router.post("/config")
async def update_search_config(config_request: SearchConfigSchema):
    """Save the updated search retrieval configuration to Blob Storage and disk."""
    manager = SearchConfigManager()
    await manager.save_config(config_request.model_dump())
    return {"status": "saved", "config": config_request}


@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse, include_in_schema=False)
@router.post("/query", response_model=ChatResponse, include_in_schema=False)
async def chat_interaction(
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db_session),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_user_groups: Optional[str] = Header(None, alias="X-User-Groups"),
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
        user_id = x_user_id or "local_user"
        user_groups_str = x_user_groups or "User"
        acl_groups = [g.strip() for g in user_groups_str.split(",") if g.strip()]

        # Propagate freshness filter (clearing out Swagger UI auto-generated dictionary placeholders)
        filters = {}
        if request.filters:
            for k, v in request.filters.items():
                if k != "additionalProp1" and v != {} and v is not None:
                    filters[k] = v
        filters["freshness_filter"] = request.freshness_filter

        context = QueryContext(
            query=request.query,
            user_id=user_id,
            filters=filters,
            acl_groups=acl_groups,
        )

        # Load dynamic search settings
        config_manager = SearchConfigManager()
        search_config = await config_manager.load_config()

        logger.info(f"Executing hybrid retrieval with strategy: {request.search_strategy}")
        retrieved_items = await retriever.retrieve(
            context,
            limit=search_config.get("final_limit", 5),
            query_embedding=query_embedding,
            search_strategy=request.search_strategy,
            search_config=search_config,
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
            clean_content = item.content.replace("[[MATCH_START]]", "").replace("[[MATCH_END]]", "")
            context_blocks.append(
                f"[Source {idx+1}] - Title: {item.title}\n"
                f"Section: {item.section_title or 'N/A'}\n"
                f"Content: {clean_content}\n"
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
                    allowed_groups=item.metadata.get("allowed_groups", []),
                )
            )

        context_str = "\n---\n".join(context_blocks)
        if request.locale == "cs":
            system_message = (
                "Jste užitečný firemní asistent pro vyhledávání (AI Search Assistant).\n"
                "Vaším úkolem je odpovídat na dotazy uživatelů POUZE s využitím níže poskytnutých firemních dokumentů.\n"
                "Pravidla pro odpověď:\n"
                "- Odpovídejte VÝHRADNĚ v českém jazyce.\n"
                "- Spoléhejte se POUZE na poskytnuté dokumenty. Nevymýšlejte si informace ani neextrapolujte mimo kontext.\n"
                "- Pokud poskytnutý kontext neobsahuje dostatek informací pro úplnou odpověď, uveďte to výslovně.\n"
                "- Citujte své zdroje pomocí čísel v hranatých závorkách, např. [1], [2] odpovídající číslům zdrojů níže.\n\n"
                f"=== ZÍSKANÉ firemní dokumenty ===\n{context_str}\n"
            )
        else:
            system_message = (
                "You are a helpful, enterprise AI Search Assistant.\n"
                "Your task is to answer user queries using ONLY the retrieved corporate documents supplied below.\n"
                "Groundedness constraints:\n"
                "- Answer EXCLUSIVELY in the English language.\n"
                "- Rely ONLY on the provided context evidence. Do not extrapolate.\n"
                "- If the context does not contain enough information to formulate a complete answer, state that explicitly.\n"
                "- Cite your sources using bracketed annotations, e.g. [1], [2] matching source numbers below.\n\n"
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
