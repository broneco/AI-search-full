"""Guarded existing-ACA sidecar rollout; public plans never contain env values."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
import os
import re
import subprocess
import shutil
from urllib.parse import quote, urlsplit
import ipaddress

HELPER = 'jhu-vpn'
SECRET_FIELDS = dict(JHU_VPN_USERNAME_SECRET='ju-ai-search-vpn-username-prod',
    JHU_VPN_PASSWORD_SECRET='ju-ai-search-vpn-password-prod',
    JHU_VPN_PROFILE_SECRET='ju-ai-search-vpn-client-config-prod',
    JHU_API_USERNAME_SECRET='ju-ai-search-jhu-api-username-prod',
    JHU_API_PASSWORD_SECRET='ju-ai-search-jhu-api-password-prod',
    JHU_GATEWAY_KEY_SECRET='ju-ai-search-jhu-gateway-key-prod')


class DeploymentError(Exception):
    pass  # Fixed operational codes; never raw ARM or credential exceptions.


@dataclass(frozen=True)
class Options:
    subscription: str
    azure_tenant: str
    resource_group: str
    app: str
    tenant: str
    sql_host: str
    sql_database: str
    vault: str
    target_endpoint: str
    revision_suffix: str
    backend_image: str | None = None
    helper_image: str | None = None
    backend_cpu: float | None = None
    backend_memory: str | None = None
    helper_cpu: float = .25
    helper_memory: str = '0.5Gi'
    verified_model: str | None = None
    app_version: str | None = None
    advanced_model_deployment: str | None = None


def fingerprint(app: dict) -> str:
    fields={key:app.get(key) for key in ('id','identity','location')}
    fields['properties']={key:app['properties'].get(key) for key in
        ('template','configuration','environmentId','managedEnvironmentId','latestReadyRevisionName')}
    return hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def env_values(container: dict) -> dict:
    entries=container.get('env',[])
    names=[entry['name'] for entry in entries]
    if len(names)!=len(set(names)):raise DeploymentError('duplicate_runtime_environment')
    return {entry['name']:entry.get('value') for entry in entries}


def replace_env(container: dict, updates: dict, remove: tuple = ()) -> None:
    container['env']=[entry for entry in container.get('env',[])
                      if entry['name'] not in updates and entry['name'] not in remove]
    container['env'].extend(dict(name=name,value=value) for name,value in updates.items())


def immutable_image(value: str | None, registry: str) -> bool:
    if not value:return False
    prefix=registry+'/'
    if not value.startswith(prefix):return False
    tail=value[len(prefix):]
    if not re.fullmatch(r'[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}',tail):return False
    return all(part not in {'.','..',''} for part in tail.split('@')[0].split('/'))


@dataclass
class Plan:
    public: dict
    template: dict = field(repr=False)
    etag: str | None = field(default=None,repr=False)


def build_plan(current: dict, account: dict, metadata: list[dict], options: Options) -> Plan:
    validate_cli_targets(options)
    if account.get('id')!=options.subscription or account.get('tenantId')!=options.azure_tenant:
        raise DeploymentError('azure_account_mismatch')
    expected=f'/subscriptions/{options.subscription}/resourceGroups/{options.resource_group}/providers/Microsoft.App/containerApps/{options.app}'
    if current.get('id','').lower()!=expected.lower():raise DeploymentError('app_target_mismatch')
    if options.tenant.split('-')[0].lower() not in {'ju','jhu'}:raise DeploymentError('jhu_tenant_required')
    try:
        target=urlsplit(options.target_endpoint)
        address=ipaddress.IPv4Address(target.hostname or '')
        if (target.scheme!='http' or target.username or target.password or target.query or target.fragment
                or target.path not in {'','/'} or not 1 <= (target.port or 0) <= 65535
                or address.is_loopback or address.is_multicast or address.is_unspecified):raise ValueError()
    except ValueError:raise DeploymentError('jhu_target_invalid') from None
    if (not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',options.revision_suffix)
            or '--' in options.revision_suffix or options.revision_suffix.endswith('-')
            or len(options.app)+2+len(options.revision_suffix)>64):
        raise DeploymentError('revision_suffix_invalid')
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]',options.vault):
        raise DeploymentError('vault_name_invalid')
    properties=current['properties'];original=properties['template']
    if properties.get('configuration',{}).get('activeRevisionsMode')!='Single':
        raise DeploymentError('single_revision_mode_required')
    containers=original.get('containers',[])
    backends=[container for container in containers if container['name']!=HELPER]
    if len(backends)!=1 or len(containers) not in (1,2):raise DeploymentError('unreviewed_container_topology')
    backend=deepcopy(backends[0]);runtime=env_values(backend)
    if backend.get('command') or backend.get('args'):raise DeploymentError('unreviewed_backend_entrypoint')
    expected_runtime=dict(TENANT_ID=options.tenant,AZURE_SQL_HOST=options.sql_host,AZURE_SQL_DB=options.sql_database)
    if any(runtime.get(name)!=value for name,value in expected_runtime.items()):
        raise DeploymentError('runtime_database_or_tenant_mismatch')
    if runtime.get('APP_ENV') not in {'dev','prod'} or runtime.get('DATABASE_BACKEND')!='azure_sql':
        raise DeploymentError('cloud_runtime_required')
    if runtime.get('AZURE_KEY_VAULT_NAME')!=options.vault:raise DeploymentError('existing_vault_mismatch')
    if 'SystemAssigned' not in current.get('identity',{}).get('type','') or not current['identity'].get('principalId'):
        raise DeploymentError('existing_managed_identity_required')
    if properties.get('configuration',{}).get('ingress',{}).get('targetPort')!=8000:
        raise DeploymentError('backend_ingress_mismatch')
    ingress=properties['configuration']['ingress']
    if any(entry.get('targetPort') in {18080,18081,18082}
           for entry in ingress.get('additionalPortMappings',[]) or []):
        raise DeploymentError('helper_port_ingress_forbidden')
    if original.get('initContainers'):raise DeploymentError('unreviewed_init_containers')
    registry=backends[0]['image'].split('/')[0]
    if not registry.endswith('.azurecr.io'):raise DeploymentError('existing_acr_required')
    blockers=[]
    if not options.verified_model or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}',options.verified_model):
        blockers.append('verified_model_configuration_required')
    if not options.app_version or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+',options.app_version):
        blockers.append('runtime_version_required')
    for name,image in [('backend',options.backend_image),('helper',options.helper_image)]:
        if not immutable_image(image,registry):blockers.append(name+'_immutable_image_required')
    enabled={entry['name'] for entry in metadata if entry.get('enabled') is True}
    blockers.extend('secret_missing_or_disabled:'+name for name in SECRET_FIELDS.values() if name not in enabled)
    common=dict(APP_ENV=runtime['APP_ENV'],TENANT_ID=options.tenant,JHU_CONNECTION_MODE='sidecar',
                JHU_SIDECAR_APP_NAME=options.app,JHU_KEY_VAULT_NAME=options.vault,
                JHU_LLM_ENDPOINT=f'http://{target.hostname}:{target.port}',JHU_LLM_ALLOW_HTTP='true',
                JHU_GATEWAY_KEY_SECRET=SECRET_FIELDS['JHU_GATEWAY_KEY_SECRET'])
    backend_updates={**common,**{key:SECRET_FIELDS[key] for key in ('JHU_API_USERNAME_SECRET','JHU_API_PASSWORD_SECRET')},
                     'JHU_LLM_VERIFIED_MODEL':options.verified_model or '',
                     'APP_VERSION':options.app_version or '', 'WEB_CONCURRENCY':'1',
                     'AZURE_OPENAI_THINKING_DEPLOYMENT':options.advanced_model_deployment or ''}
    remove=('JHU_LLM_USERNAME','JHU_LLM_PASSWORD','AZURE_KEY_VAULT_SECRET_JHU_LLM_USERNAME',
            'AZURE_KEY_VAULT_SECRET_JHU_LLM_PASSWORD','JHU_HELPER_WORKSPACE')
    replace_env(backend,backend_updates,remove)
    previous_resources=deepcopy(backend['resources'])
    backend['resources']={key:value for key,value in backend['resources'].items() if key!='ephemeralStorage'}
    if options.backend_cpu is not None:backend['resources']['cpu']=options.backend_cpu
    if options.backend_memory is not None:backend['resources']['memory']=options.backend_memory
    helper_env={**common,**{key:SECRET_FIELDS[key] for key in
                           ('JHU_VPN_USERNAME_SECRET','JHU_VPN_PASSWORD_SECRET','JHU_VPN_PROFILE_SECRET')}}
    helper=dict(name=HELPER,image=options.helper_image,command=['python','-u','/opt/probe/service.py','cloud'],
        resources=dict(cpu=options.helper_cpu,memory=options.helper_memory),
        env=[dict(name=key,value=value) for key,value in helper_env.items()],
        probes=[dict(type='Startup',tcpSocket=dict(port=18082),periodSeconds=5,failureThreshold=30),
                dict(type='Liveness',tcpSocket=dict(port=18082),periodSeconds=30,failureThreshold=3)])
    backend['image']=options.backend_image
    try:
        cpu=sum(Decimal(str(item['resources']['cpu'])) for item in (backend,helper))
        memory=sum(Decimal(item['resources']['memory'].removesuffix('Gi')) for item in (backend,helper))
        if (not all(item['resources']['memory'].endswith('Gi') for item in (backend,helper))
                or not Decimal('.25')<=cpu<=Decimal('2') or cpu%Decimal('.25') or memory!=2*cpu
                or any(Decimal(str(item['resources']['cpu']))<=0 for item in (backend,helper))):raise ValueError()
    except Exception:raise DeploymentError('resource_combination_invalid') from None
    template=deepcopy(original)
    template.update(containers=[backend,helper],revisionSuffix=options.revision_suffix)
    template.setdefault('scale',{}).update(minReplicas=1,maxReplicas=1)
    old_cpu=sum(Decimal(str(item['resources']['cpu'])) for item in containers)
    old_memory=sum(Decimal(item['resources']['memory'].removesuffix('Gi')) for item in containers)
    resources_changed=(cpu!=old_cpu or memory!=old_memory
        or backend['resources']['cpu']!=previous_resources['cpu']
        or backend['resources']['memory']!=previous_resources['memory'])
    public=dict(mode='plan',subscription=options.subscription,azure_tenant=options.azure_tenant,
        resource_group=options.resource_group,app=options.app,tenant=options.tenant,
        sql_host=options.sql_host,sql_database=options.sql_database,
        fingerprint=fingerprint(current),previous_revision=properties.get('latestReadyRevisionName'),
        previous_images=[dict(name=item['name'],image=item['image']) for item in containers],
        proposed_images=[dict(name=item['name'],image=item['image']) for item in (backend,helper)],
        resources=dict(previous_cpu=str(old_cpu),previous_memory_gib=str(old_memory),
                       proposed_cpu=str(cpu),proposed_memory_gib=str(memory),change_requires_confirmation=resources_changed),
        scale=dict(previous={key:original.get('scale',{}).get(key) for key in
                             ('minReplicas','maxReplicas','cooldownPeriod','pollingInterval')},
                   proposed={key:template['scale'].get(key) for key in
                             ('minReplicas','maxReplicas','cooldownPeriod','pollingInterval')}),
        location=current['location'],
        runtime_version=options.app_version,
        advanced_model=dict(previous=runtime.get('AZURE_OPENAI_THINKING_DEPLOYMENT'),
                            proposed=options.advanced_model_deployment,
                            state='requires_deployment_verification' if options.advanced_model_deployment else 'not_configured'),
        required_secret_names=list(SECRET_FIELDS.values()),blockers=blockers,
        existing_sidecar=any(item['name']==HELPER for item in containers),
        operator_checks=['model_schema_migrations','GPT_deployments_and_optional_model_availability',
                         'VPN_session_policy_and_local_helper_disconnected','frontend_release_and_rollback'])
    return Plan(public,template,current.get('etag'))


def apply_plan(client: AzureClient, plan: Plan, options: Options, *, expected_fingerprint: str | None,
               expected_revision: str | None, migrations_confirmed: bool, resources_confirmed: bool,
               session_policy_confirmed: bool, models_confirmed: bool,
               overlap_confirmed: bool = False) -> dict:
    if (expected_fingerprint!=plan.public['fingerprint'] or not expected_revision
            or expected_revision!=plan.public['previous_revision']):raise DeploymentError('reviewed_target_required')
    if plan.public['blockers']:raise DeploymentError('plan_has_blockers')
    if not migrations_confirmed or not session_policy_confirmed or not models_confirmed:
        raise DeploymentError('operator_confirmation_required')
    if plan.public['resources']['change_requires_confirmation'] and not resources_confirmed:
        raise DeploymentError('resource_change_confirmation_required')
    if plan.public['existing_sidecar'] and not overlap_confirmed:raise DeploymentError('revision_session_overlap_unreviewed')
    for image in (options.backend_image,options.helper_image):client.verify_image(image)
    if fingerprint(client.read_app())!=expected_fingerprint:raise DeploymentError('application_changed_since_plan')
    client.patch_template(plan.template,plan.etag,plan.public['location'])
    return dict(mode='apply-requested',app=options.app,revision_suffix=options.revision_suffix,
                previous_revision=expected_revision,acceptance='pending_cloud_functional_tests')


class AzureClient:
    def __init__(self,options: Options):
        validate_cli_targets(options)
        self.options=options

    def az(self,*args: str) -> dict | list:
        try:
            executable=shutil.which('az')
            if executable is None:raise ValueError()
            environment={**os.environ,'PYTHONIOENCODING':'utf-8'}
            result=subprocess.run([executable,*args,'--only-show-errors','--output','json'],
                                  capture_output=True,timeout=60,env=environment)
            if result.returncode:raise ValueError()
            return json.loads(result.stdout)
        except Exception:raise DeploymentError('azure_cli_read_failed') from None

    def account(self) -> dict:return self.az('account','show','--query','{id:id,tenantId:tenantId}')

    def read_app(self) -> dict:
        return self.az('containerapp','show','--name',self.options.app,'--resource-group',self.options.resource_group,
                       '--subscription',self.options.subscription)

    def secret_metadata(self) -> list[dict]:
        return self.az('keyvault','secret','list','--vault-name',self.options.vault,
                       '--query','[].{name:name,enabled:attributes.enabled}')

    def verify_image(self,image: str) -> None:
        host,reference=image.split('/',1)
        record=self.az('acr','repository','show','--name',host.split('.')[0],'--image',reference,
                       '--subscription',self.options.subscription,'--query','{digest:digest}')
        if record.get('digest')!=reference.split('@')[1]:raise DeploymentError('registry_digest_mismatch')

    def patch_template(self,template: dict,etag: str | None,location: str) -> None:
        # In-memory ARM body: never put copied runtime env values in command
        # arguments, a generated YAML file or logs. Only template is patched.
        from azure.identity import AzureCliCredential
        import httpx
        op=self.options
        path=(f'/subscriptions/{quote(op.subscription,safe="")}/resourceGroups/{quote(op.resource_group,safe="")}'
              f'/providers/Microsoft.App/containerApps/{quote(op.app,safe="")}')
        try:
            with AzureCliCredential(process_timeout=10) as credential:
                token=credential.get_token('https://management.azure.com/.default').token
            headers={'Authorization':'Bearer '+token}
            if etag:headers['If-Match']=etag
            with httpx.Client(timeout=120,trust_env=False,follow_redirects=False) as client:
                response=client.patch('https://management.azure.com'+path+'?api-version=2025-07-01',
                                      headers=headers,json={'location':location,
                                                           'properties':{'template':template}})
                if response.status_code not in (200,201,202):raise ValueError()
        except Exception:raise DeploymentError('arm_template_update_failed') from None


def validate_cli_targets(options: Options) -> None:
    # Azure CLI is a .cmd launcher on Windows: only canonical resource names
    # reach its argument vector; copied env/secret values never do.
    for value,pattern in ((options.subscription,r'[A-Za-z0-9-]{1,64}'),
                          (options.resource_group,r'[A-Za-z0-9_.-]{1,90}'),
                          (options.app,r'[a-z][a-z0-9-]{1,30}'),
                          (options.vault,r'[A-Za-z][A-Za-z0-9-]{1,22}[A-Za-z0-9]')):
        if not re.fullmatch(pattern,value):raise DeploymentError('azure_target_name_invalid')
