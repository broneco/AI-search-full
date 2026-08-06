import logging
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from app.api.dependencies import get_db_session
from app.core.config import settings
from app.core.prompts import get_tenant_prompts_map, update_tenant_prompt, get_tenant_base

router = APIRouter()
logger = logging.getLogger(__name__)


class PromptUpdateRequest(BaseModel):
    locale: str = "cs"
    prompt_text: str


class PromptResponse(BaseModel):
    tenant_id: str
    tenant_base: str
    prompts: Dict[str, str]


@router.get("", response_model=PromptResponse)
@router.get("/", response_model=PromptResponse, include_in_schema=False)
async def get_prompts():
    """Get system prompt templates for current tenant."""
    prompts = get_tenant_prompts_map(settings.TENANT_ID)
    return PromptResponse(
        tenant_id=settings.TENANT_ID,
        tenant_base=get_tenant_base(settings.TENANT_ID),
        prompts=prompts,
    )


@router.put("", response_model=PromptResponse)
@router.put("/", response_model=PromptResponse, include_in_schema=False)
async def update_prompt(request: PromptUpdateRequest):
    """Update custom system prompt for current tenant and locale."""
    if not request.prompt_text or not request.prompt_text.strip():
        raise HTTPException(status_code=400, detail="Text systémového promptu nesmí být prázdný.")
    
    updated_prompts = update_tenant_prompt(
        tenant_id=settings.TENANT_ID,
        locale=request.locale,
        prompt_text=request.prompt_text.strip(),
    )
    logger.info(f"System prompt updated for tenant '{settings.TENANT_ID}' (locale: {request.locale})")
    
    return PromptResponse(
        tenant_id=settings.TENANT_ID,
        tenant_base=get_tenant_base(settings.TENANT_ID),
        prompts=updated_prompts,
    )
