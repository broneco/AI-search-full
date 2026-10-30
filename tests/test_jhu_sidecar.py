"""ACA context, MI-only snapshots and fixed loopback transport; no cloud access."""
import asyncio
from contextlib import contextmanager
import importlib
import importlib.util
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.core.embedding_config import embedding_entry
from app.core.model_config import ModelError, load_model_catalog
from app.providers import jhu_managed as managed
from app.providers.jhu_connection import connection_status, refresh_connection
from app.providers.jhu_secrets import (CredentialPair, JHUConnectionError, JHUSecretResolver,
                                     SidecarAPISecretReferences)
from app.providers.jhu_sidecar import ENDPOINT, sidecar_context
from app.providers.llm import ChatMessage
from app.providers.model_discovery import discover_models
from app.providers.model_runtime import ProfileLLMProvider
from app.providers.ollama_embeddings import OllamaEmbeddingProvider
from scripts.vpn_spike.cloud import CloudBootstrapError, cloud_config, load_payload
from test_jhu_transport import managed_service

PROFILE = ('client\ndev tun\nproto udp\nremote vpn.example.test 1194\nauth-user-pass\n'
           'auth-nocache\nverify-x509-name vpn.example.test name\n<ca>\nAAAA\n</ca>\n')


def runtime_env():
    return dict(APP_ENV='prod', TENANT_ID='ju-prod', JHU_CONNECTION_MODE='sidecar', JHU_SIDECAR_APP_NAME='test-app',
                CONTAINER_APP_NAME='test-app', CONTAINER_APP_REVISION='test-app--test',
                CONTAINER_APP_REPLICA_NAME='test-app--test-replica',
                IDENTITY_ENDPOINT='http://127.0.0.1:42356/msi/token', IDENTITY_HEADER='synthetic-platform-token',
                JHU_LLM_ENDPOINT='http://192.0.2.1:11434', JHU_KEY_VAULT_NAME='test-vault',
                JHU_VPN_USERNAME_SECRET='vpn-user', JHU_VPN_PASSWORD_SECRET='vpn-password',
                JHU_VPN_PROFILE_SECRET='vpn-profile', JHU_GATEWAY_KEY_SECRET='gateway-key')


@pytest.fixture
def sidecar_service(managed_service, monkeypatch):
    _, state, _, reads = managed_service
    env = runtime_env()
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    for key, value in dict(APP_ENV='prod', JHU_CONNECTION_MODE='sidecar',
                           JHU_SIDECAR_APP_NAME='test-app', JHU_GATEWAY_KEY_SECRET='gateway-key').items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr('app.providers.jhu_sidecar.platform.system', lambda: 'Linux')
    monkeypatch.setattr(managed, 'verify_helper', lambda: pytest.fail('Cloud must not call Docker'))
    @contextmanager
    def resolver(vault, refs, identity):
        assert identity == 'managed_identity' and isinstance(refs, SidecarAPISecretReferences)
        assert not hasattr(refs, 'vpn_username')
        reads.append(identity)
        yield SimpleNamespace(api_credentials=lambda: CredentialPair('vault-user','vault-password'),
                              gateway_key=lambda:'a'*64)
    monkeypatch.setattr(managed, 'key_vault_resolver', resolver)
    state['health_body'] = dict(state='ready', updated_at=time.time(), protocol_version=2,
                                context=sidecar_context(settings))
    return managed_service


def test_aca_chat_embedding_discovery_share_mi_snapshot_without_docker(sidecar_service):
    entry, _, calls, reads = sidecar_service
    async def exercise():
        assert await ProfileLLMProvider(load_model_catalog('ju-prod').profiles[-1]).generate(
            [ChatMessage(role='user',content='Otázka')]) == 'Odpověď [1]'
        assert len(await OllamaEmbeddingProvider(entry).embed_query('Dotaz')) == 768
        assert len((await discover_models())['models']) == 1
        state = await connection_status()
        assert state['mode']=='sidecar' and state['state']=='ready'
        assert not {'context','target','username','password','key','endpoint'} & state.keys()
        assert (await refresh_connection())['state']=='ready'
    asyncio.run(exercise())
    assert reads == ['managed_identity','managed_identity']
    assert all(str(request.url).startswith(ENDPOINT) for request in calls)


@pytest.mark.parametrize('field,value', [('application','other'), ('replica','other'),
                                        ('tenant','other'), ('target','192.0.2.2:11434')])
def test_wrong_sidecar_context_never_receives_model_request(sidecar_service, field, value):
    entry,state,calls,_ = sidecar_service
    state['health_body']['context'][field] = value
    with pytest.raises(ModelError) as error:
        asyncio.run(OllamaEmbeddingProvider(entry).embed_query('Text'))
    assert error.value.code=='jhu_connection_unavailable'
    assert [request.url.path for request in calls] == ['/_jhu/health']


@pytest.mark.parametrize('field,value', [('APP_ENV','local'), ('TENANT_ID','other-prod'),
    ('JHU_LLM_ENDPOINT','http://localhost:11434'), ('JHU_LLM_ENDPOINT','https://192.0.2.1:11434'),
    ('JHU_SIDECAR_APP_NAME','other-app'), ('JHU_GATEWAY_KEY_SECRET','api-user')])
