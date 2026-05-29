from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract base class for generating text embeddings.

    Provides high-level methods to convert text queries and document chunks into
    numerical vectors, facilitating semantic and vector searches.
    """

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
