from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.providers import factory
from app.providers.azure_openai import AzureOpenAIEmbeddingProvider
from app.providers.embeddings import EmbeddingProfile


def test_embedding_profile_is_immutable_and_fingerprints_vector_semantics():
    profile = EmbeddingProfile("model-a", "rev-1", 2)

    assert profile.profile_id == EmbeddingProfile("model-a", "rev-1", 2).profile_id
    assert profile.profile_id != EmbeddingProfile("model-b", "rev-1", 2).profile_id
    assert profile.profile_id != EmbeddingProfile("model-a", "rev-2", 2).profile_id
    assert profile.profile_id != EmbeddingProfile("model-a", "rev-1", 3).profile_id
    assert profile.profile_id != EmbeddingProfile("model-a", "rev-1", 2, query_prefix="query: ").profile_id

    with pytest.raises(FrozenInstanceError):
        profile.dimensions = 3


def test_embedding_profile_rejects_invalid_dimensions_and_vectors():
    with pytest.raises(ValueError, match="greater than zero"):
        EmbeddingProfile("model-a", "rev-1", 0)

    profile = EmbeddingProfile("model-a", "rev-1", 2)
    with pytest.raises(ValueError, match="expects 2 dimensions"):
        profile.validate_vector([1.0])
    with pytest.raises(ValueError, match="non-finite"):
        profile.validate_vector([1.0, float("nan")])


class _RecordingEmbeddings:
    def __init__(self):
        self.calls = []

    async def create(self, *, input, model, dimensions):
        self.calls.append({"input": input, "model": model, "dimensions": dimensions})
        def marker(value):
            try:
                return float(value)
            except ValueError:
                return float(len(value))

        return SimpleNamespace(
            data=[
                SimpleNamespace(embedding=[marker(value), 1.0])
                for value in input
            ]
        )


@pytest.mark.anyio
async def test_azure_provider_prepares_queries_and_documents_separately():
    profile = EmbeddingProfile(
        "model-a", "rev-1", 2, query_prefix="query: ", document_prefix="passage: "
    )
    provider = AzureOpenAIEmbeddingProvider(profile=profile)
    recording = _RecordingEmbeddings()
    provider.client = SimpleNamespace(embeddings=recording)

    query_vector = await provider.embed_query("question")
    document_vectors = await provider.embed_documents(["chunk one", "chunk two"])

    assert query_vector == [float(len("query: question")), 1.0]
    assert document_vectors == [
        [float(len("passage: chunk one")), 1.0],
        [float(len("passage: chunk two")), 1.0],
    ]
    assert recording.calls == [
        {"input": ["query: question"], "model": "text-embedding-3-large", "dimensions": 2},
        {
            "input": ["passage: chunk one", "passage: chunk two"],
            "model": "text-embedding-3-large",
            "dimensions": 2,
        },
    ]


@pytest.mark.anyio
async def test_azure_provider_preserves_order_across_batches():
    profile = EmbeddingProfile("model-a", "rev-1", 2)
    provider = AzureOpenAIEmbeddingProvider(profile=profile)
    recording = _RecordingEmbeddings()
    provider.client = SimpleNamespace(embeddings=recording)
    texts = [str(index) for index in range(33)]

    vectors = await provider.embed_documents(texts)

    assert [int(vector[0]) for vector in vectors] == list(range(33))
    assert [len(call["input"]) for call in recording.calls] == [32, 1]


@pytest.mark.anyio
async def test_azure_provider_rejects_wrong_dimension_and_incomplete_batch():
    profile = EmbeddingProfile("model-a", "rev-1", 2)
    provider = AzureOpenAIEmbeddingProvider(profile=profile)

    class WrongDimensionEmbeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0])])

    provider.client = SimpleNamespace(embeddings=WrongDimensionEmbeddings())
    with pytest.raises(ValueError, match="expects 2 dimensions"):
        await provider.embed_query("question")

    class IncompleteEmbeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(data=[])

    provider.client = SimpleNamespace(embeddings=IncompleteEmbeddings())
    with pytest.raises(ValueError, match="returned 0 document embeddings for 1 inputs"):
        await provider.embed_documents(["chunk"])


def test_provider_factory_uses_configured_azure_profile(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "azure_openai")
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_MODEL", "model-b")
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_MODEL_REVISION", "rev-4")
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_DIMENSIONS", 384)
    monkeypatch.setattr(settings, "AZURE_OPENAI_EMBEDDING_QUERY_PREFIX", "query: ")

    provider = factory.create_embedding_provider()

    assert provider.profile.model_id == "model-b"
    assert provider.profile.model_revision == "rev-4"
    assert provider.profile.dimensions == 384
    assert provider.profile.query_prefix == "query: "


def test_provider_factory_fails_clearly_for_unregistered_providers(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "local_model")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "local_model")

    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        factory.create_embedding_provider()
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        factory.create_llm_provider()
