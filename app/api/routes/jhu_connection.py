"""Management-only local connection controls; never accepts endpoints/credentials."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.identity import Principal, require_manager
from app.core.tenant_identity import tenant_config_name
from app.providers.jhu_connection import connection_status, refresh_connection

router = APIRouter()


def jhu_manager(principal: Principal = Depends(require_manager)) -> Principal:
    if tenant_config_name(principal.tenant_id) != 'jhu':
        raise HTTPException(404, 'Tenant nemá spravované JHU připojení.')
    return principal


@router.get('')
async def status(principal: Principal = Depends(jhu_manager)):
    return await connection_status()


@router.post('/refresh')
async def refresh(principal: Principal = Depends(jhu_manager)):
    return await refresh_connection()
