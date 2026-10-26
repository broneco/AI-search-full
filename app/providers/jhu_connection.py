"""Shared connection guard and process-wide budget for JHU model operations."""
import asyncio
import platform
import math
import re
import threading
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.core.model_config import ModelError

slots = threading.BoundedSemaphore(1)


@lru_cache(maxsize=1)
def verified_ssl_context():
    # Cache immutable TLS configuration only, never an event-loop-bound client.
    # Use precisely HTTPX's verified trust_env=False defaults.
    return httpx.create_ssl_context(verify=True, trust_env=False)


def jhu_configured() -> tuple[bool, str | None]:
    if settings.JHU_CONNECTION_MODE == 'managed':
        from app.providers.jhu_managed import validate_managed_config, managed_failure
        from app.providers.jhu_secrets import JHUConnectionError
        try:
            validate_managed_config()
            reason = managed_failure()
            return reason is None, reason
        except JHUConnectionError as exc:
            return False, exc.code
    if not (settings.JHU_LLM_ENDPOINT and settings.JHU_LLM_USERNAME and settings.JHU_LLM_PASSWORD):
        return False, 'not_configured'
    url = urlsplit(settings.JHU_LLM_ENDPOINT)
    if (not url.hostname or url.scheme not in {'http', 'https'} or url.username or url.password
            or url.query or url.fragment or url.path not in {'', '/'}):
        return False, 'invalid_connection'
    if url.scheme == 'http' and not settings.JHU_LLM_ALLOW_HTTP:
        return False, 'secure_connection_required'
    return True, None


async def embedding_connection() -> dict[str, str]:
    if settings.JHU_CONNECTION_MODE == 'managed':
        from app.providers.jhu_managed import managed_connection
        from app.providers.jhu_secrets import JHUConnectionError
        try:
            conn = await asyncio.to_thread(managed_connection)
            return dict(endpoint=conn.endpoint, username=conn.credentials.username,
                        password=conn.credentials.password, gateway_key=conn.key)
        except JHUConnectionError as exc:
            raise ModelError(exc.code, 'Spravované připojení JHU není dostupné. Ověřte helper a Key Vault.', 503) from None
    endpoint = settings.JHU_LLM_ENDPOINT
    if not (endpoint and settings.JHU_LLM_USERNAME and settings.JHU_LLM_PASSWORD):
        raise ModelError("embedding_not_configured", "Doplňte připojení k JHU modelové službě.")
    url = urlsplit(endpoint)
    if (not url.hostname or url.scheme not in {"http", "https"} or url.username or url.password
            or url.query or url.fragment or url.path not in {"", "/"}):
        raise ModelError("embedding_connection_invalid", "Připojení k embeddingové službě není platné.")
    if url.scheme == "http":
        if not settings.JHU_LLM_ALLOW_HTTP:
            raise ModelError("embedding_secure_connection_required", "HTTP připojení není povolené.")
        if settings.APP_ENV == "local":
            if platform.system() != "Windows":
                raise ModelError("model_vpn_required", "Lokální HTTP test vyžaduje ověřenou Windows VPN trasu.")
            from app.providers.vpn import verify_windows_vpn
            await asyncio.to_thread(verify_windows_vpn, url.hostname, settings.JHU_LLM_VPN_INTERFACE)
    return dict(endpoint=endpoint.rstrip("/"), username=settings.JHU_LLM_USERNAME, password=settings.JHU_LLM_PASSWORD)


@asynccontextmanager
async def jhu_client(connection: dict, timeout, limits=None, *, require_ready=True):
    headers = {'X-JHU-Connection': connection['gateway_key']} if 'gateway_key' in connection else {}
    options = dict(timeout=timeout, trust_env=False, follow_redirects=False,
                   auth=httpx.BasicAuth(connection['username'], connection['password']), headers=headers,
                   verify=verified_ssl_context())
    if limits is not None:
        options['limits'] = limits
    async with httpx.AsyncClient(**options) as client:
        if headers and require_ready:
            status = await helper_health(client, connection)
            if status['state'] != 'ready':
                raise ModelError('jhu_connection_unavailable', 'JHU spojení není připravené. Dotaz zkuste po obnovení spojení.', 503)
        try:
            yield client
        except httpx.HTTPStatusError as exc:
            if headers and exc.response.headers.get('X-JHU-Gateway-Error') == 'connection_unavailable':
                raise ModelError('jhu_connection_unavailable', 'JHU spojení bylo přerušeno. Po obnovení odešlete nový dotaz.', 503) from None
            raise
        except httpx.TransportError as exc:
            if headers and not isinstance(exc, httpx.TimeoutException):
                raise ModelError('jhu_connection_unavailable', 'JHU spojení bylo přerušeno. Po obnovení odešlete nový dotaz.', 503) from None
            raise


async def helper_health(client, connection) -> dict:
    """Whitelist operational metadata. Never return upstream paths or secrets."""
    try:
        response = await client.get(connection['endpoint'] + '/_jhu/health', timeout=3)
        response.raise_for_status()
        body = response.json()
        if (not isinstance(body, dict) or body.get('protocol_version') != 2
                or body.get('state') not in {'disabled', 'connecting', 'ready', 'degraded', 'auth_failed'}):
            raise ValueError()
        age = time.time() - float(body['updated_at'])
        if not math.isfinite(age) or age < 0:
            raise ValueError()
        code = body.get('code')
        if code is not None and (not isinstance(code, str) or not re.fullmatch(r'vpn_[a-z_]{1,60}', code)):
            raise ValueError()
        result = dict(state=body['state'], code=code)
        for name in ('attempts', 'generation', 'tls_channels'):
            value = body.get(name, 0)
            if type(value) is not int or value < 0:
                raise ValueError()
            result[name] = value
        if age > 30 and result['state'] == 'ready':
            result.update(state='degraded', code='vpn_status_stale')
        return result
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise ModelError('jhu_connection_unavailable', 'JHU spojení není připravené. Ověřte helper nebo obnovte připojení.', 503) from None


async def connection_status() -> dict:
    if settings.JHU_CONNECTION_MODE != 'managed':
        return dict(mode='direct', state='disabled', code='jhu_managed_disabled')
    started = time.monotonic()
    try:
        connection = await embedding_connection()
        async with jhu_client(connection, httpx.Timeout(3), require_ready=False) as client:
            result = await helper_health(client, connection)
        return dict(mode='managed', **result, health_ms=round(1000 * (time.monotonic() - started)))
    except ModelError as exc:
        return dict(mode='managed', state='degraded', code=exc.code)


async def refresh_connection() -> dict:
    from app.providers.jhu_managed import refresh_managed_connection
    from app.providers.jhu_secrets import JHUConnectionError
    if settings.JHU_CONNECTION_MODE != 'managed':
        raise ModelError('jhu_managed_disabled', 'Spravované připojení není zapnuté.', 409)
    if not slots.acquire(blocking=False):
        raise ModelError('model_busy', 'JHU služba právě zpracovává požadavek. Obnovte připojení po dokončení.', 429)
    worker = asyncio.create_task(asyncio.to_thread(refresh_managed_connection))
    def release_when_finished(task):
        try:
            if not task.cancelled():
                task.exception()  # Consume a failure even if the caller disconnected.
        finally:
            slots.release()
    worker.add_done_callback(release_when_finished)
    try:
        await asyncio.shield(worker)
        return await connection_status()
    except JHUConnectionError as exc:
        raise ModelError(exc.code, 'Připojení se nepodařilo obnovit. Předchozí snapshot nebyl přepsán.', 503) from None
