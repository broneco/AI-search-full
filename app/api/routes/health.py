from fastapi import APIRouter
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    app_name: str


@router.get("", response_model=HealthResponse)
@router.get("/", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        environment=settings.APP_ENV,
        version="0.1.0",
        app_name=settings.APP_NAME,
    )
