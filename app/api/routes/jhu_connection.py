"""Management-only local/ACA connection controls; never accepts endpoints/credentials."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.identity import Principal, require_manager, get_principal
from app.core.tenant_identity import tenant_config_name
from app.providers.jhu_connection import connection_status, refresh_connection, reconnect_connection

router = APIRouter()


@router.get('/availability')
async def availability(principal: Principal = Depends(get_principal)):
    if tenant_config_name(principal.tenant_id) != 'jhu':
        raise HTTPException(404, 'Tenant nemá spravované JHU připojení.')
    result = await connection_status()
    return {key:result.get(key) for key in ('mode', 'state', 'code')}


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


@router.post('/reconnect', status_code=202)
async def reconnect(principal: Principal = Depends(jhu_manager)):
    return await reconnect_connection()
