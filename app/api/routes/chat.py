import logging
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.core.config import settings
from app.core.prompts import get_system_prompt
from app.core.search_config import SearchConfigManager, SearchConfigSchema
from app.providers.factory import create_embedding_provider, create_llm_provider
from app.providers.llm import ChatMessage
from app.retrieval.vector import VectorRetriever
from app.retrieval.base import QueryContext
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource, ChatMetadata
from app.api.identity import Principal, get_principal, require_manager
from app.retrieval.filters import validate_filters, exact_value
from app.retrieval.access import ACCESS_POLICY, authorized_history, history_references
from app.storage.vector_store import SearchIndexError
from app.storage.ann_search import prepare_vector_search, sql_query_timeout, SearchExecutionError, execution_error
from sqlalchemy.exc import DBAPIError

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize providers
llm_provider = create_llm_provider()
embedding_provider = create_embedding_provider()


@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse, include_in_schema=False)
@router.post("/query", response_model=ChatResponse, include_in_schema=False)
async def chat_interaction(
    request: ChatRequest,
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(get_principal),
) -> ChatResponse:
    """End-to-end grounded RAG chat endpoint with multi-turn history awareness."""
    start_time = time.time()

    # 1. Authenticate user & load multi-turn thread history first
    past_messages = []
    active_thread_id = None
    from app.storage.models import DBUser
    current_db_user = db.get(DBUser, principal.user_id)
    filters = {k: v for k, v in request.filters.items()
               if k != "additionalProp1" and v != {} and v is not None}
    filters["freshness_filter"] = request.freshness_filter
    try:
        validate_filters(filters)
    except ValueError as error:
        raise HTTPException(422, str(error))

    config_manager = SearchConfigManager()
    search_config = await config_manager.load_config()
    vector_plan = None
    if request.search_strategy in {"vector", "hybrid"}:
        try:
            with sql_query_timeout(db, search_config.get("vector_query_timeout_seconds", 10)):
                vector_plan = prepare_vector_search(db, principal.tenant_id, embedding_provider.profile,
                                                    search_config.get("vector_search_mode", "exact"))
        except DBAPIError as error:
            controlled = execution_error(error, "preflight")
            raise HTTPException(controlled.status_code, str(controlled), headers={"X-Search-Error-Code": controlled.code})
        except SearchExecutionError as error:
            raise HTTPException(error.status_code, str(error), headers={"X-Search-Error-Code": error.code})
        except SearchIndexError as error:
            raise HTTPException(503, str(error))

    from app.storage.models import DBChatThread, DBChatMessage
    user_question_title = request.query[:50] + ("..." if len(request.query) > 50 else "")

    if request.thread_id:
        try:
            t_uuid = uuid.UUID(request.thread_id)
            thread = db.query(DBChatThread).filter(
                exact_value(DBChatThread.tenant_id, principal.tenant_id, db.bind.dialect.name),
                DBChatThread.thread_id == t_uuid,
                DBChatThread.user_id == current_db_user.user_id
            ).first()
            if thread:
                active_thread_id = str(thread.thread_id)
                past_messages = (
                    db.query(DBChatMessage)
                    .filter(DBChatMessage.thread_id == t_uuid,
                            exact_value(DBChatMessage.tenant_id, principal.tenant_id, db.bind.dialect.name))
                    .order_by(DBChatMessage.created_at.asc())
                    .all()
                )
                # Auto-update thread title if it's default "Nová konverzace" or empty
                if thread.title in ("Nová konverzace", "New Chat", "") or len(past_messages) == 0:
                    thread.title = user_question_title
                    db.commit()
            else:
                raise HTTPException(404, "Konverzace nebyla nalezena.")
        except ValueError:
            raise HTTPException(400, "Invalid thread UUID.")

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
        logger.info("Generating query embedding for tenant %s", principal.tenant_id)
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
        
        context = QueryContext(
            query=retrieval_query,
            tenant_id=principal.tenant_id,
            user_id=str(principal.user_id),
            filters=filters,
            acl_groups=list(principal.groups),
        )

        logger.info(f"Executing hybrid retrieval with strategy: {request.search_strategy}")
        retrieved_items = await retriever.retrieve(
            context,
            limit=search_config.get("final_limit", 5),
            query_embedding=query_embedding,
            query_profile=embedding_provider.profile,
            search_strategy=request.search_strategy,
            search_config=search_config,
            vector_plan=vector_plan,
        )
        logger.info("Retrieved %s authorized chunks for tenant %s", len(retrieved_items), principal.tenant_id)
        logger.info("Search diagnostics %s", retriever.diagnostics)
    except SearchExecutionError as error:
        raise HTTPException(error.status_code, str(error), headers={"X-Search-Error-Code": error.code})
    except SearchIndexError as error:
        raise HTTPException(503, str(error))
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
                context_chunk_ids=item.metadata.get("context_chunk_ids", [item.chunk_id]),
            )
        )

    context_str = "\n---\n".join(context_blocks)
    system_message = get_system_prompt(settings.TENANT_ID, request.locale, context_str)

    messages = [ChatMessage(role="system", content=system_message)]
    # Attach last 6 past message turns for multi-turn conversational context
    visible_history = authorized_history(db, past_messages[-6:], principal)
    for pm in visible_history:
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
            references = {(uuid.UUID(chunk_id), uuid.UUID(source.document_id))
                          for source in sources for chunk_id in [source.chunk_id, *source.context_chunk_ids]}
            for past in visible_history:
                references.update(history_references(past) or set())
            saved_evidence = {
                "access_policy": ACCESS_POLICY,
                "citations": [source.model_dump() for source in sources],
                "access_refs": [{"chunk_id": str(cid), "document_id": str(did)}
                                for cid, did in sorted(references)],
            }
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
                sources=saved_evidence,
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
        retrieval_strategy = "vector_" + retriever.diagnostics.get("vector_mode", "exact")
    elif request.search_strategy == "keyword":
        retrieval_strategy = "keyword_sql"
    else:
        retrieval_strategy = "hybrid_" + retriever.diagnostics.get("vector_mode", "exact")

    metadata = ChatMetadata(
        mode=request.mode,
        retrieval_strategy=retrieval_strategy,
        model_profile=request.mode,
        latency_ms=latency_ms,
        search_diagnostics=retriever.diagnostics,
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
async def save_search_config(config_data: SearchConfigSchema, principal: Principal = Depends(require_manager)):
    """Update the retrieval & chunking search configuration."""
    config_manager = SearchConfigManager()
    await config_manager.save_config(config_data.model_dump())
    return {"status": "success", "message": "Search configuration saved successfully."}
