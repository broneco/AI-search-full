"""Read-only Ollama inventory. Capabilities are evidence, not model approval."""
import asyncio
from datetime import datetime, timezone
import re
import threading

import httpx

from app.core.model_config import ModelError
from app.providers.jhu_connection import embedding_connection

_scan_slot = threading.BoundedSemaphore(1)
_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,199}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def public_model(tag: dict, metadata: dict) -> dict:
    """Whitelist public metadata; never expose templates, system prompts or paths."""
    capabilities = metadata.get("capabilities")
    if not isinstance(capabilities, list) or any(not isinstance(x, str) for x in capabilities):
        raise ValueError("Invalid capabilities")
    capabilities = sorted(set(capabilities) & {"completion", "embedding", "vision", "audio", "tools", "thinking"})
    details = metadata.get("details") or tag.get("details") or {}
    info = metadata.get("model_info") or {}
    family = details.get("family", "")
    if not isinstance(family, str):
        raise ValueError("Invalid model family")
    # Some community rerankers advertise completion; they are not chat LLMs.
    if "rerank" in tag["name"].casefold():
        kind = "reranker"
    elif "embedding" in capabilities:
        kind = "embedding"
    elif "completion" in capabilities and family not in {"bert", "nomic-bert"}:
        kind = "chat_candidate"
    else:
        kind = "unsupported"
    def integer(key):
        value = info.get(f"{family}.{key}", details.get(key))
        return value if type(value) is int and value > 0 else None
    result = dict(name=tag["name"], digest=tag["digest"], kind=kind, capabilities=capabilities,
                  size_bytes=tag.get("size") if type(tag.get("size")) is int and tag["size"] >= 0 else None,
                  dimensions=integer("embedding_length") if kind == "embedding" else None,
                  context_length=integer("context_length"))
    for key in ("parameter_size", "quantization_level"):
        value = details.get(key)
        result[key] = value if isinstance(value, str) and len(value) <= 40 else None
    return result


async def discover_models() -> dict:
    """No inference, embedding, pull or configuration/database writes."""
    connection = await embedding_connection()  # same Basic auth, URL and VPN guard
    if not _scan_slot.acquire(blocking=False):
        raise ModelError("model_discovery_busy", "Načítání katalogu již probíhá. Zkuste to za chvíli.", 429)
    try:
        async with asyncio.timeout(60):
            async with httpx.AsyncClient(auth=httpx.BasicAuth(connection["username"], connection["password"]),
                    timeout=httpx.Timeout(15, connect=5), trust_env=False, follow_redirects=False,
                    limits=httpx.Limits(max_connections=3)) as client:
                result = await client.get(connection["endpoint"] + "/api/tags")
                result.raise_for_status()
                tags = result.json()["models"]
                if not isinstance(tags, list) or len(tags) > 200:
                    raise ValueError("Invalid or excessive inventory")
                seen = set()
                for tag in tags:
                    if (not isinstance(tag, dict) or not isinstance(tag.get("name"), str)
                            or not _NAME.fullmatch(tag["name"]) or ".." in tag["name"]
                            or not isinstance(tag.get("digest"), str) or not _DIGEST.fullmatch(tag["digest"])
                            or tag["name"] in seen):
                        raise ValueError("Invalid model identity")
                    seen.add(tag["name"])
                slots = asyncio.Semaphore(3)
                async def inspect(tag):
                    async with slots:
                        try:
                            result = await client.post(connection["endpoint"] + "/api/show", json={"model": tag["name"]})
                            result.raise_for_status()
                            return public_model(tag, result.json())
                        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
                            # A single broken model must not hide the rest of the inventory.
                            return dict(name=tag["name"], digest=tag["digest"], kind="unverified",
                                        capabilities=[], metadata_error="model_metadata_unavailable")
                models = await asyncio.gather(*(inspect(tag) for tag in tags))
                return dict(scanned_at=datetime.now(timezone.utc).isoformat(),
                            models=sorted(models, key=lambda m: (m["kind"], m["name"])))
    except ModelError:
        raise
    except (TimeoutError, httpx.TimeoutException):
        raise ModelError("model_discovery_timeout", "JHU katalog neodpověděl v časovém limitu.", 504) from None
    except Exception:
        raise ModelError("model_discovery_failed", "JHU katalog není dostupný nebo vrátil neplatná metadata.", 502) from None
    finally:
        _scan_slot.release()
