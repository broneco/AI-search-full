"""One guarded helper path for all providers, without Docker/KV/network access."""
import asyncio
import base64
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import time

import httpx
import pytest

from app.core.config import settings
from app.core.embedding_config import embedding_entry
from app.core.model_config import ModelError, load_model_catalog
from app.providers.jhu_secrets import CredentialPair, JHUConnectionError
from app.providers import jhu_managed as managed
from app.providers.llm import ChatMessage
from app.providers.model_runtime import ProfileLLMProvider, availability
from app.providers.ollama_embeddings import OllamaEmbeddingProvider
from app.providers.model_discovery import discover_models


@pytest.fixture
def managed_service(monkeypatch):
    for key, value in dict(APP_ENV='test', TENANT_ID='ju-prod', JHU_CONNECTION_MODE='managed',
            JHU_LLM_ENDPOINT='http://192.0.2.1:11434', JHU_LLM_ALLOW_HTTP=True,
            JHU_KEY_VAULT_NAME='test-vault', JHU_API_USERNAME_SECRET='api-user',
            JHU_API_PASSWORD_SECRET='api-password', JHU_LLM_USERNAME='old-env-user',
            JHU_LLM_PASSWORD='old-env-password', JHU_LLM_VERIFIED_MODEL='qwen3.8:latest').items():
        monkeypatch.setattr(settings, key, value)
    managed.reset_managed_connection()
    calls, reads = [], []
    state = dict(ready=True, timeout=False)
    monkeypatch.setattr(managed, 'verify_helper', lambda: ('http://127.0.0.1:18081', 'a'*64))

    @contextmanager
    def resolver(vault, refs):
        assert refs.api_username == 'api-user' and not hasattr(refs, 'vpn_username')
        reads.append(vault)
        yield type('Resolver', (), {'api_credentials': lambda _: CredentialPair('vault-user', 'vault-password')})()

    monkeypatch.setattr(managed, 'key_vault_resolver', resolver)
    entry = embedding_entry('ju-prod', 'jhu-nomic')
    digest = entry.space().model_revision.removeprefix('sha256:')

    def handler(request):
        calls.append(request)
        assert request.url.host == '127.0.0.1' and request.headers['X-JHU-Connection'] == 'a'*64
        expected = 'Basic ' + base64.b64encode(b'vault-user:vault-password').decode()
        assert request.headers['Authorization'] == expected
        if request.url.path == '/_jhu/health':
            return httpx.Response(200, json=state.get('health_body', dict(state='ready' if state['ready'] else 'connecting',
                protocol_version=2, updated_at=time.time())))
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models':[{'name':entry.space().model_id, 'digest':digest}]})
        if request.url.path == '/api/show':
            return httpx.Response(200, json={'capabilities':['embedding'], 'details':{'family':'nomic-bert'},
                        'model_info':{'nomic-bert.embedding_length':768, 'nomic-bert.context_length':2048}})
        if state['timeout']:
            raise httpx.ReadTimeout('private upstream details')
        if request.url.path == '/api/embed':
            data = json.loads(request.content)
            return httpx.Response(200, json={'model':entry.space().model_id,
                'embeddings':[[1.0]+[0.0]*767 for _ in data['input']]})
        assert request.url.path == '/api/generate'
        return httpx.Response(state.get('generation_status', 200),
            json=state.get('generation_body', {'response':'Odpověď [1]', 'done':True}))

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))
    yield entry, state, calls, reads
    managed.reset_managed_connection()


def test_chat_embedding_and_discovery_share_verified_connection_and_one_kv_snapshot(managed_service):
    entry, _, calls, reads = managed_service

    async def exercise():
        answer = await ProfileLLMProvider(load_model_catalog('ju-prod').profiles[-1]).generate([ChatMessage(role='user', content='Otázka')])
        assert answer == 'Odpověď [1]'
        assert len(await OllamaEmbeddingProvider(entry).embed_query('Dotaz')) == 768
        assert len((await discover_models())['models']) == 1

    asyncio.run(exercise())
    assert reads == ['test-vault']
    paths = [request.url.path for request in calls]
    assert {'/api/generate','/api/embed','/api/tags','/api/show'} <= set(paths)
    assert paths.count('/_jhu/health') == 3


