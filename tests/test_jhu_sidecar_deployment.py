"""No real Azure writes: target, state, budget, session and secret-preservation guards."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from scripts.deployment.jhu_sidecar import (AzureClient, DeploymentError, Options, SECRET_FIELDS,
                                          apply_plan, build_plan, env_values, fingerprint)


@pytest.fixture
def deployment():
    options=Options(subscription='sub',azure_tenant='directory',resource_group='test-rg',app='test-app',
        tenant='ju-prod',sql_host='test.database.windows.net',sql_database='test-db',vault='test-vault',
        target_endpoint='http://192.0.2.1:11434',revision_suffix='test-next',
        backend_image='registry.azurecr.io/backend@sha256:'+'a'*64,
        helper_image='registry.azurecr.io/helper@sha256:'+'b'*64,verified_model='synthetic:latest',app_version='v0.1.7')
    environment=dict(APP_ENV='prod',DATABASE_BACKEND='azure_sql',TENANT_ID='ju-prod',
        AZURE_SQL_HOST=options.sql_host,AZURE_SQL_DB=options.sql_database,AZURE_KEY_VAULT_NAME=options.vault,
        JWT_SECRET='PRIVATE-JWT',JHU_LLM_PASSWORD='PRIVATE-LEGACY',OTHER_SETTING='preserve-me')
    current=dict(id='/subscriptions/sub/resourceGroups/test-rg/providers/Microsoft.App/containerApps/test-app',
        location='swedencentral',identity=dict(type='SystemAssigned',principalId='principal'),etag='old-etag',
        properties=dict(latestReadyRevisionName='test-app--old',environmentId='existing-env',
            configuration=dict(activeRevisionsMode='Single',ingress=dict(external=True,targetPort=8000),secrets=[dict(name='registry-secret')]),
            template=dict(containers=[dict(name='backend',image='registry.azurecr.io/backend:old',
                resources=dict(cpu=.5,memory='1Gi',ephemeralStorage='2Gi'),
                env=[dict(name=key,value=value) for key,value in environment.items()])],
                scale=dict(minReplicas=1,maxReplicas=3,rules=[dict(name='private-rule',
                    custom=dict(type='test',metadata=dict(private='PRIVATE-SCALE')))]))))
    account=dict(id='sub',tenantId='directory')
    metadata=[dict(name=name,enabled=True) for name in SECRET_FIELDS.values()]
    return current,account,metadata,options


def test_plan_is_redacted_preserves_credentials_and_only_adds_sidecar(deployment):
    current,account,metadata,options=deployment;before=deepcopy(current)
    plan=build_plan(*deployment)
    assert current==before and plan.public['blockers']==[]
    assert 'PRIVATE' not in json.dumps(plan.public) and 'PRIVATE' not in repr(plan)
    backend,helper=plan.template['containers']
    assert env_values(backend)['JWT_SECRET']=='PRIVATE-JWT'
    assert env_values(backend)['OTHER_SETTING']=='preserve-me'
    assert 'JHU_LLM_PASSWORD' not in env_values(backend)
    assert env_values(backend)['WEB_CONCURRENCY']=='1'
    assert env_values(backend)['APP_VERSION']=='v0.1.7'
    assert env_values(backend)['AZURE_OPENAI_THINKING_DEPLOYMENT']==''
    assert 'JHU_API_PASSWORD_SECRET' not in env_values(helper)
    assert 'JHU_VPN_PASSWORD_SECRET' not in env_values(backend)
    assert all(probe['tcpSocket']['port']==18082 for probe in helper['probes'])
    assert plan.public['resources']['proposed_cpu']=='0.75'
    assert plan.public['resources']['proposed_memory_gib']=='1.5'
    assert plan.public['resources']['change_requires_confirmation'] is True
    assert plan.template['scale']['rules']==current['properties']['template']['scale']['rules']
    assert plan.template['scale']['maxReplicas']==1


@pytest.mark.parametrize('mutation,code',[
    (lambda app:app['identity'].update(type='None'),'existing_managed_identity_required'),
    (lambda app:app['properties']['configuration'].update(activeRevisionsMode='Multiple'),'single_revision_mode_required'),
    (lambda app:app['properties']['configuration']['ingress'].update(targetPort=18081),'backend_ingress_mismatch'),
    (lambda app:app['properties']['configuration']['ingress'].update(additionalPortMappings=[dict(targetPort=18082)]),
     'helper_port_ingress_forbidden'),
    (lambda app:app['properties']['template'].update(initContainers=[dict(name='unknown')]),'unreviewed_init_containers'),
])
def test_unsafe_topology_is_rejected_before_any_write(deployment,mutation,code):
    mutation(deployment[0])
    with pytest.raises(DeploymentError,match=code):build_plan(*deployment)


def test_account_tenant_database_and_vault_targets_are_exact(deployment):
    current,account,metadata,options=deployment
    for field,value in [('azure_tenant','other'),('subscription','other'),('tenant','jhu'),
                        ('sql_database','other'),('vault','other-vault')]:
        with pytest.raises(DeploymentError):build_plan(current,account,metadata,replace(options,**{field:value}))


def test_missing_secrets_and_mutable_images_are_explicit_plan_blockers(deployment):
    current,account,metadata,options=deployment
    options=replace(options,backend_image=None,helper_image='registry.azurecr.io/helper:latest')
    plan=build_plan(current,account,metadata[:-1],options)
    assert plan.public['blockers']==['backend_immutable_image_required','helper_immutable_image_required',
                                   'secret_missing_or_disabled:'+metadata[-1]['name']]


def apply_args(plan):
    return dict(expected_fingerprint=plan.public['fingerprint'],expected_revision=plan.public['previous_revision'],
                migrations_confirmed=True,resources_confirmed=True,session_policy_confirmed=True,models_confirmed=True)


@pytest.mark.parametrize('field,value,code',[
    ('expected_fingerprint','wrong','reviewed_target_required'),
    ('expected_revision','wrong','reviewed_target_required'),
    ('resources_confirmed',False,'resource_change_confirmation_required'),
    ('migrations_confirmed',False,'operator_confirmation_required'),
    ('session_policy_confirmed',False,'operator_confirmation_required'),
    ('models_confirmed',False,'operator_confirmation_required'),
])
def test_apply_requires_reviewed_target_budget_and_session_scope(deployment,field,value,code):
    plan=build_plan(*deployment);calls=[]
    client=SimpleNamespace(verify_image=lambda _:calls.append('image'))
    args=apply_args(plan);args[field]=value
    with pytest.raises(DeploymentError,match=code):apply_plan(client,plan,deployment[-1],**args)
    assert calls==[]


def test_concurrent_configuration_change_refuses_apply_and_no_replay(deployment):
    current,_,_,options=deployment;plan=build_plan(*deployment);changed=deepcopy(current)
    changed['properties']['template']['scale']['maxReplicas']=2
    client=SimpleNamespace(verify_image=lambda _:None,read_app=lambda:changed,
        patch_template=lambda *_:pytest.fail('Do not overwrite a concurrent change'))
    with pytest.raises(DeploymentError,match='application_changed_since_plan'):
        apply_plan(client,plan,options,**apply_args(plan))


def test_successful_apply_only_submits_template_and_preserves_existing_identity_secrets(deployment):
    current,_,_,options=deployment;plan=build_plan(*deployment);writes=[]
    client=SimpleNamespace(verify_image=lambda _:None,read_app=lambda:current,
                           patch_template=lambda *args:writes.append(args))
    result=apply_plan(client,plan,options,**apply_args(plan))
    assert result['mode']=='apply-requested' and result['acceptance']=='pending_cloud_functional_tests'
    assert len(writes)==1 and writes[0]==(plan.template,'old-etag','swedencentral')
    assert 'configuration' not in plan.template and 'identity' not in plan.template
    assert fingerprint(current)==plan.public['fingerprint']


def test_existing_sidecar_upgrade_requires_revision_session_overlap_review(deployment):
    current,account,metadata,options=deployment
    original=build_plan(*deployment)
    current['properties']['template']=original.template
    plan=build_plan(current,account,metadata,options)
    with pytest.raises(DeploymentError,match='revision_session_overlap_unreviewed'):
        apply_plan(SimpleNamespace(),plan,options,**apply_args(plan))


def test_arm_patch_is_in_memory_verified_and_never_copies_app_configuration(deployment,monkeypatch):
    import azure.identity
    import httpx
    options=deployment[-1];requests=[]
    class Credential:
        def __init__(self,**_):pass
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def get_token(self,scope):
            assert scope=='https://management.azure.com/.default';return SimpleNamespace(token='PRIVATE-TOKEN')
    monkeypatch.setattr(azure.identity,'AzureCliCredential',Credential)
    original=httpx.Client
    def handler(request):
        requests.append(request);return httpx.Response(202)
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(handler)))
    client=AzureClient(options)
    monkeypatch.setattr(client,'az',lambda *_:pytest.fail('No subprocess receives ARM body/token'))
    client.patch_template({'containers':[]},'etag','swedencentral')
    assert len(requests)==1 and requests[0].headers['If-Match']=='etag'
    assert json.loads(requests[0].content)==dict(location='swedencentral',properties=dict(template={'containers':[]}))


def test_windows_cli_launcher_uses_utf8_and_only_reads_account_ids(deployment,monkeypatch):
    import scripts.deployment.jhu_sidecar as module
    calls=[]
    monkeypatch.setattr(module.shutil,'which',lambda _:r'C:\Azure\az.cmd')
    def run(args,**kwargs):
        calls.append(args)
        assert kwargs['env']['PYTHONIOENCODING']=='utf-8'
        assert kwargs['capture_output'] and kwargs['timeout']==60
        return SimpleNamespace(returncode=0,stdout=b'{"id":"sub","tenantId":"directory"}')
    monkeypatch.setattr(module.subprocess,'run',run)
    assert AzureClient(deployment[-1]).account()==dict(id='sub',tenantId='directory')
    assert calls[0][0].endswith('az.cmd')
    assert calls[0][1:5]==['account','show','--query','{id:id,tenantId:tenantId}']


@pytest.mark.parametrize('field,value',[('app','test&whoami'),('vault','test%PATH%vault'),
                                      ('subscription','sub|whoami'),('resource_group','rg;whoami')])
def test_cli_targets_reject_shell_syntax_before_subprocess(deployment,field,value):
    with pytest.raises(DeploymentError,match='azure_target_name_invalid'):
        AzureClient(replace(deployment[-1],**{field:value}))


def test_cli_defaults_to_plan_and_checks_account_before_app(deployment,monkeypatch,capsys):
    import deploy_jhu_sidecar as cli
    current,account,metadata,options=deployment
    monkeypatch.setattr(cli,'AzureClient',lambda _:SimpleNamespace(account=lambda:account,
        read_app=lambda:current,secret_metadata=lambda:metadata))
    args=['deploy_jhu_sidecar.py']
    for key,value in vars(options).items():
        if value is not None:args.extend(['--'+key.replace('_','-'),str(value)])
    monkeypatch.setattr('sys.argv',args)
    assert cli.main()==0
    assert json.loads(capsys.readouterr().out)['mode']=='plan'
    account['tenantId']='other'
    monkeypatch.setattr(cli,'AzureClient',lambda _:SimpleNamespace(account=lambda:account,
        read_app=lambda:pytest.fail('Account must be checked first')))
    assert cli.main()==1
    assert json.loads(capsys.readouterr().out)==dict(code='azure_account_mismatch')


def test_arm_failure_is_redacted_and_not_retried(deployment,monkeypatch):
    import azure.identity
    import httpx
    calls=[]
    class Credential:
        def __init__(self,**_):pass
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def get_token(self,_):return SimpleNamespace(token='synthetic')
    monkeypatch.setattr(azure.identity,'AzureCliCredential',Credential)
    original=httpx.Client
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('PRIVATE response payload',request=request)
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(handler)))
    with pytest.raises(DeploymentError,match='^arm_template_update_failed$'):
        AzureClient(deployment[-1]).patch_template({},None,'swedencentral')
    assert len(calls)==1
