import base64
import hashlib
import hmac
import json
import time
from typing import Optional, List
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.core.config import settings
from app.storage.db import init_db
from app.storage.models import DBUser

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
    email: str
    username: str
    role: str
    groups: List[str]


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


def hash_password(password: str) -> str:
    return hashlib.sha256(f"{password}:{settings.JWT_SECRET}".encode("utf-8")).hexdigest()


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
    signature = hmac.new(settings.JWT_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid token format")
        payload_b64, signature = parts[0], parts[1]
        expected_sig = hmac.new(settings.JWT_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("Invalid token signature")
        
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        if payload.get("exp") and time.time() > payload["exp"]:
            raise ValueError("Token expired")
        return payload
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
    hashed = hash_password(request.password)

    try:
        user = db.query(DBUser).filter(
            DBUser.email == clean_email
        ).first()
    except Exception as query_err:
        # If database tables do not exist (e.g. startup network timeout), auto-initialize schemas and retry
        init_db()
        user = db.query(DBUser).filter(
            DBUser.email == clean_email
        ).first()

    if not user or user.password_hash != hashed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nesprávný e-mail nebo heslo.",
        )

    token = create_token(user)
    return AuthResponse(
        access_token=token,
        user=UserResponse(
            user_id=str(user.user_id),
            email=user.email,
            username=user.username,
            role=user.role,
            groups=user.groups or ["User"],
        ),
    )


@router.post("/register", response_model=AuthResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db_session),
):
    """Register a new user scoped to the current TENANT_ID."""
    clean_email = request.email.strip().lower()
    try:
        existing = db.query(DBUser).filter(
            DBUser.tenant_id == settings.TENANT_ID,
            DBUser.email == clean_email
        ).first()
    except Exception:
        init_db()
        existing = db.query(DBUser).filter(
            DBUser.tenant_id == settings.TENANT_ID,
            DBUser.email == clean_email
        ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uživatel s tímto e-mailem již v organizaci existuje.",
        )

    hashed = hash_password(request.password)
    groups = request.groups or (["User", "Management"] if request.role in ("Management", "Admin") else ["User"])

    new_user = DBUser(
        tenant_id=settings.TENANT_ID,
        email=clean_email,
        username=request.username.strip(),
        password_hash=hashed,
        role=request.role or "User",
        groups=groups,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_token(new_user)
    return AuthResponse(
        access_token=token,
        user=UserResponse(
            user_id=str(new_user.user_id),
            email=new_user.email,
            username=new_user.username,
            role=new_user.role,
            groups=new_user.groups or ["User"],
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
    db: Session = Depends(get_db_session),
):
    """Get profile of current authenticated user from token."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
    elif x_session_token:
        token = x_session_token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Přihlašovací token chybí.",
        )

    payload = decode_token(token)
    user_id = payload.get("sub")

    user = db.query(DBUser).filter(
        DBUser.tenant_id == settings.TENANT_ID,
        DBUser.user_id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uživatel nebyl nalezen.",
        )

    return UserResponse(
        user_id=str(user.user_id),
        email=user.email,
        username=user.username,
        role=user.role,
        groups=user.groups or ["User"],
    )
