from typing import Any, AsyncIterator, List, Optional
from openai import AsyncAzureOpenAI

from app.core.config import settings
from app.providers.embeddings import EmbeddingProvider
from app.providers.llm import ChatMessage, LLMProvider


class AzureOpenAIProvider(LLMProvider):
    """Real LLM provider implementing the LLMProvider contract using Azure OpenAI."""

    def __init__(self) -> None:
        """Initialize the AsyncAzureOpenAI client."""
        # The client will throw a validation error if endpoint or api_key are missing.
        # We only instantiate the client if settings are provided.
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.api_key = settings.AZURE_OPENAI_API_KEY
        
        if self.endpoint and self.api_key:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version="2024-05-01-preview",
                timeout=settings.AZURE_OPENAI_TIMEOUT,
            )
        else:
            self.client = None

    def _get_client(self) -> AsyncAzureOpenAI:
        if not self.client:
            raise ValueError(
                "Azure OpenAI is not configured. Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."
            )
        return self.client

    def _resolve_deployment(self, model_profile: str) -> str:
        """Map generic model profiles to concrete deployment names."""
        if model_profile == "thinking":
            return settings.AZURE_OPENAI_THINKING_DEPLOYMENT
        # Default to flash deployment
        return settings.AZURE_OPENAI_FLASH_DEPLOYMENT

    async def generate(
        self,
        messages: List[ChatMessage],
        model_profile: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        client = self._get_client()
        deployment = self._resolve_deployment(model_profile)

        formatted_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        completion_args = {
            "model": deployment,
            "messages": formatted_messages,
            "temperature": temperature,
            **kwargs,
        }
        if max_tokens is not None:
            completion_args["max_tokens"] = max_tokens

        response = await client.chat.completions.create(**completion_args)
        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        messages: List[ChatMessage],
        model_profile: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        client = self._get_client()
        deployment = self._resolve_deployment(model_profile)

        formatted_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        completion_args = {
            "model": deployment,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True,
            **kwargs,
        }
        if max_tokens is not None:
            completion_args["max_tokens"] = max_tokens

        response_stream = await client.chat.completions.create(**completion_args)

        async for chunk in response_stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AzureOpenAIEmbeddingProvider(EmbeddingProvider):
    """Real embedding provider implementing the EmbeddingProvider contract using Azure OpenAI."""

    def __init__(self) -> None:
        """Initialize the AsyncAzureOpenAI client."""
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.api_key = settings.AZURE_OPENAI_API_KEY
        
        if self.endpoint and self.api_key:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version="2024-05-01-preview",
                timeout=settings.AZURE_OPENAI_TIMEOUT,
            )
        else:
            self.client = None

    def _get_client(self) -> AsyncAzureOpenAI:
        if not self.client:
            raise ValueError(
                "Azure OpenAI is not configured. Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."
            )
        return self.client

    async def embed_query(self, text: str) -> List[float]:
        client = self._get_client()
        deployment = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT

        response = await client.embeddings.create(
            input=[text],
            model=deployment,
            # text-embedding-3-large supports custom dimensions; default matches database model.
            dimensions=1536,
        )
        return response.data[0].embedding

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        client = self._get_client()
        deployment = settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
        
        # Batch size of 32 prevents payload timeouts and complies with standard Azure API limits
        batch_size = 32
        results = []
        
        # Split texts into smaller batch arrays
        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
        
        import asyncio
        
        async def embed_batch(batch: List[str]) -> List[List[float]]:
            response = await client.embeddings.create(
                input=batch,
                model=deployment,
                dimensions=1536,
            )
            return [item.embedding for item in response.data]

        # Execute batches concurrently
        tasks = [embed_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)
        
        # Flatten batch outputs
        for br in batch_results:
            results.extend(br)
            
        return results
