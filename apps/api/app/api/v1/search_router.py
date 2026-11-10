from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.dependencies import get_actor
from app.db.session import get_db
from app.services.embedding.ollama_embedder import OllamaEmbeddingError
from app.services.retrieval.semantic_search import SemanticSearchEngine, ServiceUnavailableError

search_router = APIRouter()


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Natural-language search query or requirement text")
    document_id: Optional[str] = Field(None, description="Optional document ID to restrict search scope")
    document_number: Optional[str] = Field(None, description="Optional document number to restrict search scope")
    document_revision: Optional[str] = Field(None, description="Optional document revision to filter")
    section_number: Optional[str] = Field(None, description="Optional section number to filter")
    file_format: Optional[str] = Field(None, description="Optional file format filter (DOCX or PDF)")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of relevant chunks to retrieve")
    min_score: float = Field(0.35, ge=0.0, le=1.0, description="Minimum similarity score threshold")


@search_router.post("/search/semantic")
def perform_semantic_search(
    req: SemanticSearchRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Execute natural-language semantic and hybrid keyword search across indexed QMS documents."""
    engine = SemanticSearchEngine(db=db)
    try:
        results = engine.search(
            query=req.query,
            document_id=req.document_id,
            document_number=req.document_number,
            document_revision=req.document_revision,
            section_number=req.section_number,
            file_format=req.file_format,
            top_k=req.top_k,
            min_score=req.min_score,
        )
        return results
    except ServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Semantic search service temporarily unavailable: {str(exc)}",
        )
    except OllamaEmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama embedding service error: {str(exc)}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(exc)}",
        )
