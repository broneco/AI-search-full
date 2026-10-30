"""ACA helper bootstrap. No app Settings, Docker, CLI identity or API credentials."""
import ipaddress
import os
import re
import sys
from urllib.parse import urlsplit


class CloudBootstrapError(Exception):
    pass  # Fixed codes only; SDK exceptions and secret values never escape.


def cloud_config(environ=None):
    env = os.environ if environ is None else environ
    names = ('CONTAINER_APP_NAME', 'CONTAINER_APP_REVISION', 'CONTAINER_APP_REPLICA_NAME')
    values = [env.get(name, '') for name in names]
    tenant = env.get('TENANT_ID', '')
    if (sys.platform != 'linux' or env.get('APP_ENV') not in {'dev', 'prod'}
            or env.get('JHU_CONNECTION_MODE') != 'sidecar'
            or tenant.split('-')[0].lower() not in {'ju', 'jhu'}
            or not all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,252}', value) for value in values)
            or values[0] != env.get('JHU_SIDECAR_APP_NAME')
            or not values[1].startswith(values[0]+'--') or not values[2].startswith(values[1]+'-')
            or not env.get('IDENTITY_ENDPOINT') or not env.get('IDENTITY_HEADER')):
        raise CloudBootstrapError('vpn_cloud_runtime_invalid')
    vault = env.get('JHU_KEY_VAULT_NAME', '')
    refs = [env.get(name, '') for name in ('JHU_VPN_USERNAME_SECRET', 'JHU_VPN_PASSWORD_SECRET',
                                         'JHU_VPN_PROFILE_SECRET', 'JHU_GATEWAY_KEY_SECRET')]
    if (not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{1,22}[A-Za-z0-9]', vault)
            or len(set(refs)) != 4 or not all(re.fullmatch(r'[A-Za-z0-9-]{1,127}', ref) for ref in refs)):
        raise CloudBootstrapError('vpn_cloud_reference_invalid')
    try:
        url = urlsplit(env.get('JHU_LLM_ENDPOINT', ''))
        address = ipaddress.IPv4Address(url.hostname or '')
        if (url.scheme != 'http' or url.username or url.password or url.query or url.fragment
                or url.path not in {'', '/'} or not 1 <= (url.port or 0) <= 65535
                or address.is_loopback or address.is_multicast or address.is_unspecified):
            raise ValueError()
    except ValueError:
        raise CloudBootstrapError('vpn_cloud_target_invalid') from None
    return dict(vault=vault, references=refs, target_ip=url.hostname, target_port=url.port,
                context=dict(application=values[0], revision=values[1], replica=values[2],
                             tenant=tenant, target=f'{url.hostname}:{url.port}'))


def load_payload(config):
    # SDK stays isolated in the helper: exactly four named reads, no listing,
    # fallback identity chain, env credential values or hidden SDK retries.
    from azure.identity import ManagedIdentityCredential
    from azure.keyvault.secrets import SecretClient
    try:
        with ManagedIdentityCredential(retry_total=0, connection_timeout=3, read_timeout=3) as credential:
            with SecretClient(vault_url=f"https://{config['vault']}.vault.azure.net", credential=credential,
                              logging_enable=False, retry_total=0, connection_timeout=5, read_timeout=10) as client:
                values = [client.get_secret(ref).value for ref in config['references']]
        if not all(isinstance(value, str) and value for value in values):
            raise ValueError()
        username, password, profile, key = values
        if not re.fullmatch(r'[a-f0-9]{64}', key):
            raise ValueError()
        return dict(vpn_username=username, vpn_password=password, profile=profile,
                    gateway_key=key, target_ip=config['target_ip'], target_port=config['target_port'])
    except Exception:
        raise CloudBootstrapError('vpn_cloud_secrets_unavailable') from None
