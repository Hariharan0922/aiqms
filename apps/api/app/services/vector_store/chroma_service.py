import json
import logging
from pathlib import Path
from typing import Any, Optional
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    chromadb = None
    ChromaSettings = None
from app.core.config import settings
from app.services.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class ChromaVectorStoreService(BaseVectorStore):
    """Local, in-process persistent ChromaDB vector store for AIQMS."""

    COLLECTION_CHUNKS = "aiqms_document_chunks"
    COLLECTION_ISO = "iso_13485_clauses"

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = Path(persist_dir or (Path(settings.aiqms_storage_dir) / "chroma")).resolve()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        if chromadb is None:
            logger.warning("chromadb is not installed; vector store functionality is in stub mode.")
            self._client = None
            return
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True),
        )
        # Pre-initialize primary collections with cosine distance metric
        self._get_or_create_collection(self.COLLECTION_CHUNKS)
        self._get_or_create_collection(self.COLLECTION_ISO)

    def _get_or_create_collection(self, collection_name: str):
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
        """ChromaDB metadata only allows str, int, float, or bool. Convert others safely."""
        clean = {}
        for k, v in meta.items():
            if v is None:
                clean[k] = ""
            elif isinstance(v, (str, int, float, bool)):
                clean[k] = v
            elif isinstance(v, (dict, list)):
                clean[k] = json.dumps(v)
            else:
                clean[k] = str(v)
        return clean

    def upsert_chunks(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        """Upsert document chunks, embeddings, and metadata into ChromaDB."""
        if not ids:
            return 0

        collection = self._get_or_create_collection(collection_name)
        sanitized_metas = [self._sanitize_metadata(m) for m in metadatas]

        # Chroma upsert updates existing IDs or inserts new ones idempotently
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=sanitized_metas,
        )
        return len(ids)

    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_dict: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Query nearest neighbor documents using cosine similarity."""
        collection = self._get_or_create_collection(collection_name)
        count = collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": actual_k,
        }

        if filter_dict:
            # ChromaDB expects {"field": "value"} or compound operators
            query_kwargs["where"] = filter_dict

        try:
            results = collection.query(**query_kwargs)
        except Exception as exc:
            logger.warning("Chroma query failed with filter %s: %s", filter_dict, exc)
            # Retry without where filter if filter failed
            if filter_dict:
                query_kwargs.pop("where", None)
                results = collection.query(**query_kwargs)
            else:
                raise

        output = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        for idx in range(len(ids)):
            dist = distances[idx] if idx < len(distances) else 1.0
            # Cosine distance in Chroma is 1.0 - cosine_similarity.
            # Thus similarity = 1.0 - distance. Bound between 0.0 and 1.0.
            similarity = max(0.0, min(1.0, 1.0 - dist))

            meta = metas[idx] if idx < len(metas) else {}
            # Restore deserialized fields if present
            clean_meta = dict(meta)

            output.append({
                "id": ids[idx],
                "score": round(similarity, 4),
                "distance": round(dist, 4),
                "document": docs[idx] if idx < len(docs) else "",
                "metadata": clean_meta,
            })

        # Sort descending by similarity score
        output.sort(key=lambda x: x["score"], reverse=True)
        return output

    def get_chunk(self, chunk_id: str, collection_name: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Retrieve a specific chunk and its metadata by vector ID."""
        col_name = collection_name or self.COLLECTION_CHUNKS
        collection = self._get_or_create_collection(col_name)
        res = collection.get(ids=[chunk_id], include=["metadatas", "documents", "embeddings"])
        if res and res.get("ids") and len(res["ids"]) > 0:
            return {
                "id": res["ids"][0],
                "document": res["documents"][0] if res.get("documents") else "",
                "metadata": res["metadatas"][0] if res.get("metadatas") else {},
                "embedding": res["embeddings"][0] if res.get("embeddings") is not None and len(res["embeddings"]) > 0 else None,
            }
        return None

    def get_document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        """Retrieve all vector chunk records belonging to a document ID."""
        collection = self._get_or_create_collection(self.COLLECTION_CHUNKS)
        res = collection.get(where={"document_id": document_id}, include=["metadatas", "documents"])
        output = []
        ids = res.get("ids", [])
        docs = res.get("documents", [])
        metas = res.get("metadatas", [])
        for i in range(len(ids)):
            output.append({
                "id": ids[i],
                "document": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
            })
        return output

    def delete(
        self,
        collection_name: str,
        filter_dict: Optional[dict[str, Any]] = None,
        ids: Optional[list[str]] = None,
    ) -> int:
        """Delete items from the collection."""
        collection = self._get_or_create_collection(collection_name)
        if ids:
            collection.delete(ids=ids)
            return len(ids)
        elif filter_dict:
            collection.delete(where=filter_dict)
            return 1
        return 0

    def delete_document_chunks(self, document_id: str) -> int:
        """Purge all chunk vectors corresponding to a document ID."""
        return self.delete(
            collection_name=self.COLLECTION_CHUNKS,
            filter_dict={"document_id": document_id},
        )

    def get_stats(self) -> dict[str, Any]:
        """Return counts and status for all Chroma collections."""
        chunks_col = self._get_or_create_collection(self.COLLECTION_CHUNKS)
        iso_col = self._get_or_create_collection(self.COLLECTION_ISO)

        return {
            "status": "online",
            "persist_dir": str(self.persist_dir),
            "engine": "ChromaDB (HNSW Cosine)",
            "total_chunks_indexed": chunks_col.count(),
            "iso_clauses_indexed": iso_col.count(),
            "collections": {
                self.COLLECTION_CHUNKS: {
                    "count": chunks_col.count(),
                    "distance_metric": "cosine",
                },
                self.COLLECTION_ISO: {
                    "count": iso_col.count(),
                    "distance_metric": "cosine",
                },
            },
        }
