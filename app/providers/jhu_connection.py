"""Shared connection guard and process-wide budget for JHU model operations."""
import asyncio
import platform
import threading
from urllib.parse import urlsplit

from app.core.config import settings
from app.core.model_config import ModelError

slots = threading.BoundedSemaphore(1)


async def embedding_connection() -> dict[str, str]:
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
