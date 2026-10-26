"""Opt-in faults against an owned helper only; optional explicitly approved Docker restart."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import time

import httpx
import pytest

from app.core.config import Settings, settings
from app.core.embedding_config import embedding_entry
from app.core.local_model_registry import make_profile
from app.core.model_config import ModelError
from app.providers.jhu_connection import (connection_status, embedding_connection, jhu_client, refresh_connection)
from app.providers.jhu_managed import reset_managed_connection
from app.providers.jhu_secrets import SecretReferences, key_vault_resolver
from app.providers.llm import ChatMessage
from app.providers.model_discovery import discover_models
from app.providers.model_runtime import ProfileLLMProvider
from app.providers.ollama_embeddings import OllamaEmbeddingProvider
from scripts.vpn_spike.manager import HelperManager


def restart_rancher():
    """Only under the separate opt-in; never reset/unregister/delete anything."""
    executable=Path(os.getenv('RANCHER_DESKTOP_EXE', str(Path(os.environ['ProgramFiles'])/'Rancher Desktop'/'Rancher Desktop.exe')))
    assert executable.is_file()
    result=subprocess.run(['rdctl','shutdown'],capture_output=True,timeout=60)
    assert result.returncode == 0, 'Rancher shutdown failed; raw output withheld'
    subprocess.run(['powershell.exe','-NoProfile','-Command',
        "Get-Process -Name 'Rancher Desktop' -ErrorAction SilentlyContinue | Wait-Process -Timeout 45"],
        capture_output=True,timeout=50)
    command="Start-Process -FilePath '"+str(executable).replace("'","''")+"' -WindowStyle Hidden"
    subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,check=True,timeout=15)
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        result=subprocess.run(['docker','version','--format','{{.Server.Version}}'],capture_output=True,timeout=15)
        if result.returncode == 0: return
        time.sleep(2)
    raise AssertionError('Docker did not return after Rancher restart')


def test_live_managed_rekey_fault_refresh_and_soak(tmp_path, monkeypatch):
    if os.getenv('RUN_JHU_RESILIENCE_TESTS') != '1':
        pytest.skip('Explicit RUN_JHU_RESILIENCE_TESTS=1; private profile/KV/Docker required')
    soak=int(os.getenv('JHU_RESILIENCE_SOAK_SECONDS','300'))
    assert 120<=soak<=3600
    root=Path(__file__).resolve().parents[1]
    local=Settings(_env_file=(root/'.env.jhu-model',root/'.env.local'),APP_ENV='local',TENANT_ID='jhu')
    owner_root=tmp_path/'helper-owner';owner_root.mkdir()
    manager=HelperManager(owner_root)
    assert manager.inspect() is None, 'Refuse to alter any pre-existing helper'
    source=Path(os.getenv('JHU_VPN_PROFILE',str(Path.home()/'OpenVPN/config/Client/Client.ovpn'))).read_text(encoding='utf-8-sig')
    # Only this test's derived tmpfs profile uses a shorter rekey interval.
    profile=re.sub(r'^reneg-sec .*\n?','',source,flags=re.MULTILINE).rstrip()+'\nreneg-sec 30\n'
    vault=os.getenv('JHU_KEY_VAULT_NAME','ju-ai-search-kv-prod')
    refs=SecretReferences('ju-ai-search-vpn-username-prod','ju-ai-search-vpn-password-prod',
                         'ju-ai-search-jhu-api-username-prod','ju-ai-search-jhu-api-password-prod')
    from urllib.parse import urlsplit
    url=urlsplit(local.JHU_LLM_ENDPOINT)
    def payload():
        with key_vault_resolver(vault,refs) as resolver: credentials=resolver.vpn_credentials()
        return dict(profile=profile,vpn_username=credentials.username,vpn_password=credentials.password,
                    target_ip=url.hostname,target_port=url.port or 80)
    public=dict(APP_ENV='local',TENANT_ID='jhu',JHU_CONNECTION_MODE='managed',
        JHU_LLM_ENDPOINT=local.JHU_LLM_ENDPOINT,JHU_LLM_ALLOW_HTTP=True,
        JHU_LLM_USERNAME=None,JHU_LLM_PASSWORD=None,JHU_KEY_VAULT_NAME=vault,
        JHU_API_USERNAME_SECRET=refs.api_username,JHU_API_PASSWORD_SECRET=refs.api_password,
        JHU_HELPER_WORKSPACE=str(owner_root))
    for key,value in public.items(): monkeypatch.setattr(settings,key,value)
    fingerprint=hashlib.sha256(profile.encode()).hexdigest()
    report={}
    def emit(stage): print(json.dumps({'stage':stage}),flush=True)
    def start():
        manager.start(fingerprint,payload)
        assert manager.wait_ready()['state']=='ready'
    async def health():
        conn=await embedding_connection()
        async with jhu_client(conn,httpx.Timeout(3),require_ready=False) as client:
            response=await client.get(conn['endpoint']+'/_jhu/health',timeout=3)
            response.raise_for_status()
            return response.json()
    def sample():
        code="""import json,pathlib
