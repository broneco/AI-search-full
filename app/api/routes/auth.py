import base64
import hashlib
import hmac
import json
import time
import math
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_db_session
from app.core.config import settings
from app.core.passwords import hash_password, verify_password, consume_dummy_verification
from app.storage.db import init_db
from app.storage.models import DBUser
from app.retrieval.filters import exact_value
from app.api.identity import Principal, get_principal, require_manager, bearer_scheme

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str
    role: Optional[str] = "User"
    groups: Optional[List[str]] = None


class UserResponse(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    username: str
    role: str
    groups: List[str]


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


def _signing_key() -> bytes:
    if settings.APP_ENV not in {"local", "test"} and settings.JWT_SECRET == "dolphin-ai-search-secret-key-2026":
        raise HTTPException(503, "Configure a private JWT_SECRET before enabling authentication.")
    if not settings.JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET is missing.")
    return settings.JWT_SECRET.encode("utf-8")


def _legacy_password_secret() -> str | None:
    if settings.LEGACY_PASSWORD_SECRET:
        return settings.LEGACY_PASSWORD_SECRET
    # Developer/demo compatibility only. Never guess an old production key.
    if settings.APP_ENV in {"local", "test"}:
        return settings.JWT_SECRET
    return None


def create_token(user: DBUser) -> str:
    payload = {
        "sub": str(user.user_id),
        "tenant_id": user.tenant_id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "groups": user.groups or ["User"],
        "exp": int(time.time()) + (30 * 86400), # 30 days valid
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(_signing_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid token format")
        payload_b64, signature = parts[0], parts[1]
        expected_sig = hmac.new(_signing_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("Invalid token signature")
        
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict) or type(payload.get("exp")) not in (int, float):
            raise ValueError("Missing token expiration")
        if not math.isfinite(payload["exp"]) or time.time() >= payload["exp"]:
            raise ValueError("Token expired")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Neplatný nebo vypršený přístupový token.",
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db_session),
):
    """Authenticate user with email and password within the database scope."""
    clean_email = request.email.strip().lower()
    _signing_key()  # Fail before database writes if cloud signing is unavailable.

    try:
        user = db.query(DBUser).filter(
            exact_value(DBUser.tenant_id, settings.TENANT_ID, db.bind.dialect.name),
            DBUser.email == clean_email
        ).first()
    except Exception as query_err:
        # If database tables do not exist (e.g. startup network timeout), auto-initialize schemas and retry
        init_db()
        user = db.query(DBUser).filter(
            exact_value(DBUser.tenant_id, settings.TENANT_ID, db.bind.dialect.name),
            DBUser.email == clean_email
        ).first()

    valid, upgrade = False, False
    previous_hash = user.password_hash if user and user.tenant_id == settings.TENANT_ID else None
    if previous_hash:
        valid, upgrade = await run_in_threadpool(
            verify_password, request.password, previous_hash, legacy_secret=_legacy_password_secret()
        )
    if not valid:
        if not previous_hash or not previous_hash.startswith("$argon2id$"):
            await run_in_threadpool(consume_dummy_verification, request.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nesprávný e-mail nebo heslo.",
        )

    token = create_token(user)
    if upgrade:
        upgraded_hash = await run_in_threadpool(hash_password, request.password)
        # Do not overwrite a password reset that happened during verification.
        try:
            changed = db.execute(update(DBUser).where(
                DBUser.user_id == user.user_id,
                exact_value(DBUser.tenant_id, settings.TENANT_ID, db.bind.dialect.name),
                exact_value(DBUser.password_hash, previous_hash, db.bind.dialect.name),
            ).values(password_hash=upgraded_hash).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(401, "Přihlašovací údaje se změnily. Přihlaste se znovu.")
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503, "Přihlášení nyní nelze bezpečně dokončit.") from None
    return AuthResponse(
        access_token=token,
        user=UserResponse(
            user_id=str(user.user_id),
            tenant_id=user.tenant_id,
            email=user.email,
            username=user.username,
            role=user.role,
            groups=user.groups or ["User"],
        ),
    )


@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    http_request: Request,
    db: Session = Depends(get_db_session),
    credentials=Security(bearer_scheme),
):
    """Register a new user scoped to the current TENANT_ID."""
    if settings.APP_ENV not in {"local", "test"}:
        if not http_request.headers.get("Authorization") and not http_request.headers.get("X-Session-Token"):
            raise HTTPException(403, "Registraci v organizaci provádí správce.")
        require_manager(get_principal(http_request, db))
    _signing_key()
    clean_email = request.email.strip().lower()
    try:
        existing = db.query(DBUser).filter(
            exact_value(DBUser.tenant_id, settings.TENANT_ID, db.bind.dialect.name),
            DBUser.email == clean_email
        ).first()
    except Exception:
        init_db()
        existing = db.query(DBUser).filter(
            exact_value(DBUser.tenant_id, settings.TENANT_ID, db.bind.dialect.name),
            DBUser.email == clean_email
        ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uživatel s tímto e-mailem již v organizaci existuje.",
        )

    hashed = await run_in_threadpool(hash_password, request.password)
    # Self-registration cannot grant privileged roles or custom ACL groups.
    groups = ["User"]

    new_user = DBUser(
        tenant_id=settings.TENANT_ID,
        email=clean_email,
        username=request.username.strip(),
        password_hash=hashed,
        role="User",
        groups=groups,
    )
    db.add(new_user)
    db.flush()
    token = create_token(new_user)
    db.commit()
    db.refresh(new_user)

    return AuthResponse(
        access_token=token,
        user=UserResponse(
            user_id=str(new_user.user_id),
            tenant_id=new_user.tenant_id,
            email=new_user.email,
            username=new_user.username,
            role=new_user.role,
            groups=new_user.groups or ["User"],
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_current_user(
    db: Session = Depends(get_db_session),
    principal: Principal = Depends(get_principal),
):
    """Get profile of current authenticated user from token."""
    user = db.get(DBUser, principal.user_id)

    return UserResponse(
        user_id=str(user.user_id),
        tenant_id=user.tenant_id,
        email=user.email,
        username=user.username,
        role=user.role,
        groups=user.groups or ["User"],
    )
