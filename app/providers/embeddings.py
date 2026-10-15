from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import json
import math
from typing import List


@dataclass(frozen=True)
class EmbeddingProfile:
    """Immutable description of an embedding space and its input preparation."""

    model_id: str
    model_revision: str
    dimensions: int
    normalization: str = "provider-defined"
    query_transform_version: str = "raw-text-v1"
    document_transform_version: str = "raw-text-v1"
    query_prefix: str = ""
    document_prefix: str = ""

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("Embedding profile model_id must not be empty.")
        if not self.model_revision.strip():
            raise ValueError("Embedding profile model_revision must not be empty.")
        if self.dimensions < 1:
            raise ValueError("Embedding profile dimensions must be greater than zero.")

    @property
    def profile_id(self) -> str:
        """Return a stable identifier for every setting that changes vector meaning."""
        profile_data = {
            "document_prefix": self.document_prefix,
            "document_transform_version": self.document_transform_version,
            "dimensions": self.dimensions,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "normalization": self.normalization,
            "query_prefix": self.query_prefix,
            "query_transform_version": self.query_transform_version,
        }
        canonical = json.dumps(profile_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def prepare_query(self, text: str) -> str:
        return f"{self.query_prefix}{text}"

    def prepare_document(self, text: str) -> str:
        return f"{self.document_prefix}{text}"

    def validate_vector(self, vector: List[float]) -> List[float]:
        if len(vector) != self.dimensions:
            raise ValueError(
                f"Embedding profile {self.profile_id[:12]} expects "
                f"{self.dimensions} dimensions, received {len(vector)}."
            )
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Embedding vector contains a non-finite value.")
        return vector

    def validate_vectors(self, vectors: List[List[float]]) -> List[List[float]]:
        return [self.validate_vector(vector) for vector in vectors]


class EmbeddingProvider(ABC):
    """Abstract base class for generating text embeddings.

    Provides high-level methods to convert text queries and document chunks into
    numerical vectors, facilitating semantic and vector searches.
    """

    @property
    @abstractmethod
    def profile(self) -> EmbeddingProfile:
        """Describe the model space returned by this provider."""
        raise NotImplementedError

    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """Embed a single query text into a vector.

        Args:
            text: Query string.

        Returns:
            A list of floats representing the embedding vector.
        """
        pass

    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of document texts into a list of vectors.

        Args:
            texts: List of document strings.

        Returns:
            A list of embedding vectors.
        """
        pass
