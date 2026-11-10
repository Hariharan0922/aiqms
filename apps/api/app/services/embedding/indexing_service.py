import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.models.ingestion import IngestedChunk, IngestedDocument, IngestedDocumentMetadata, IngestionLog
from app.services.embedding.ollama_embedder import OllamaEmbeddingClient, OllamaEmbeddingError
from app.services.vector_store.chroma_service import ChromaVectorStoreService

logger = logging.getLogger(__name__)


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of stripped text content."""
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


class DocumentIndexingService:
    """Modular service managing chunk embedding generation, duplicate detection, and ChromaDB indexing."""

    def __init__(
        self,
        db: Session,
        embedder: Optional[OllamaEmbeddingClient] = None,
        vector_store: Optional[ChromaVectorStoreService] = None,
    ):
        self.db = db
        self.embedder = embedder or OllamaEmbeddingClient()
        self.vector_store = vector_store or ChromaVectorStoreService()

    def index_document(
        self,
        document_id: str,
        force_reindex: bool = False,
        batch_size: int = 16,
    ) -> dict[str, Any]:
        """Index all eligible chunks for a document into ChromaDB with duplicate detection."""
        doc = self.db.query(IngestedDocument).filter_by(id=document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found in database.")

        # If already indexed and not forcing reindex, return existing status
        if doc.vector_status == "indexed" and not force_reindex:
            chunks = self.db.query(IngestedChunk).filter_by(document_id=doc.id).all()
            return {
                "document_id": doc.id,
                "status": "already_indexed",
                "total_chunks": len(chunks),
                "indexed_chunks": sum(1 for c in chunks if c.embedding_status == "embedded"),
                "skipped_duplicates": 0,
                "failed_chunks": sum(1 for c in chunks if c.embedding_status == "failed"),
                "vector_status": doc.vector_status,
                "indexed_at": doc.vector_indexed_at.isoformat() if doc.vector_indexed_at else None,
            }

        # If forcing reindex, purge existing ChromaDB vectors for this document first
        if force_reindex:
            self.vector_store.delete_document_chunks(document_id=doc.id)

        # Retrieve chunks for this document
        chunks_query = self.db.query(IngestedChunk).filter_by(document_id=doc.id).order_by(IngestedChunk.chunk_sequence)
        if not force_reindex:
            # Only process pending or failed chunks
            chunks_to_process = chunks_query.filter(IngestedChunk.embedding_status.in_(["pending", "failed"])).all()
        else:
            chunks_to_process = chunks_query.all()

        if not chunks_to_process:
            doc.vector_status = "indexed"
            if not doc.vector_indexed_at:
                doc.vector_indexed_at = datetime.now(timezone.utc)
            self.db.commit()
            return {
                "document_id": doc.id,
                "status": "indexed",
                "total_chunks": doc.total_chunks,
                "indexed_chunks": 0,
                "skipped_duplicates": 0,
                "failed_chunks": 0,
                "vector_status": doc.vector_status,
            }

        # Track results
        indexed_count = 0
        skipped_duplicates = 0
        failed_count = 0
        now = datetime.now(timezone.utc)

        # 1. Duplicate detection: check for existing identical content hashes in PostgreSQL
        chunks_to_embed: list[IngestedChunk] = []
        vectors_to_upsert: list[list[float]] = []

        for chunk in chunks_to_process:
            # Ensure content hash is populated
            if not chunk.content_hash:
                chunk.content_hash = compute_content_hash(chunk.chunk_text)

            # Check if an identical chunk has already been embedded in PostgreSQL (across or within documents)
            existing_embedded = (
                self.db.query(IngestedChunk)
                .filter(
                    IngestedChunk.content_hash == chunk.content_hash,
                    IngestedChunk.embedding_status == "embedded",
                    IngestedChunk.id != chunk.id,
                )
                .first()
            )

            # If existing embedded chunk found, we can check if its vector exists in ChromaDB
            cached_vector = None
            if existing_embedded and existing_embedded.vector_id:
                chroma_entry = self.vector_store.get_chunk(existing_embedded.vector_id)
                if chroma_entry and chroma_entry.get("embedding") is not None:
                    raw_emb = chroma_entry["embedding"]
                    cached_vector = [float(x) for x in raw_emb]

            if cached_vector is not None:
                # Reuse cached vector without calling Ollama
                skipped_duplicates += 1
                meta = self._build_chunk_metadata(doc, chunk)
                self.vector_store.upsert_chunks(
                    collection_name=ChromaVectorStoreService.COLLECTION_CHUNKS,
                    ids=[chunk.id],
                    embeddings=[cached_vector],
                    documents=[chunk.chunk_text],
                    metadatas=[meta],
                )
                chunk.embedding_status = "embedded"
                chunk.embedding_model = self.embedder.model
                chunk.embedded_at = now
                chunk.vector_id = chunk.id
                chunk.embedding_error = None
                indexed_count += 1
            else:
                chunks_to_embed.append(chunk)

        # 2. Batch embed the remaining unique chunks via Ollama nomic-embed-text
        for i in range(0, len(chunks_to_embed), batch_size):
            batch = chunks_to_embed[i : i + batch_size]
            batch_texts = [c.chunk_text for c in batch]

            try:
                embeddings = self.embedder.embed_batch(batch_texts)
                metas = [self._build_chunk_metadata(doc, c) for c in batch]
                ids = [c.id for c in batch]

                # Upsert into ChromaDB
                self.vector_store.upsert_chunks(
                    collection_name=ChromaVectorStoreService.COLLECTION_CHUNKS,
                    ids=ids,
                    embeddings=embeddings,
                    documents=batch_texts,
                    metadatas=metas,
                )

                # Update PostgreSQL chunk records
                for idx, c in enumerate(batch):
                    c.embedding_status = "embedded"
                    c.embedding_model = self.embedder.model
                    c.embedded_at = now
                    c.vector_id = c.id
                    c.embedding_error = None
                    indexed_count += 1

            except Exception as exc:
                logger.error("Failed to embed batch starting at chunk %d: %s", i, exc)
                for c in batch:
                    c.embedding_status = "failed"
                    c.embedding_error = str(exc)
                    failed_count += 1

        # 3. Update Document Vector Status
        if failed_count == 0:
            doc.vector_status = "indexed"
            doc.vector_indexed_at = now
            doc.error_message = None
        elif indexed_count > 0:
            doc.vector_status = "indexed"  # Partial index
            doc.vector_indexed_at = now
            doc.error_message = f"{failed_count} chunks failed embedding generation."
        else:
            doc.vector_status = "failed"
            doc.error_message = f"Embedding generation failed for all {failed_count} chunks."

        # Audit log in PostgreSQL
        log = IngestionLog(
            document_id=doc.id,
            step="embedding_and_vector_indexing",
            status="success" if failed_count == 0 else "partial" if indexed_count > 0 else "failed",
            message=f"Indexed {indexed_count} chunks, {skipped_duplicates} duplicates reused, {failed_count} failed.",
            details_json={
                "indexed_chunks": indexed_count,
                "skipped_duplicates": skipped_duplicates,
                "failed_chunks": failed_count,
                "embedding_model": self.embedder.model,
            },
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(doc)

        return {
            "document_id": doc.id,
            "status": doc.vector_status,
            "total_chunks": doc.total_chunks,
            "indexed_chunks": indexed_count,
            "skipped_duplicates": skipped_duplicates,
            "failed_chunks": failed_count,
            "embedding_model": self.embedder.model,
            "indexed_at": doc.vector_indexed_at.isoformat() if doc.vector_indexed_at else None,
        }

    def reindex_document(
        self,
        document_id: str,
        new_revision: Optional[str] = None,
    ) -> dict[str, Any]:
        """Re-index a document after revision update or content change, preserving DB authority."""
        doc = self.db.query(IngestedDocument).filter_by(id=document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        # Update revision metadata if provided
        if new_revision:
            if doc.metadata_record:
                doc.metadata_record.revision_number = new_revision
            else:
                doc.metadata_record = IngestedDocumentMetadata(document_id=doc.id, revision_number=new_revision)
                self.db.add(doc.metadata_record)
            for chunk in doc.chunks:
                chunk.document_revision = new_revision

        # Mark vector status as unindexed/processing
        doc.vector_status = "unindexed"
        doc.vector_indexed_at = None
        for chunk in doc.chunks:
            chunk.embedding_status = "pending"
            chunk.vector_id = None

        self.db.commit()

        # Run fresh indexing with force_reindex=True
        return self.index_document(document_id=doc.id, force_reindex=True)

    def recover_failed_embeddings(self, document_id: Optional[str] = None, limit: int = 50) -> dict[str, Any]:
        """Retrieve failed chunks from PostgreSQL and attempt recovery embedding."""
        query = self.db.query(IngestedChunk).filter_by(embedding_status="failed")
        if document_id:
            query = query.filter_by(document_id=document_id)

        failed_chunks = query.limit(limit).all()
        if not failed_chunks:
            return {
                "message": "No failed chunks found for recovery.",
                "recovered_count": 0,
                "still_failed_count": 0,
            }

        recovered_count = 0
        still_failed_count = 0
        now = datetime.now(timezone.utc)

        # Group by document to build proper metadata
        docs_cache: dict[str, IngestedDocument] = {}

        for chunk in failed_chunks:
            if chunk.document_id not in docs_cache:
                doc = self.db.query(IngestedDocument).filter_by(id=chunk.document_id).first()
                if doc:
                    docs_cache[chunk.document_id] = doc

            doc = docs_cache.get(chunk.document_id)
            if not doc:
                continue

            try:
                # Retry single chunk
                vector = self.embedder.embed_documents([chunk.chunk_text])[0]
                meta = self._build_chunk_metadata(doc, chunk)

                self.vector_store.upsert_chunks(
                    collection_name=ChromaVectorStoreService.COLLECTION_CHUNKS,
                    ids=[chunk.id],
                    embeddings=[vector],
                    documents=[chunk.chunk_text],
                    metadatas=[meta],
                )

                chunk.embedding_status = "embedded"
                chunk.embedding_model = self.embedder.model
                chunk.embedded_at = now
                chunk.vector_id = chunk.id
                chunk.embedding_error = None
                recovered_count += 1
            except Exception as exc:
                chunk.embedding_error = f"Recovery attempt failed: {str(exc)}"
                still_failed_count += 1

        self.db.commit()

        # Update document statuses if any documents were touched
        for doc in docs_cache.values():
            unembedded = (
                self.db.query(IngestedChunk)
                .filter(IngestedChunk.document_id == doc.id, IngestedChunk.embedding_status != "embedded")
                .count()
            )
            if unembedded == 0:
                doc.vector_status = "indexed"
                doc.vector_indexed_at = now
                doc.error_message = None
            self.db.commit()

        return {
            "recovered_count": recovered_count,
            "still_failed_count": still_failed_count,
            "processed_chunks": len(failed_chunks),
        }

    def get_document_embedding_status(self, document_id: str) -> dict[str, Any]:
        """Retrieve detailed embedding metrics and status for a document."""
        doc = self.db.query(IngestedDocument).filter_by(id=document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        chunks = self.db.query(IngestedChunk).filter_by(document_id=doc.id).all()
        meta = doc.metadata_record

        embedded_chunks = [c for c in chunks if c.embedding_status == "embedded"]
        pending_chunks = [c for c in chunks if c.embedding_status == "pending"]
        failed_chunks = [c for c in chunks if c.embedding_status == "failed"]

        return {
            "document_id": doc.id,
            "filename": doc.original_filename,
            "document_number": meta.document_number if meta else None,
            "revision": meta.revision_number if meta else None,
            "vector_status": doc.vector_status,
            "vector_indexed_at": doc.vector_indexed_at.isoformat() if doc.vector_indexed_at else None,
            "total_chunks": len(chunks),
            "embedded_count": len(embedded_chunks),
            "pending_count": len(pending_chunks),
            "failed_count": len(failed_chunks),
            "embedding_model": self.embedder.model,
            "error_message": doc.error_message,
            "failed_chunk_errors": [
                {"chunk_id": c.id, "sequence": c.chunk_sequence, "error": c.embedding_error}
                for c in failed_chunks if c.embedding_error
            ],
        }

    def get_system_embedding_status(self) -> dict[str, Any]:
        """Retrieve system-wide vector storage and embedding status."""
        conn_info = self.embedder.check_connection()
        chroma_stats = self.vector_store.get_stats()

        total_db_chunks = self.db.query(IngestedChunk).count()
        embedded_db_chunks = self.db.query(IngestedChunk).filter_by(embedding_status="embedded").count()
        pending_db_chunks = self.db.query(IngestedChunk).filter_by(embedding_status="pending").count()
        failed_db_chunks = self.db.query(IngestedChunk).filter_by(embedding_status="failed").count()

        total_docs = self.db.query(IngestedDocument).count()
        indexed_docs = self.db.query(IngestedDocument).filter_by(vector_status="indexed").count()

        return {
            "ollama": conn_info,
            "chroma": chroma_stats,
            "database_metrics": {
                "total_documents": total_docs,
                "indexed_documents": indexed_docs,
                "total_chunks": total_db_chunks,
                "embedded_chunks": embedded_db_chunks,
                "pending_chunks": pending_db_chunks,
                "failed_chunks": failed_db_chunks,
            },
        }

    def _build_chunk_metadata(self, doc: IngestedDocument, chunk: IngestedChunk) -> dict[str, Any]:
        """Construct sanitized metadata dictionary preserving provenance and revision."""
        meta = doc.metadata_record
        return {
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "document_number": chunk.document_number or (meta.document_number if meta else None) or "UNKNOWN",
            "document_revision": chunk.document_revision or (meta.revision_number if meta else None) or "00",
            "section_number": chunk.section_number or "",
            "section_title": chunk.section_title or "General",
            "page_start": chunk.page_start or 1,
            "page_end": chunk.page_end or 1,
            "chunk_sequence": chunk.chunk_sequence,
            "content_hash": chunk.content_hash or compute_content_hash(chunk.chunk_text),
            "filename": doc.original_filename,
        }
