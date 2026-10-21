"""Digest-pinned Ollama /api/embed adapter; no truncation, retries or fallback."""
import math

import httpx

from app.core.embedding_config import EmbeddingEntry
from app.core.model_config import ModelError
from app.providers.embeddings import EmbeddingProvider
from app.providers.embeddings import EmbeddingProfile
from app.providers.jhu_connection import embedding_connection, slots


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, entry: EmbeddingEntry) -> None:
        self.entry = entry
        self._profile = entry.space()

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([self.profile.prepare_query(text)]))[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed([self.profile.prepare_document(text) for text in texts])

    async def _verify_digest(self, client, endpoint):
        result = await client.get(endpoint + "/api/tags")
        result.raise_for_status()
        models = result.json()["models"]
        matches = [item for item in models if item.get("name") == self.profile.model_id]
        expected = self.profile.model_revision.removeprefix("sha256:")
        if len(matches) != 1 or matches[0].get("digest") != expected:
            raise ModelError("embedding_model_changed", "Model chybí nebo se změnil jeho digest. Vytvořte nový profil a index.")

    async def _embed(self, inputs):
        if not inputs:
            return []
        if any(len(text) > self.entry.max_input_chars for text in inputs):
            raise ModelError("embedding_input_too_large", "Text překračuje vstupní limit embeddingového profilu.", 422)
        conn = await embedding_connection()
        if not slots.acquire(blocking=False):
            raise ModelError("model_busy", "JHU služba právě zpracovává jiný požadavek. Zkuste to znovu.", 429)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.entry.timeout_seconds, connect=10),
                    auth=httpx.BasicAuth(conn["username"], conn["password"]), trust_env=False,
                    follow_redirects=False) as client:
                await self._verify_digest(client, conn["endpoint"])
                vectors = []
                for start in range(0, len(inputs), self.entry.batch_size):
                    batch = inputs[start:start + self.entry.batch_size]
                    result = await client.post(conn["endpoint"] + "/api/embed", json={
                        "model": self.profile.model_id, "input": batch, "truncate": False})
                    result.raise_for_status()
                    body = result.json()
                    if body.get("model") != self.profile.model_id:
                        raise ValueError("Unexpected response model")
                    current = body["embeddings"]
                    if not isinstance(current, list) or len(current) != len(batch):
                        raise ValueError("Incomplete embedding batch")
                    for vector in current:
                        if not isinstance(vector, list) or any(type(x) not in {float, int} for x in vector):
                            raise ValueError("Invalid vector type")
                        self.profile.validate_vector(vector)
                        if not math.isclose(math.hypot(*vector), 1.0, abs_tol=0.001):
                            raise ValueError("Expected L2-normalized vector")
                    vectors.extend(current)
                # A mutable tag must not silently mix two embedding spaces.
                await self._verify_digest(client, conn["endpoint"])
                return vectors
        except ModelError:
            raise
        except httpx.TimeoutException:
            raise ModelError("embedding_timeout", "JHU embedding neodpověděl v časovém limitu.", 504) from None
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            code, message, status_code = {
                400: ("embedding_input_rejected", "Embeddingová služba odmítla vstup; ověřte délku textu a kontext modelu.", 422),
                401: ("embedding_credentials_invalid", "JHU přihlašovací údaje byly odmítnuty.", 502),
                403: ("embedding_credentials_invalid", "JHU přihlašovací údaje byly odmítnuty.", 502),
                404: ("embedding_model_not_found", "Embeddingový model nebo API není dostupné.", 503),
                429: ("model_busy", "JHU služba je vytížená. Zkuste to později.", 429),
            }.get(status, ("embedding_request_failed", "Embeddingová služba požadavek odmítla.", 502))
            raise ModelError(code, message, status_code) from None
        except Exception:
            raise ModelError("embedding_request_failed", "Volání embeddingové služby selhalo nebo vrátilo neplatná data.", 502) from None
        finally:
            slots.release()
