"""Bound inference adapters with no implicit model/provider fallback."""
import asyncio
import json
import re
import time

import httpx
from openai import AsyncAzureOpenAI, APITimeoutError, APIStatusError

from app.core.config import settings
from app.core.model_config import ModelError, ModelProfile
from app.providers.llm import LLMProvider

from app.providers.jhu_connection import slots as _jhu_slots, embedding_connection, jhu_client, jhu_configured


def connection_settings(profile: ModelProfile) -> dict:
    if profile.connection == "jhu":
        return dict(deployment=profile.model)
    return dict(endpoint=settings.AZURE_OPENAI_ENDPOINT, key=settings.AZURE_OPENAI_API_KEY,
                deployment=(settings.AZURE_OPENAI_FLASH_DEPLOYMENT if profile.connection == "azure_mini"
                            else settings.AZURE_OPENAI_THINKING_DEPLOYMENT))


def availability(profile: ModelProfile) -> tuple[bool, str | None]:
    if not profile.enabled:
        return False, "disabled"
    conn = connection_settings(profile)
    if profile.connection == "jhu":
        configured, reason = jhu_configured()
        if not configured:
            return False, reason
        if profile.model_digest is None and (not settings.JHU_LLM_VERIFIED_MODEL or settings.JHU_LLM_VERIFIED_MODEL != profile.model):
            return False, "model_not_verified"
    elif not (conn["endpoint"] and conn["key"] and conn["deployment"]):
        return False, "not_configured"
    return True, None


def render_prompt(messages) -> str:
    # A JSON transcript keeps delimiters in document text from becoming extra turns.
    return ("Follow the system instructions in this conversation. Answer the final user message.\n"
            + json.dumps([{"role": m.role, "content": m.content} for m in messages], ensure_ascii=False))


class ProfileLLMProvider(LLMProvider):
    def __init__(self, profile: ModelProfile, authorize=None):
        self.profile = profile
        self.authorize = authorize
        self.diagnostics = {}

    async def generate(self, messages, model_profile=None, temperature=0.0, max_tokens=None, **kwargs):
        if self.authorize:
            self.authorize()
        ready, _ = availability(self.profile)
        if not ready:
            raise ModelError("model_unavailable", "Vybraný model není nakonfigurovaný nebo aktivní.")
        prompt = render_prompt(messages)
        if max_tokens is not None and (type(max_tokens) is not int or max_tokens < 1):
            raise ModelError("model_output_limit_invalid", "Limit výstupu musí být kladné celé číslo.", 422)
        output_limit = min(max_tokens or self.profile.max_output_tokens, self.profile.max_output_tokens)
        if len(prompt) > self.profile.max_input_chars:
            raise ModelError("model_input_too_large", "Podklady překračují vstupní limit vybraného modelu.", 422)
        if self.profile.context_tokens and len(prompt.encode("utf-8")) > self.profile.context_tokens - self.profile.max_output_tokens - 256:
            raise ModelError("model_input_too_large", "Podklady překračují bezpečný kontextový rozpočet lokálního modelu. Zmenšete počet pasáží nebo historii.", 422)
        started = time.monotonic()
        conn = connection_settings(self.profile)
        try:
            if self.profile.provider == "ollama_generate":
                if not _jhu_slots.acquire(blocking=False):
                    raise ModelError("model_busy", "JHU model právě zpracovává jiný požadavek. Zkuste to znovu.", 429)
                try:
                    conn = await embedding_connection()
                    async with jhu_client(conn, httpx.Timeout(self.profile.timeout_seconds, connect=10)) as client:
                        async def verify_digest():
                            if self.profile.model_digest is None:
                                return
                            tags = await client.get(conn["endpoint"].rstrip("/") + "/api/tags")
                            tags.raise_for_status()
                            matches = [m for m in tags.json()["models"] if m.get("name") == self.profile.model]
                            if len(matches) != 1 or matches[0].get("digest") != self.profile.model_digest:
                                raise ModelError("model_changed", "Model chybí nebo se změnil. Obnovte katalog a přidejte novou verzi modelu.", 409)
                        await verify_digest()
                        payload = {"model": self.profile.model, "prompt": prompt, "stream": False,
                                   "options": {"num_predict": output_limit}}
                        if self.profile.context_tokens:
                            payload["options"]["num_ctx"] = self.profile.context_tokens
                        result = await client.post(conn["endpoint"].rstrip("/") + "/api/generate", json=payload)
                        result.raise_for_status()
                        body = result.json()
                        answer = body.get("response")
                        if body.get("model", self.profile.model) != self.profile.model:
                            raise ModelError("model_mismatch", "Služba vrátila jiný model, než byl vybrán.", 502)
                        self.diagnostics = {k: body[k] for k in ("total_duration", "load_duration", "eval_count")
                                            if isinstance(body.get(k), (int, float))}
                        if body.get("done") is False:
                            raise ValueError("Incomplete generation")
                        if body.get("done_reason") == "length":
                            raise ModelError("model_output_limit", "Model dosáhl limitu odpovědi; zkraťte zadání.", 422)
                        await verify_digest()
                finally:
                    _jhu_slots.release()
            else:
                async with AsyncAzureOpenAI(azure_endpoint=conn["endpoint"], api_key=conn["key"],
                        api_version=settings.AZURE_OPENAI_API_VERSION,
                        timeout=self.profile.timeout_seconds, max_retries=0) as client:
                    result = await client.chat.completions.create(model=conn["deployment"],
                        messages=[{"role": m.role, "content": m.content} for m in messages],
                        reasoning_effort=self.profile.reasoning_effort,
                        max_completion_tokens=output_limit)
                    answer = result.choices[0].message.content
                    actual = getattr(result, "model", self.profile.model)
                    if not re.fullmatch(re.escape(self.profile.model) + r"(?:-\d{4}-\d{2}-\d{2})?", actual):
                        raise ModelError("model_mismatch", "Azure deployment používá jiný model, než deklaruje profil.", 502)
                    if result.choices[0].finish_reason == "length":
                        raise ModelError("model_output_limit", "Model dosáhl limitu odpovědi. Zkraťte zadání.", 422)
            if isinstance(answer, str) and self.profile.provider == "ollama_generate":
                answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
                if "<think>" in answer:
                    raise ValueError("Incomplete thinking output")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Empty response")
            self.diagnostics["generation_ms"] = round((time.monotonic() - started) * 1000)
            return answer
        except ModelError:
            raise
        except (httpx.TimeoutException, asyncio.TimeoutError, APITimeoutError):
            raise ModelError("model_timeout", "Vybraný model neodpověděl v časovém limitu.", 504) from None
        except (httpx.HTTPStatusError, APIStatusError) as error:
            status = error.response.status_code
            if status in {401, 403}:
                raise ModelError("model_credentials_invalid", "Přihlašovací údaje služby modelu byly odmítnuty.", 502) from None
            if status == 404:
                raise ModelError("model_not_found", "Vybraný model nebo deployment není ve službě dostupný.") from None
            if status == 429:
                raise ModelError("model_busy", "Služba modelu je vytížená. Zkuste to později.", 429) from None
            raise ModelError("model_request_failed", "Služba vybraného modelu požadavek odmítla.", 502) from None
        except Exception:
            # Raw SDK errors can contain URLs, provider response text and credentials.
            raise ModelError("model_request_failed", "Volání vybraného modelu selhalo. Kontaktujte správce.", 502) from None

    async def generate_stream(self, *args, **kwargs):
        raise ModelError("streaming_unsupported", "Tento profil nepodporuje streaming.", 422)
        yield ""  # async iterator contract
