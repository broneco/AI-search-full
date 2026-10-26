"""Operational status/refresh never grants model or document permissions."""
import asyncio
import threading
from contextlib import contextmanager

import pytest

from app.core.config import settings
from app.providers import jhu_managed as managed
from app.providers.jhu_connection import connection_status, refresh_connection, slots
from app.providers.jhu_secrets import CredentialPair, JHUConnectionError
from app.core.model_config import ModelError
from test_jhu_transport import managed_service
from test_model_catalog import models_db, models_client, account


def test_status_is_separate_from_backend_health_and_sanitized(models_db, models_client, managed_service):
    _, headers = account(models_db, ['Management'])
    state = managed_service[1]
    state['ready'] = False
    result = models_client.get('/api/models/connection', headers=headers)
    assert result.status_code == 200 and result.json()['state'] == 'connecting'
    assert models_client.get('/api/health').json()['status'] == 'healthy'
    assert not {'endpoint','key','credentials','username','password','forwarded'} & result.json().keys()


def test_status_and_refresh_require_current_management_and_exact_tenant(models_db, models_client, managed_service, monkeypatch):
    assert models_client.get('/api/models/connection').status_code == 401
    normal, headers = account(models_db, ['User'])
    for method,path in [('get','/api/models/connection'), ('post','/api/models/connection/refresh')]:
        assert getattr(models_client, method)(path, headers={**headers,'X-User-Groups':'Management'}).status_code == 403
    manager, headers = account(models_db, ['Management'])
    assert models_client.post('/api/models/connection/refresh',headers=headers).status_code == 200
    manager.groups=['User']; models_db.commit()
    assert models_client.post('/api/models/connection/refresh',headers=headers).status_code == 403
    monkeypatch.setattr(settings,'TENANT_ID','other')
    _, other_headers=account(models_db,['Management'])
    before=len(managed_service[2])
    assert models_client.get('/api/models/connection',headers=other_headers).status_code == 404
    assert models_client.get('/api/models/connection',headers=headers).status_code == 401
    assert len(managed_service[2]) == before


def test_refresh_is_explicit_atomic_and_can_load_new_api_credentials(managed_service, monkeypatch):
    first=managed.managed_connection()
    @contextmanager
    def failure(*_):
        raise JHUConnectionError('jhu_vault_forbidden')
        yield
    monkeypatch.setattr(managed,'key_vault_resolver',failure)
    with pytest.raises(JHUConnectionError): managed.refresh_managed_connection()
    assert managed.managed_connection() is first
    @contextmanager
    def changed(*_):
        yield type('Resolver',(),{'api_credentials':lambda _:CredentialPair('rotated-user','rotated-password')})()
    monkeypatch.setattr(managed,'key_vault_resolver',changed)
    monkeypatch.setattr(managed,'verify_helper',lambda:('http://127.0.0.1:12345','b'*64))
    managed.refresh_managed_connection()
    second=managed.managed_connection()
    assert second.key != first.key and second.credentials.username == 'rotated-user'
    assert second.endpoint == 'http://127.0.0.1:12345'
    assert 'rotated' not in repr(second)


def test_refresh_does_not_interrupt_an_inflight_operation_or_repeat_model_call(managed_service):
    assert slots.acquire(blocking=False)
    try:
        with pytest.raises(ModelError) as caught: asyncio.run(refresh_connection())
        assert caught.value.code == 'model_busy'
        assert managed_service[2] == [] and managed_service[3] == []
    finally: slots.release()


def test_disconnected_refresh_caller_does_not_release_the_slot_while_kv_is_running(managed_service, monkeypatch):
    entered,release=threading.Event(),threading.Event()
    def refresh():
        entered.set(); assert release.wait(3)
    monkeypatch.setattr(managed,'refresh_managed_connection',refresh)
    async def exercise():
        task=asyncio.create_task(refresh_connection())
        try:
            assert await asyncio.to_thread(entered.wait,1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
            assert not slots.acquire(blocking=False)
        finally: release.set()
        for _ in range(100):
            await asyncio.sleep(.01)
            if slots.acquire(blocking=False):
                slots.release();return
        raise AssertionError('Refresh slot did not return after worker exit')
    asyncio.run(exercise())


def test_terminal_status_remains_visible_after_heartbeat_ages(managed_service):
    managed_service[1]['health_body']=dict(protocol_version=2,state='auth_failed',code='vpn_auth_failed',
        attempts=1,generation=0,tls_channels=0,updated_at=1)
    result=asyncio.run(connection_status())
    assert result['state']=='auth_failed' and result['code']=='vpn_auth_failed'


def test_connection_error_and_sticky_failure_can_be_explicitly_refreshed(managed_service, monkeypatch):
    original=managed.verify_helper
    def fail(): raise JHUConnectionError('jhu_helper_unavailable')
    monkeypatch.setattr(managed,'verify_helper',fail)
    assert asyncio.run(connection_status())['code']=='jhu_helper_unavailable'
    monkeypatch.setattr(managed,'verify_helper',original)
    assert asyncio.run(connection_status())['state']=='degraded'
    assert asyncio.run(refresh_connection())['state']=='ready'
