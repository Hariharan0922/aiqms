from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseVectorStore(ABC):
    @abstractmethod
    def upsert_chunks(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        """Upsert document chunks, embeddings, and metadata into the specified collection."""
        pass

    @abstractmethod
    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_dict: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Query nearest neighbor documents using cosine similarity."""
        pass

    @abstractmethod
    def delete(
        self,
        collection_name: str,
        filter_dict: Optional[dict[str, Any]] = None,
        ids: Optional[list[str]] = None,
    ) -> int:
        """Delete entries matching the filter or IDs."""
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Return collection counts and health metrics."""
        pass