def test_only_verified_tls_context_is_reused_across_distinct_event_loops(managed_service, monkeypatch):
    import ssl
    contexts,clients=[],[]
    factory=httpx.AsyncClient
    def record(**kwargs):
        contexts.append(kwargs['verify'])
        client=factory(**kwargs);clients.append(client)
        return client
    monkeypatch.setattr(httpx,'AsyncClient',record)
    provider=ProfileLLMProvider(load_model_catalog('ju-prod').profiles[-1])
    for _ in range(2):
        asyncio.run(provider.generate([ChatMessage(role='user',content='Otázka')]))
    assert contexts[0] is contexts[1]
    assert contexts[0].verify_mode==ssl.CERT_REQUIRED and contexts[0].check_hostname
    assert clients[0] is not clients[1] and all(client.is_closed for client in clients)


def test_unready_helper_never_sends_model_call_and_next_question_can_recover(managed_service):
    _, state, calls, reads = managed_service
    provider = ProfileLLMProvider(load_model_catalog('ju-prod').profiles[-1])
    state['ready'] = False
    with pytest.raises(ModelError) as error:
        asyncio.run(provider.generate([ChatMessage(role='user', content='Dotaz')]))
    assert error.value.code == 'jhu_connection_unavailable'
    assert all(r.url.path == '/_jhu/health' for r in calls)
    state['ready'] = True
    assert asyncio.run(provider.generate([ChatMessage(role='user', content='Další dotaz')])) == 'Odpověď [1]'
    assert reads == ['test-vault']


def test_generation_timeout_has_no_retry_or_fallback(managed_service):
    _, state, calls, _ = managed_service
    state['timeout'] = True
    with pytest.raises(ModelError) as error:
        asyncio.run(ProfileLLMProvider(load_model_catalog('ju-prod').profiles[-1]).generate([ChatMessage(role='user', content='Dotaz')]))
    assert error.value.code == 'model_timeout'
    assert sum(r.url.path == '/api/generate' for r in calls) == 1


def test_busy_operations_reject_before_docker_or_key_vault_lookup(managed_service):
    from app.providers.jhu_connection import slots
    assert slots.acquire(blocking=False)
    async def exercise():
        operations=(lambda:ProfileLLMProvider(load_model_catalog('ju-prod').profiles[-1]).generate([
            ChatMessage(role='user',content='Dotaz')]),
            lambda:OllamaEmbeddingProvider(managed_service[0]).embed_query('Dotaz'),discover_models)
        for operation in operations:
            with pytest.raises(ModelError) as caught: await operation()
            assert caught.value.code=='model_busy'
    try:
        asyncio.run(exercise())
        assert managed_service[2] == [] and managed_service[3] == []
    finally: slots.release()


def test_public_managed_probe_uses_common_transport(managed_service, capsys):
    from probe_jhu_model import managed_probe
    assert asyncio.run(managed_probe('qwen3.8:latest')) == 0
    results = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(results) == 2 and all(r['model'] == 'qwen3.8:latest' for r in results)
    assert sum(r.url.path == '/api/generate' for r in managed_service[2]) == 2


@pytest.mark.parametrize('body,status,code', [
    ([],200,'jhu_probe_response_invalid'),
    ({'response':''},200,'jhu_probe_response_empty'),
    ({'response':'text','model':'other'},200,'jhu_probe_model_mismatch'),
    ({'error':'private-provider-details'},401,'jhu_probe_request_rejected'),
])
def test_cli_probe_failure_is_specific_redacted_and_never_retried(managed_service, capsys, body, status, code):
    from probe_jhu_model import managed_probe
    managed_service[1].update(generation_body=body,generation_status=status)
    assert asyncio.run(managed_probe('qwen3.8:latest')) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['error'] == code
    assert 'private' not in json.dumps(result)
    assert sum(r.url.path == '/api/generate' for r in managed_service[2]) == 1


