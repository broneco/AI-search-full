import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.routes.auth import decode_token
from app.core.config import settings
from app.storage.models import DBUser, DBChatThread, DBChatMessage

router = APIRouter()


class ThreadCreateRequest(BaseModel):
    title: Optional[str] = "Nová konverzace"


class ThreadUpdateRequest(BaseModel):
    title: str


class ThreadResponse(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    sources: Optional[List[dict]] = None
    created_at: str


class ThreadDetailResponse(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[MessageResponse]


def get_current_user_id(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> uuid.UUID:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
        payload = decode_token(token)
        return uuid.UUID(payload["sub"])
    elif x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            pass
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Přihlášení vyžadováno. Prosím přihlaste se k účtu.",
    )


@router.get("", response_model=List[ThreadResponse])
@router.get("/", response_model=List[ThreadResponse], include_in_schema=False)
async def list_threads(
    db: Session = Depends(get_db_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """List all chat threads belonging to the authenticated user in current TENANT_ID."""
    threads = (
        db.query(DBChatThread)
        .filter(
            DBChatThread.tenant_id == settings.TENANT_ID,
            DBChatThread.user_id == user_id,
        )
        .order_by(DBChatThread.updated_at.desc())
        .all()
    )

    result = []
    for t in threads:
        msg_count = db.query(DBChatMessage).filter(DBChatMessage.thread_id == t.thread_id).count()
        if msg_count > 0:
            result.append(
                ThreadResponse(
                    thread_id=str(t.thread_id),
                    title=t.title,
                    created_at=t.created_at.isoformat(),
                    updated_at=t.updated_at.isoformat(),
                    message_count=msg_count,
                )
            )
    return result


@router.post("", response_model=ThreadResponse)
@router.post("/", response_model=ThreadResponse, include_in_schema=False)
async def create_thread(
    request: ThreadCreateRequest,
    db: Session = Depends(get_db_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Create a new chat thread for current user."""
    new_thread = DBChatThread(
        tenant_id=settings.TENANT_ID,
        user_id=user_id,
        title=request.title or "Nová konverzace",
    )
    db.add(new_thread)
    db.commit()
    db.refresh(new_thread)

    return ThreadResponse(
        thread_id=str(new_thread.thread_id),
        title=new_thread.title,
        created_at=new_thread.created_at.isoformat(),
        updated_at=new_thread.updated_at.isoformat(),
        message_count=0,
    )


@router.get("/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread_detail(
    thread_id: str,
    db: Session = Depends(get_db_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Get full message history and citation sources for a specific thread."""
    try:
        t_uuid = uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid thread UUID format.")

    thread = (
        db.query(DBChatThread)
        .filter(
            DBChatThread.tenant_id == settings.TENANT_ID,
            DBChatThread.thread_id == t_uuid,
            DBChatThread.user_id == user_id,
        )
        .first()
    )

    if not thread:
        raise HTTPException(status_code=404, detail="Konverzace nebyla nalezena.")

    messages = (
        db.query(DBChatMessage)
        .filter(DBChatMessage.thread_id == t_uuid)
        .order_by(DBChatMessage.created_at.asc())
        .all()
    )

    msg_responses = [
        MessageResponse(
            message_id=str(m.message_id),
            role=m.role,
            content=m.content,
            sources=m.sources if isinstance(m.sources, list) else None,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]

    return ThreadDetailResponse(
        thread_id=str(thread.thread_id),
        title=thread.title,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
        messages=msg_responses,
    )


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: str,
    request: ThreadUpdateRequest,
    db: Session = Depends(get_db_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Rename thread title."""
    try:
        t_uuid = uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid thread UUID format.")

    thread = (
        db.query(DBChatThread)
        .filter(
            DBChatThread.tenant_id == settings.TENANT_ID,
            DBChatThread.thread_id == t_uuid,
            DBChatThread.user_id == user_id,
        )
        .first()
    )

    if not thread:
        raise HTTPException(status_code=404, detail="Konverzace nebyla nalezena.")

    thread.title = request.title.strip()
    db.commit()
    db.refresh(thread)

    msg_count = db.query(DBChatMessage).filter(DBChatMessage.thread_id == t_uuid).count()
    return ThreadResponse(
        thread_id=str(thread.thread_id),
        title=thread.title,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
        message_count=msg_count,
    )


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: str,
    db: Session = Depends(get_db_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Delete thread and all associated messages."""
    try:
        t_uuid = uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid thread UUID format.")

    thread = (
        db.query(DBChatThread)
        .filter(
            DBChatThread.tenant_id == settings.TENANT_ID,
            DBChatThread.thread_id == t_uuid,
            DBChatThread.user_id == user_id,
        )
        .first()
    )

    if not thread:
        raise HTTPException(status_code=404, detail="Konverzace nebyla nalezena.")

    db.delete(thread)
    db.commit()

    return {"status": "deleted", "thread_id": thread_id}
