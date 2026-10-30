"""One process snapshot of a verified local/ACA helper and KV API credentials.

No Docker or vault subprocess is launched for each model call. Failure is sticky
until restart/reset, never a reason to fall back to direct HTTP/env credentials.
"""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import subprocess
import threading
from urllib.parse import urlsplit

from app.core.config import settings
from app.core.tenant_identity import tenant_config_name
from app.providers.jhu_secrets import (APISecretReferences, SidecarAPISecretReferences,
                                     CredentialPair, JHUConnectionError, key_vault_resolver)


@dataclass(frozen=True)
class ManagedConnection:
    endpoint: str
    credentials: CredentialPair = field(repr=False)
    key: str = field(repr=False)


_lock = threading.RLock()
_snapshot: ManagedConnection | None = None
_failure: str | None = None
_signature = None


def signature():
    return (settings.APP_ENV, settings.TENANT_ID, settings.JHU_CONNECTION_MODE,
            settings.JHU_LLM_ENDPOINT, settings.JHU_LLM_ALLOW_HTTP,
            settings.JHU_KEY_VAULT_NAME, settings.JHU_API_USERNAME_SECRET,
            settings.JHU_API_PASSWORD_SECRET, settings.JHU_HELPER_WORKSPACE,
            settings.JHU_GATEWAY_KEY_SECRET, settings.JHU_SIDECAR_APP_NAME)


def validate_managed_config() -> None:
    if settings.JHU_CONNECTION_MODE == 'sidecar':
        from app.providers.jhu_sidecar import sidecar_context
        sidecar_context(settings)
        return
    if settings.APP_ENV not in {'local', 'test'} or tenant_config_name(settings.TENANT_ID) != 'jhu':
        raise JHUConnectionError('jhu_managed_local_only')
    try:
        url = urlsplit(settings.JHU_LLM_ENDPOINT or '')
        port = url.port
    except ValueError:
        raise JHUConnectionError('jhu_endpoint_invalid') from None
    if (url.scheme != 'http' or not url.hostname or url.username or url.password or url.query
            or url.fragment or url.path not in {'', '/'} or not settings.JHU_LLM_ALLOW_HTTP
            or port == 0):
        raise JHUConnectionError('jhu_endpoint_invalid')
    if not all((settings.JHU_KEY_VAULT_NAME, settings.JHU_API_USERNAME_SECRET, settings.JHU_API_PASSWORD_SECRET)):
        raise JHUConnectionError('jhu_secret_reference_missing')
    APISecretReferences(settings.JHU_API_USERNAME_SECRET, settings.JHU_API_PASSWORD_SECRET)


def verify_helper() -> tuple[str, str]:
    root = Path(settings.JHU_HELPER_WORKSPACE or Path.cwd()).resolve()
    owner = hashlib.sha256(str(root).casefold().encode()).hexdigest()[:16]
    name = 'ai-search-jhu-' + owner

    def docker(args):
        try:
            result = subprocess.run(['docker', *args], capture_output=True, timeout=10)
            if result.returncode:
                raise JHUConnectionError('jhu_helper_unavailable')
            return result.stdout.decode().strip()
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            raise JHUConnectionError('jhu_helper_unavailable') from None

    try:
        data = json.loads(docker(['inspect', '--format',
            '{"id":{{json .Id}},"running":{{json .State.Running}},"labels":{{json .Config.Labels}},"ports":{{json .NetworkSettings.Ports}}}', name]))
        labels = data['labels']
        url = urlsplit(settings.JHU_LLM_ENDPOINT)
        if (not data['running'] or labels.get('ai-search.owner') != owner
                or labels.get('ai-search.jhu-helper') != 'v1' or labels.get('ai-search.jhu-protocol') != '2'
                or labels.get('ai-search.jhu-target') != f'{url.hostname}:{url.port or 80}'
                or not re.fullmatch(r'[a-f0-9]{64}', data['id'])):
            raise ValueError()
        bindings = data['ports']['18081/tcp']
        if len(bindings) != 1 or bindings[0]['HostIp'] != '127.0.0.1':
            raise ValueError()
        port = int(bindings[0]['HostPort'])
        if not 1 <= port <= 65535:
            raise ValueError()
        key = docker(['exec', data['id'], 'cat', '/run/probe/gateway.key'])
        if not re.fullmatch(r'[a-f0-9]{64}', key):
            raise ValueError()
        return f'http://127.0.0.1:{port}', key
    except (ValueError, KeyError, TypeError, AttributeError):
        raise JHUConnectionError('jhu_helper_mapping_invalid') from None


def reset_managed_connection() -> None:
    global _signature, _snapshot, _failure
    with _lock:
        _signature, _snapshot, _failure = None, None, None


def managed_failure() -> str | None:
    return _failure if _signature == signature() else None


def _load_connection() -> ManagedConnection:
    validate_managed_config()
    if settings.JHU_CONNECTION_MODE == 'sidecar':
        from app.providers.jhu_sidecar import ENDPOINT
        refs = SidecarAPISecretReferences(settings.JHU_API_USERNAME_SECRET, settings.JHU_API_PASSWORD_SECRET,
                                         settings.JHU_GATEWAY_KEY_SECRET)
        with key_vault_resolver(settings.JHU_KEY_VAULT_NAME, refs, 'managed_identity') as resolver:
            credentials, key = resolver.api_credentials(), resolver.gateway_key()
        return ManagedConnection(ENDPOINT, credentials, key)
    endpoint, key = verify_helper()
    refs = APISecretReferences(settings.JHU_API_USERNAME_SECRET, settings.JHU_API_PASSWORD_SECRET)
    with key_vault_resolver(settings.JHU_KEY_VAULT_NAME, refs) as resolver:
        credentials = resolver.api_credentials()
    return ManagedConnection(endpoint, credentials, key)


def refresh_managed_connection() -> None:
    """Explicit control operation. Publish atomically only after all checks pass."""
    global _signature, _snapshot, _failure
    with _lock:
        try:
            candidate = _load_connection()
        except JHUConnectionError:
            raise
        except Exception:
            raise JHUConnectionError('jhu_connection_unavailable') from None
        _signature, _snapshot, _failure = signature(), candidate, None


def managed_connection() -> ManagedConnection:
    global _signature, _snapshot, _failure
    with _lock:
        if _signature != signature():
            _signature, _snapshot, _failure = signature(), None, None
        if _failure:
            raise JHUConnectionError(_failure)
        if _snapshot is not None:
            return _snapshot
        try:
            _snapshot = _load_connection()
            return _snapshot
        except JHUConnectionError as exc:
            _failure = exc.code
            raise
        except Exception:
            _failure = 'jhu_connection_unavailable'
            raise JHUConnectionError(_failure) from None