@pytest.mark.parametrize('failure', [False, True])
def test_backend_startup_initializes_once_and_optional_failure_is_nonfatal(managed_service, monkeypatch, failure):
    from app.main import app, lifespan
    calls = []
    def initialize():
        calls.append('managed')
        if failure:
            raise JHUConnectionError('jhu_vault_forbidden')
    monkeypatch.setattr(managed, 'managed_connection', initialize)
    monkeypatch.setattr('app.main.init_db', lambda: calls.append('database'))
    async def exercise():
        async with lifespan(app):
            calls.append('ready')
    asyncio.run(exercise())
    assert calls == ['managed', 'database', 'ready']


@pytest.mark.parametrize('health_body', [[], {'state':'ready','protocol_version':1,'updated_at':0},
    {'state':'ready','protocol_version':2,'updated_at':0}])
def test_malformed_or_stale_health_fails_before_model_call(managed_service, health_body):
    _, state, calls, _ = managed_service
    state['health_body'] = health_body
    with pytest.raises(ModelError) as caught:
        asyncio.run(ProfileLLMProvider(load_model_catalog('ju-prod').profiles[-1]).generate([
            ChatMessage(role='user', content='Dotaz')]))
    assert caught.value.code == 'jhu_connection_unavailable'
    assert len(calls) == 1 and calls[0].url.path == '/_jhu/health'


@pytest.mark.parametrize('field,value', [('APP_ENV','prod'), ('TENANT_ID','other'),
    ('JHU_LLM_ALLOW_HTTP',False), ('JHU_LLM_ENDPOINT','http://example.test:invalid')])
def test_managed_mode_rejects_invalid_environment_before_io(managed_service, monkeypatch, field, value):
    monkeypatch.setattr(settings, field, value)
    assert availability(load_model_catalog('ju-prod').profiles[-1])[0] is False
    assert managed_service[2] == [] and managed_service[3] == []


def test_vault_failure_is_sticky_and_only_disables_jhu(managed_service, monkeypatch):
    _, _, calls, _ = managed_service
    def fail(*_): raise JHUConnectionError('jhu_vault_forbidden')
    monkeypatch.setattr(managed, 'key_vault_resolver', fail)
    with pytest.raises(JHUConnectionError, match='jhu_vault_forbidden'):
        managed.managed_connection()
    assert not availability(load_model_catalog('ju-prod').profiles[-1])[0]
    assert calls == []
    monkeypatch.setattr(settings, 'AZURE_OPENAI_ENDPOINT', 'https://azure.example.test')
    monkeypatch.setattr(settings, 'AZURE_OPENAI_API_KEY', 'test-key')
    assert availability(load_model_catalog('ju-prod').profiles[0])[0]


@pytest.mark.parametrize('host_ip,target,protocol', [('0.0.0.0','192.0.2.1:11434','2'),
    ('127.0.0.1','192.0.2.9:11434','2'), ('127.0.0.1','192.0.2.1:11434','1')])
def test_mapping_guard_rejects_public_binding_wrong_target_or_protocol(managed_service, monkeypatch, host_ip,target,protocol):
    # Call the real guard, not the fixture stub.
    import importlib
    guard = importlib.reload(managed).verify_helper
    owner = __import__('hashlib').sha256(str(Path.cwd()).casefold().encode()).hexdigest()[:16]
    data = dict(id='b'*64, running=True, labels={'ai-search.owner':owner, 'ai-search.jhu-helper':'v1',
        'ai-search.jhu-protocol':protocol, 'ai-search.jhu-target':target},
        ports={'18081/tcp':[{'HostIp':host_ip,'HostPort':'12345'}]})
    monkeypatch.setattr(subprocess, 'run', lambda *a,**kw: subprocess.CompletedProcess(a,0,json.dumps(data).encode(),b''))
    with pytest.raises(JHUConnectionError, match='jhu_helper_mapping_invalid'):
        guard()
