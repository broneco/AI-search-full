"""ACA-only fixed loopback contract. Never imports Docker or resolves a URL from a request."""
import ipaddress
import os
import platform
import re
from urllib.parse import urlsplit

from app.providers.jhu_secrets import JHUConnectionError, SidecarAPISecretReferences

ENDPOINT = 'http://127.0.0.1:18081'


def sidecar_context(config, environ=None) -> dict:
    from app.core.tenant_identity import tenant_config_name
    environ = os.environ if environ is None else environ
    if (config.APP_ENV not in {'dev', 'prod'} or tenant_config_name(config.TENANT_ID) != 'jhu'
            or platform.system() != 'Linux'):
        raise JHUConnectionError('jhu_sidecar_aca_only')
    names = ('CONTAINER_APP_NAME', 'CONTAINER_APP_REVISION', 'CONTAINER_APP_REPLICA_NAME')
    values = [environ.get(name, '') for name in names]
    if (not all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,252}', value) for value in values)
            or values[0] != config.JHU_SIDECAR_APP_NAME
            or not values[1].startswith(values[0]+'--')
            or not values[2].startswith(values[1]+'-')
            or not environ.get('IDENTITY_ENDPOINT') or not environ.get('IDENTITY_HEADER')):
        raise JHUConnectionError('jhu_sidecar_runtime_invalid')
    try:
        url = urlsplit(config.JHU_LLM_ENDPOINT or '')
        address = ipaddress.IPv4Address(url.hostname or '')
        if (url.scheme != 'http' or url.username or url.password or url.query or url.fragment
                or url.path not in {'', '/'} or not 1 <= (url.port or 0) <= 65535
                or not config.JHU_LLM_ALLOW_HTTP
                or address.is_loopback or address.is_multicast or address.is_unspecified):
            raise ValueError()
    except ValueError:
        raise JHUConnectionError('jhu_endpoint_invalid') from None
    if not config.JHU_KEY_VAULT_NAME:
        raise JHUConnectionError('jhu_secret_reference_missing')
    SidecarAPISecretReferences(config.JHU_API_USERNAME_SECRET, config.JHU_API_PASSWORD_SECRET,
                              config.JHU_GATEWAY_KEY_SECRET)
    return dict(application=values[0], revision=values[1], replica=values[2],
                tenant=config.TENANT_ID, target=f'{url.hostname}:{url.port}')
