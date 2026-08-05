import logging
import time
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.core.config import settings
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
    """End-to-end grounded RAG chat endpoint with multi-turn history awareness."""
    start_time = time.time()

    # 1. Authenticate user & load multi-turn thread history first
    past_messages = []
    active_thread_id = None
    current_db_user = None

    auth_header = http_request.headers.get("Authorization")
    session_header = http_request.headers.get("X-Session-Token")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "").strip()
    elif session_header:
        token = session_header.strip()

    tenant_base = settings.TENANT_ID.split("-")[0]
    valid_tenants = [settings.TENANT_ID, tenant_base]

    if token:
        try:
            from app.api.routes.auth import decode_token
            from app.storage.models import DBUser
            payload = decode_token(token)
            current_db_user = db.query(DBUser).filter(
                DBUser.tenant_id.in_(valid_tenants),
                DBUser.user_id == uuid.UUID(payload["sub"])
            ).first()
        except Exception:
            pass

    if not current_db_user and x_user_id:
        try:
            from app.storage.models import DBUser
            current_db_user = db.query(DBUser).filter(
                DBUser.tenant_id.in_(valid_tenants),
                DBUser.user_id == uuid.UUID(x_user_id)
            ).first()
        except Exception:
            pass

    if not current_db_user and not token and not x_user_id:
        from app.storage.models import DBUser
        current_db_user = db.query(DBUser).filter(DBUser.tenant_id.in_(valid_tenants)).first()

    if not current_db_user:
        raise HTTPException(
            status_code=401,
            detail="Přihlášení vyžadováno. Prosím přihlaste se k účtu.",
        )

    from app.storage.models import DBChatThread, DBChatMessage
    user_question_title = request.query[:50] + ("..." if len(request.query) > 50 else "")

    if request.thread_id:
        try:
            t_uuid = uuid.UUID(request.thread_id)
            thread = db.query(DBChatThread).filter(
                DBChatThread.tenant_id.in_(valid_tenants),
                DBChatThread.thread_id == t_uuid,
                DBChatThread.user_id == current_db_user.user_id
            ).first()
            if thread:
                active_thread_id = str(thread.thread_id)
                past_messages = (
                    db.query(DBChatMessage)
                    .filter(DBChatMessage.thread_id == t_uuid)
                    .order_by(DBChatMessage.created_at.asc())
                    .all()
                )
                # Auto-update thread title if it's default "Nová konverzace" or empty
                if thread.title in ("Nová konverzace", "New Chat", "") or len(past_messages) == 0:
                    thread.title = user_question_title
                    db.commit()
        except Exception:
            pass

    if not active_thread_id:
        # Auto-create a new thread with user's question as title
        new_t = DBChatThread(
            tenant_id=settings.TENANT_ID,
            user_id=current_db_user.user_id,
            title=user_question_title,
        )
        db.add(new_t)
        db.commit()
        db.refresh(new_t)
        active_thread_id = str(new_t.thread_id)

    # 2. Formulate search query for vector retrieval
    retrieval_query = request.query

    # 3. Embed retrieval query
    try:
        logger.info(f"Generating vector embedding for retrieval query: '{retrieval_query}'")
        query_embedding = await embedding_provider.embed_query(retrieval_query)
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Azure OpenAI Query Embedding generation failed: {str(e)}",
        )

    # 4. Retrieve grounded evidence using VectorRetriever
    try:
        retriever = VectorRetriever(db)
        
        user_id = x_user_id or "local_user"
        user_groups_str = x_user_groups or "User"
        acl_groups = [g.strip() for g in user_groups_str.split(",") if g.strip()]

        filters = {}
        if request.filters:
            for k, v in request.filters.items():
                if k != "additionalProp1" and v != {} and v is not None:
                    filters[k] = v
        filters["freshness_filter"] = request.freshness_filter

        context = QueryContext(
            query=retrieval_query,
            user_id=user_id,
            filters=filters,
            acl_groups=acl_groups,
        )

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
        logger.info(f"RETRIEVAL_DEBUG: Retrieved {len(retrieved_items)} items for query: '{request.query}'")
        for i, item in enumerate(retrieved_items):
            logger.info(f"RETRIEVAL_DEBUG [{i+1}]: Title='{item.title}' | Page={item.page_number} | Snippet={repr(item.content[:80])}")
    except Exception as e:
        logger.error(f"Database vector retrieval failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database vector retrieval failed: {str(e)}",
        )

    # 5. Formulate system prompt grounded in retrieved context
    context_blocks = []
    sources = []
    for idx, item in enumerate(retrieved_items):
        clean_content = item.content.replace("[[MATCH_START]]", "").replace("[[MATCH_END]]", "")
        context_blocks.append(
            f"[{idx+1}] Název: {item.title} (Sekce: {item.section_title or 'N/A'}, Strana: {item.page_number or 'N/A'})\n"
            f"Obsah: {clean_content}\n"
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
            "- Spoléhejte se POUZE na poskytnuté dokumenty.\n"
            "- Pokud v poskytnutých dokumentech naleznete odpověď na dotaz (např. nárok v hodinách či dnech), uveďte ji výslovně a připojte přímé citace [1], [2] atd.\n"
            "- Pokud poskytnutý kontext neobsahuje dostatek informací pro úplnou odpověď, uveďte to výslovně.\n\n"
            f"=== ZÍSKANÉ FIREMNÍ DOKUMENTY ===\n{context_str}\n"
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

    messages = [ChatMessage(role="system", content=system_message)]
    # Attach last 6 past message turns for multi-turn conversational context
    for pm in past_messages[-6:]:
        messages.append(ChatMessage(role=pm.role, content=pm.content))
    messages.append(ChatMessage(role="user", content=request.query))

    # 6. Generate grounded LLM response using Azure OpenAI GPT deployment
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

    # 7. Save current user & assistant turn to database if active thread exists
    if active_thread_id and current_db_user:
        try:
            from app.storage.models import DBChatMessage, DBChatThread
            import datetime
            t_uuid = uuid.UUID(active_thread_id)
            sources_dict_list = [s.model_dump() for s in sources]
            user_msg = DBChatMessage(
                tenant_id=settings.TENANT_ID,
                thread_id=t_uuid,
                role="user",
                content=request.query,
            )
            asst_msg = DBChatMessage(
                tenant_id=settings.TENANT_ID,
                thread_id=t_uuid,
                role="assistant",
                content=answer,
                sources=sources_dict_list,
            )
            db.add(user_msg)
            db.add(asst_msg)
            db.query(DBChatThread).filter(DBChatThread.thread_id == t_uuid).update(
                {"updated_at": datetime.datetime.utcnow()}
            )
            db.commit()
        except Exception as e:
            logger.error(f"Failed to persist chat messages to database: {e}")

    latency_ms = int((time.time() - start_time) * 1000)

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
        thread_id=active_thread_id,
    )


@router.get("/config")
async def get_search_config():
    """Get the active retrieval & chunking search configuration."""
    config_manager = SearchConfigManager()
    config = await config_manager.load_config()
    return config


@router.post("/config")
async def save_search_config(config_data: SearchConfigSchema):
    """Update the retrieval & chunking search configuration."""
    config_manager = SearchConfigManager()
    await config_manager.save_config(config_data.model_dump())
    return {"status": "success", "message": "Search configuration saved successfully."}