p=pathlib.Path('/sys/fs/cgroup')
if (p/'cpu.stat').exists() and (p/'memory.current').exists():
 cpu=int(dict(line.split() for line in (p/'cpu.stat').read_text().splitlines())['usage_usec'])
 mem=int((p/'memory.current').read_text()); peak=int((p/'memory.peak').read_text())
else:
 cpu=int((p/'cpuacct/cpuacct.usage').read_text())//1000
 mem=int((p/'memory/memory.usage_in_bytes').read_text());peak=int((p/'memory/memory.max_usage_in_bytes').read_text())
print(json.dumps(dict(cpu_usec=cpu,memory_bytes=mem,peak_bytes=peak)))"""
        return json.loads(manager.docker(['exec',manager.inspect()['id'],'python','-c',code]).stdout)
    async def exercise():
        original_client=httpx.AsyncClient
        async def diagnose(response):
            if response.request.url.path!='/api/generate': return
            await response.aread()
            try: body=response.json()
            except ValueError: body={}
            answer=body.get('response') if isinstance(body,dict) else None
            if response.status_code!=200 or not isinstance(answer,str) or not answer.strip():
                reason=body.get('done_reason') if isinstance(body,dict) else None
                print(json.dumps(dict(stage='generation_response_diagnostic',status=response.status_code,
                    answer_chars=len(answer) if isinstance(answer,str) else None,
                    done_reason=reason if reason in ('stop','length') else 'other')),flush=True)
        monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original_client(**kwargs,event_hooks={'response':[diagnose]}))
        found=(await discover_models())['models']
        row=next(m for m in found if m['name']=='llama3.2:3b')
        _,llm=make_profile('jhu',row)
        provider=ProfileLLMProvider(llm.model_copy(update={'max_output_tokens':512}))
        assert len(await OllamaEmbeddingProvider(embedding_entry('jhu','jhu-nomic')).embed_query('Univerzitní knihovna'))==768
        before=(await health())['forwarded']['/api/generate']
        pending=asyncio.create_task(provider.generate([ChatMessage(role='user',content=
            'Napiš velmi podrobný český text o fungování univerzity ve třiceti odstavcích.')]))
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if (await health())['forwarded']['/api/generate']>before: break
            assert not pending.done(), 'Generation ended before fault injection'
            await asyncio.sleep(.05)
        else: raise AssertionError('No submitted generation observed')
        with pytest.raises(ModelError) as busy:
            await provider.generate([ChatMessage(role='user',content='Souběžná varianta porovnání')])
        assert busy.value.code=='model_busy'
        identifier=manager.inspect()['id']
        kill="import os,signal,pathlib; p=[int(x.name) for x in pathlib.Path('/proc').iterdir() if x.name.isdigit() and (x/'comm').exists() and (x/'comm').read_text().strip()=='openvpn']; assert len(p)==1; os.kill(p[0],signal.SIGTERM)"
        started=time.monotonic()
        await asyncio.to_thread(manager.docker,['exec',identifier,'python','-c',kill])
        with pytest.raises(ModelError) as failed: await asyncio.wait_for(pending,15)
        assert failed.value.code=='jhu_connection_unavailable'
        report['interrupted_generation_ms']=round(1000*(time.monotonic()-started))
        assert (await health())['forwarded']['/api/generate']==before+1
        emit('interrupted_once')
        recovered=await asyncio.to_thread(manager.wait_ready,90,1)
        assert recovered['state']=='ready' and recovered['generation']==2
        report['recovery_ms']=round(1000*(time.monotonic()-started))
        try:
            assert await provider.generate([ChatMessage(role='user',content='Napiš jednu českou větu o knihovně.')],max_tokens=100)
        except ModelError as error:
            print(json.dumps({'stage':'recovered_generation_failed','code':error.code,
                'diagnostics':provider.diagnostics}),flush=True)
            raise
        emit('next_question_recovered')
        # Explicit helper replacement: stale backend snapshot cannot generate.
        await asyncio.to_thread(manager.stop);await asyncio.to_thread(start)
        assert (await connection_status())['state']=='degraded'
        assert (await refresh_connection())['state']=='ready'
        assert await provider.generate([ChatMessage(role='user',content='Napiš jednu českou větu o studiu.')],max_tokens=100)
        emit('explicit_helper_refresh')
        if os.getenv('RUN_JHU_DOCKER_RESTART_TESTS')=='1':
            started=time.monotonic()
            await asyncio.to_thread(restart_rancher)
            assert (await connection_status())['state']=='degraded'
            await asyncio.to_thread(manager.stop)
            await asyncio.to_thread(start)
            assert (await refresh_connection())['state']=='ready'
            assert await provider.generate([ChatMessage(role='user',content='Napiš jednu českou větu o univerzitě.')],max_tokens=100)
            report['docker_restart_recovery_s']=round(time.monotonic()-started,1)
            emit('docker_restart_recovered')
        baseline=await asyncio.to_thread(sample)
        initial=await health();latencies=[];started=time.monotonic()
        emit('soak_started')
        while time.monotonic()-started<soak:
            status=await connection_status()
            assert status['state']=='ready'
            latencies.append(status['health_ms'])
            conn=await embedding_connection()
            async with jhu_client(conn,httpx.Timeout(10)) as client:
                response=await client.get(conn['endpoint']+'/api/tags');response.raise_for_status()
            await asyncio.sleep(15)
        final=await health();resources=await asyncio.to_thread(sample)
        print(json.dumps(dict(stage='soak_finished',initial_generation=initial['generation'],
            generation=final['generation'],code=final.get('code'),tls_channels=final['tls_channels'],
            recovery_causes=final.get('recovery_causes',{}))),flush=True)
        assert final['generation']==initial['generation']==1
        assert final['tls_channels']>initial['tls_channels'], 'No actual rekey observed'
        report.update(soak_seconds=round(time.monotonic()-started),tls_channels=final['tls_channels'],
            health_p50_ms=statistics.median(latencies),health_max_ms=max(latencies),
            helper_peak_bytes=resources['peak_bytes'],helper_memory_bytes=resources['memory_bytes'],
            helper_average_cpu_cores=round((resources['cpu_usec']-baseline['cpu_usec'])/1e6/(time.monotonic()-started),4),
            models=len(found),no_generation_replay=True)
    reset_managed_connection()
    try:
        start();emit('helper_ready');asyncio.run(exercise());print(json.dumps(report),flush=True)
    finally:
        manager.stop();reset_managed_connection()
