"""Central construction point for configured model providers."""

from app.core.config import settings
from app.providers.azure_openai import AzureOpenAIEmbeddingProvider, AzureOpenAIProvider
from app.providers.embeddings import EmbeddingProfile, EmbeddingProvider
from app.providers.llm import LLMProvider


def create_embedding_profile() -> EmbeddingProfile:
    """Build the declared profile for the currently configured embedding model."""
    return EmbeddingProfile(
        model_id=settings.AZURE_OPENAI_EMBEDDING_MODEL,
        model_revision=settings.AZURE_OPENAI_EMBEDDING_MODEL_REVISION,
        dimensions=settings.AZURE_OPENAI_EMBEDDING_DIMENSIONS,
        query_prefix=settings.AZURE_OPENAI_EMBEDDING_QUERY_PREFIX,
        document_prefix=settings.AZURE_OPENAI_EMBEDDING_DOCUMENT_PREFIX,
    )


def create_embedding_provider(provider_name: str | None = None) -> EmbeddingProvider:
    selected = (provider_name or settings.EMBEDDING_PROVIDER).strip().lower()
    if selected == "azure_openai":
        return AzureOpenAIEmbeddingProvider(profile=create_embedding_profile())
    raise ValueError(f"Unsupported embedding provider: {selected!r}.")


def catalog_embedding_provider(tenant: str, name: str | None = None, *, space: EmbeddingProfile | None = None, session=None) -> EmbeddingProvider:
    from app.core.embedding_config import embedding_entry
    entry = embedding_entry(tenant, name, space=space, session=session)
    if entry.provider == "azure_openai":
        return AzureOpenAIEmbeddingProvider(profile=entry.space())
    from app.providers.ollama_embeddings import OllamaEmbeddingProvider
    return OllamaEmbeddingProvider(entry)


def create_llm_provider(provider_name: str | None = None) -> LLMProvider:
    selected = (provider_name or settings.LLM_PROVIDER).strip().lower()
    if selected == "azure_openai":
        return AzureOpenAIProvider()
    raise ValueError(f"Unsupported LLM provider: {selected!r}.")


def create_profile_provider(profile, authorize=None) -> LLMProvider:
    from app.providers.model_runtime import ProfileLLMProvider
    return ProfileLLMProvider(profile, authorize=authorize)
