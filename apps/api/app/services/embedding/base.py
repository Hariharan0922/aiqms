from abc import ABC, abstractmethod


class BaseEmbeddingClient(ABC):
    @abstractmethod
    def embed_text(self, text: str, prefix: str = "search_document:") -> list[float]:
        """Embed a single string with the specified prefix."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str], prefix: str = "search_document:") -> list[list[float]]:
        """Embed a list of strings in batches."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a search query with 'search_query:' prefix."""
        pass