def test_invalid_cloud_config_fails_before_any_secret_read(sidecar_service, monkeypatch, field, value):
    monkeypatch.setattr(settings,field,value)
    with pytest.raises(JHUConnectionError): managed.managed_connection()
    assert sidecar_service[3] == []


def test_cloud_requires_platform_identity_and_keeps_local_guard(sidecar_service, monkeypatch):
    monkeypatch.delenv('IDENTITY_HEADER')
    with pytest.raises(JHUConnectionError,match='jhu_sidecar_runtime_invalid'): managed.managed_connection()
    monkeypatch.setattr(settings,'JHU_CONNECTION_MODE','managed')
    with pytest.raises(JHUConnectionError,match='jhu_managed_local_only'): managed.managed_connection()


def test_cloud_helper_only_reads_four_vpn_profile_gateway_secrets(monkeypatch):
    import azure.identity
    import azure.keyvault.secrets
    monkeypatch.setattr('scripts.vpn_spike.cloud.sys.platform','linux')
    config=cloud_config(runtime_env());reads=[];closed=[]
    values=dict(zip(config['references'],['vpn-name','vpn-pass',PROFILE,'a'*64]))
    class Credential:
        def __enter__(self):return self
        def __exit__(self,*_):closed.append('identity')
    class Client(Credential):
        def get_secret(self,name):
            reads.append(name);return SimpleNamespace(value=values[name])
        def __exit__(self,*_):closed.append('vault')
    def identity(**kwargs):
        assert kwargs['retry_total']==0;return Credential()
    def client(**kwargs):
        assert kwargs['retry_total']==0 and kwargs['logging_enable'] is False;return Client()
    monkeypatch.setattr(azure.identity,'ManagedIdentityCredential',identity)
    monkeypatch.setattr(azure.identity,'AzureCliCredential',lambda **_:pytest.fail('No CLI identity'))
    monkeypatch.setattr(azure.keyvault.secrets,'SecretClient',client)
    payload=load_payload(config)
    assert payload['gateway_key']=='a'*64 and payload['profile']==PROFILE
    assert reads==['vpn-user','vpn-password','vpn-profile','gateway-key']
    assert closed==['vault','identity'] and 'api_username' not in payload
    values['gateway-key']='private invalid value'
    with pytest.raises(CloudBootstrapError) as error:load_payload(config)
    assert str(error.value)=='vpn_cloud_secrets_unavailable' and error.value.__suppress_context__


def test_backend_gateway_reference_cannot_resolve_vpn_credentials():
    refs=SidecarAPISecretReferences('api-user','api-password','gateway-key')
    reader=SimpleNamespace(get_secret=lambda name:SimpleNamespace(value='b'*64))
    resolver=JHUSecretResolver(reader,refs)
    assert resolver.gateway_key()=='b'*64
    with pytest.raises(JHUConnectionError,match='jhu_vpn_credentials_not_configured'):
        resolver.vpn_credentials()


def test_cloud_bootstrap_failure_stays_alive_without_retry_or_private_files(tmp_path,monkeypatch,capsys):
    # Load the flat container entrypoint with its actual sibling modules.
    for name in ('profile','lifecycle','gateway'):
        monkeypatch.setitem(sys.modules,name,importlib.import_module('scripts.vpn_spike.'+name))
    spec=importlib.util.spec_from_file_location('sidecar_service_under_test',
        Path(__file__).resolve().parents[1]/'scripts/vpn_spike/service.py')
    service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)
    monkeypatch.setattr(service,'RUNTIME',tmp_path)
    statuses=[]
    monkeypatch.setattr(service,'write_json',lambda name,data:statuses.append(dict(data)))
    monkeypatch.setattr(service.signal,'signal',lambda *_:None)
    monkeypatch.setattr(service.signal,'SIGUSR1',10,raising=False)
    events=[]
    class Event:
        stopped=False
        def set(self):self.stopped=True
        def is_set(self):return self.stopped
        def wait(self,timeout=None):
            assert timeout is None;events.append('held-terminal');self.stopped=True
    class Gateway:
        def __init__(self,address,*_):assert address==('127.0.0.1',18081)
        def serve_forever(self):pass
        def abort_upstreams(self):pass
        def shutdown(self):pass
        def server_close(self):pass
    monkeypatch.setattr(service.threading,'Event',Event)
    monkeypatch.setattr(service.threading,'Thread',lambda **_:SimpleNamespace(start=lambda:None))
    monkeypatch.setattr(service,'GatewayServer',Gateway)
    class Liveness(Gateway):
        def __init__(self,address,*_):assert address==('0.0.0.0',18082)
    monkeypatch.setattr(service,'LivenessServer',Liveness)
    monkeypatch.setattr(service.subprocess,'Popen',lambda *_a,**_k:pytest.fail('No VPN before valid secrets'))
    calls=[]
    def load():calls.append(1);raise RuntimeError('PRIVATE secret from SDK')
    service.serve(load,{})
    assert calls==[1] and events==['held-terminal']
    assert any(row.get('code')=='vpn_cloud_bootstrap_failed' for row in statuses)
    assert capsys.readouterr().out=='{"code":"vpn_cloud_bootstrap_failed"}\n'
    assert not any((tmp_path/name).exists() for name in ('auth','client.conf','gateway.key','bootstrap.json'))
