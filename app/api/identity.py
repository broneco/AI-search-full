"""Resolve identity and current permissions from the server's user records."""
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.core.config import settings
from app.storage.models import DBUser
from app.retrieval.filters import exact_value


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    tenant_id: str
    groups: tuple[str, ...]


bearer_scheme = HTTPBearer(auto_error=False)


def get_principal(request: Request, db: Session = Depends(get_db_session),
                  credentials=Security(bearer_scheme)) -> Principal:
    from app.api.routes.auth import decode_token

    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(401, "Invalid authorization header.")
        token = token.strip()
    else:
        token = request.headers.get("X-Session-Token")
    if not token:
        raise HTTPException(401, "Přihlášení vyžadováno.")
    payload = decode_token(token)
    if payload.get("tenant_id") != settings.TENANT_ID:
        raise HTTPException(401, "Token belongs to a different tenant.")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise HTTPException(401, "Invalid user identity.")
    user = db.query(DBUser).filter(
        DBUser.user_id == user_id, exact_value(DBUser.tenant_id, settings.TENANT_ID, db.bind.dialect.name)
    ).first()
    if user is None or user.tenant_id != settings.TENANT_ID:
        raise HTTPException(401, "User is no longer available.")
    groups = user.groups
    if not isinstance(groups, list) or any(not isinstance(group, str) for group in groups):
        raise HTTPException(403, "Invalid server-side group assignment.")
    # Signed token groups and arbitrary X-User-* headers never grant permissions.
    return Principal(user.user_id, user.tenant_id, tuple(sorted({group.strip() for group in groups if group.strip()} | {"User"})))


def require_manager(principal: Principal = Depends(get_principal)) -> Principal:
    if "Management" not in principal.groups:
        raise HTTPException(403, "Management permission required.")
    return principal
