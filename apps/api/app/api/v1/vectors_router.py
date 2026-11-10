from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.dependencies import get_actor
from app.db.session import get_db
from app.models.ingestion import IngestedDocument
from app.services.embedding.indexing_service import DocumentIndexingService
from app.services.embedding.ollama_embedder import OllamaEmbeddingClient
from app.services.vector_store.chroma_service import ChromaVectorStoreService

vectors_router = APIRouter()


class EmbedBatchRequest(BaseModel):
    limit: int = 50


class ReindexDocumentRequest(BaseModel):
    new_revision: Optional[str] = Field(None, description="Optional updated revision number (e.g. '01', '02')")


class RecoverFailedRequest(BaseModel):
    document_id: Optional[str] = Field(None, description="Optional document ID to recover, or all if omitted")
    limit: int = Field(50, ge=1, le=500)


@vectors_router.post("/vectors/embed/document/{document_id}")
def embed_document(
    document_id: str,
    force_reindex: bool = Query(default=False, description="Force re-embedding of all chunks"),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Generate vector embeddings for all eligible chunks of a document and index into ChromaDB."""
    service = DocumentIndexingService(db=db)
    try:
        return service.index_document(document_id=document_id, force_reindex=force_reindex)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@vectors_router.post("/vectors/reindex/{document_id}")
def reindex_document(
    document_id: str,
    req: ReindexDocumentRequest = ReindexDocumentRequest(),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Re-index a document after a revision change or manual refresh, maintaining DB authority."""
    service = DocumentIndexingService(db=db)
    try:
        return service.reindex_document(document_id=document_id, new_revision=req.new_revision)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@vectors_router.post("/vectors/recover")
def recover_failed_embeddings(
    req: RecoverFailedRequest = RecoverFailedRequest(),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Attempt recovery for any chunks marked with embedding_status == 'failed'."""
    service = DocumentIndexingService(db=db)
    try:
        return service.recover_failed_embeddings(document_id=req.document_id, limit=req.limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@vectors_router.get("/vectors/document/{document_id}/status")
def get_document_vector_status(
    document_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve detailed per-document embedding status, chunk counts, and any recorded error details."""
    service = DocumentIndexingService(db=db)
    try:
        return service.get_document_embedding_status(document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@vectors_router.post("/vectors/embed/batch")
def embed_batch(
    req: EmbedBatchRequest = EmbedBatchRequest(),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Embed and index all unindexed documents up to the specified limit."""
    unindexed = (
        db.query(IngestedDocument)
        .filter(IngestedDocument.vector_status.in_(["unindexed", "failed"]))
        .limit(req.limit)
        .all()
    )

    service = DocumentIndexingService(db=db)
    results = []
    total_chunks = 0

    for doc in unindexed:
        try:
            res = service.index_document(doc.id)
            chunks = res.get("indexed_chunks", 0)
            total_chunks += chunks
            results.append({"document_id": doc.id, "chunks": chunks, "status": "success"})
        except Exception as exc:
            results.append({"document_id": doc.id, "status": "failed", "error": str(exc)})

    return {
        "processed_documents": len(unindexed),
        "total_chunks_indexed": total_chunks,
        "results": results,
    }


@vectors_router.delete("/vectors/document/{document_id}")
def delete_document_vectors(
    document_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Purge document vectors from ChromaDB and reset DB vector status."""
    doc = db.query(IngestedDocument).filter_by(id=document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    store = ChromaVectorStoreService()
    deleted_count = store.delete_document_chunks(document_id=doc.id)

    doc.vector_status = "unindexed"
    doc.vector_indexed_at = None
    for chunk in doc.chunks:
        chunk.embedding_status = "pending"
        chunk.vector_id = None
    db.commit()

    return {"document_id": doc.id, "deleted_chunks": deleted_count, "status": "unindexed"}


@vectors_router.get("/vectors/status")
def get_vector_status(db: Session = Depends(get_db)):
    """Retrieve comprehensive health, Ollama status, and vector statistics for ChromaDB and PostgreSQL."""
    service = DocumentIndexingService(db=db)
    status_data = service.get_system_embedding_status()
    # Flatten top-level keys for backwards compatibility with existing UI
    ollama_info = status_data["ollama"]
    chroma_info = status_data["chroma"]
    return {
        **chroma_info,
        "ollama_embedding_online": True,
        "embedding_model": ollama_info.get("model", "nomic-embed-text"),
        "details": status_data,
    }
