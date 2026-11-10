import logging
import re
import time
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.ingestion import IngestedChunk, IngestedDocument
from app.services.embedding.ollama_embedder import OllamaEmbeddingClient, OllamaEmbeddingError
from app.services.vector_store.chroma_service import ChromaVectorStoreService

logger = logging.getLogger(__name__)


class ServiceUnavailableError(Exception):
    """Raised when Ollama or ChromaDB dependencies are unreachable."""
    pass


class SemanticSearchEngine:
    """Production hybrid semantic and keyword retrieval engine for AIQMS documents."""

    def __init__(
        self,
        embedder: Optional[OllamaEmbeddingClient] = None,
        vector_store: Optional[ChromaVectorStoreService] = None,
        db: Optional[Session] = None,
    ):
        self.embedder = embedder or OllamaEmbeddingClient()
        self.vector_store = vector_store or ChromaVectorStoreService()
        self.db = db

    def search(
        self,
        query: str,
        document_id: Optional[str] = None,
        document_number: Optional[str] = None,
        document_revision: Optional[str] = None,
        section_number: Optional[str] = None,
        file_format: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.35,
    ) -> dict[str, Any]:
        """Perform dense semantic and hybrid keyword search with PostgreSQL authoritative data lookup."""
        start_time = time.time()
        clean_query = (query or "").strip()

        # Handle empty search query
        if not clean_query:
            return {
                "query": "",
                "total_results": 0,
                "total_hits": 0,
                "top_k": top_k,
                "min_score": min_score,
                "filters_applied": {},
                "execution_time_ms": 0.0,
                "search_time_ms": 0.0,
                "results": [],
            }

        # 1. Verify availability of Ollama embedding service
        if not self.embedder.is_available():
            raise ServiceUnavailableError(
                f"Ollama embedding service is unreachable at {self.embedder.base_url} or model {self.embedder.model} is not available."
            )

        # 2. Embed user natural-language query with search_query: prefix
        try:
            query_vector = self.embedder.embed_query(clean_query)
        except Exception as exc:
            raise ServiceUnavailableError(f"Embedding generation failed for query: {str(exc)}") from exc

        # 3. Build compound metadata filter for ChromaDB
        conditions = []
        if document_id:
            conditions.append({"document_id": document_id})
        if document_number:
            conditions.append({"document_number": document_number})
        if document_revision:
            conditions.append({"document_revision": document_revision})
        if section_number:
            conditions.append({"section_number": section_number})
        if file_format:
            conditions.append({"file_format": file_format.upper()})

        chroma_filter = None
        if len(conditions) == 1:
            chroma_filter = conditions[0]
        elif len(conditions) > 1:
            chroma_filter = {"$and": conditions}

        # 4. Query ChromaDB for candidate chunks
        fetch_k = min(100, max(top_k * 3, 15))
        try:
            raw_matches = self.vector_store.query(
                collection_name=ChromaVectorStoreService.COLLECTION_CHUNKS,
                query_embedding=query_vector,
                top_k=fetch_k,
                filter_dict=chroma_filter,
            )
        except Exception as exc:
            raise ServiceUnavailableError(f"ChromaDB vector retrieval failed: {str(exc)}") from exc

        if not raw_matches:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "query": clean_query,
                "total_results": 0,
                "total_hits": 0,
                "top_k": top_k,
                "min_score": min_score,
                "filters_applied": {
                    "document_id": document_id,
                    "document_number": document_number,
                    "document_revision": document_revision,
                    "section_number": section_number,
                    "file_format": file_format,
                },
                "execution_time_ms": elapsed_ms,
                "search_time_ms": elapsed_ms,
                "results": [],
            }

        # 5. Fetch authoritative source information from PostgreSQL
        chunk_ids = [m["id"] for m in raw_matches]
        db_chunks: dict[str, IngestedChunk] = {}
        db_docs: dict[str, IngestedDocument] = {}

        if self.db and chunk_ids:
            chunks = self.db.query(IngestedChunk).filter(IngestedChunk.id.in_(chunk_ids)).all()
            db_chunks = {c.id: c for c in chunks}
            doc_ids = {c.document_id for c in chunks}
            if doc_ids:
                docs = self.db.query(IngestedDocument).filter(IngestedDocument.id.in_(doc_ids)).all()
                db_docs = {d.id: d for d in docs}

        # 6. Hybrid scoring and provenance compilation
        section_numbers_in_query = set(re.findall(r"\b\d+(?:\.\d+)+\b", clean_query))
        query_words_lower = set(re.findall(r"\w+", clean_query.lower()))

        scored_results = []
        for match in raw_matches:
            base_score = float(match.get("score", 0.0))
            raw_distance = float(match.get("distance", round(max(0.0, 1.0 - base_score), 4)))
            chroma_meta = match.get("metadata", {})
            chunk_id = match["id"]

            # Authoritative chunk & doc data from PostgreSQL (fallback to Chroma metadata if DB session omitted)
            chunk_record = db_chunks.get(chunk_id)
            doc_record = db_docs.get(chunk_record.document_id) if chunk_record else None

            # Retrieve authoritative fields
            resolved_doc_id = chunk_record.document_id if chunk_record else chroma_meta.get("document_id")
            resolved_doc_name = doc_record.original_filename if doc_record else chroma_meta.get("filename", "Unknown Document")
            resolved_doc_format = doc_record.file_format if doc_record else chroma_meta.get("file_format", "DOCX")

            meta_record = doc_record.metadata_record if doc_record else None
            resolved_doc_number = (
                chunk_record.document_number if chunk_record and chunk_record.document_number
                else (meta_record.document_number if meta_record and meta_record.document_number else chroma_meta.get("document_number", "—"))
            )
            resolved_revision = (
                chunk_record.document_revision if chunk_record and chunk_record.document_revision
                else (meta_record.revision_number if meta_record and meta_record.revision_number else chroma_meta.get("document_revision", "00"))
            )

            resolved_sec_number = chunk_record.section_number if chunk_record else chroma_meta.get("section_number")
            resolved_sec_title = chunk_record.section_title if chunk_record else chroma_meta.get("section_title", "General Content")
            resolved_page_start = chunk_record.page_start if chunk_record else chroma_meta.get("page_start", 1)
            resolved_page_end = chunk_record.page_end if chunk_record else chroma_meta.get("page_end", 1)
            resolved_sequence = chunk_record.chunk_sequence if chunk_record else chroma_meta.get("chunk_sequence", 1)

            # Verbatim text: PostgreSQL is authoritative
            resolved_text = chunk_record.chunk_text if chunk_record else match.get("document", "")

            # Apply hybrid bonuses
            match_type = "dense"
            if resolved_sec_number and str(resolved_sec_number).strip() in section_numbers_in_query:
                base_score = min(1.0, base_score + 0.15)
                match_type = "hybrid"

            if resolved_doc_number and str(resolved_doc_number).lower() in clean_query.lower():
                base_score = min(1.0, base_score + 0.10)
                match_type = "hybrid"

            text_words = set(re.findall(r"\w+", resolved_text.lower()))
            overlap = len(query_words_lower & text_words)
            if overlap >= 3:
                base_score = min(1.0, base_score + 0.05)
                if match_type == "dense":
                    match_type = "hybrid"

            if base_score >= min_score:
                scored_results.append({
                    "chunk_id": chunk_id,
                    "document_id": resolved_doc_id,
                    "document_name": resolved_doc_name,
                    "document_number": resolved_doc_number,
                    "document_revision": resolved_revision,
                    "file_format": resolved_doc_format,
                    "section_number": resolved_sec_number,
                    "section_title": resolved_sec_title,
                    "page_start": resolved_page_start,
                    "page_end": resolved_page_end,
                    "chunk_sequence": resolved_sequence,
                    "character_count": len(resolved_text),
                    "score": round(base_score, 4),
                    "similarity_score": round(base_score, 4),
                    "cosine_distance": round(raw_distance, 4),
                    "match_type": match_type,
                    "text": resolved_text,
                })

        # Sort descending by final similarity score and trim to top_k
        scored_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        final_results = scored_results[:top_k]

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "query": clean_query,
            "total_results": len(final_results),
            "total_hits": len(final_results),
            "top_k": top_k,
            "min_score": min_score,
            "filters_applied": {
                "document_id": document_id,
                "document_number": document_number,
                "document_revision": document_revision,
                "section_number": section_number,
                "file_format": file_format,
            },
            "execution_time_ms": elapsed_ms,
            "search_time_ms": elapsed_ms,
            "results": final_results,
        }
