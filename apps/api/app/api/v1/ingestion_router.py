from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_actor
from app.db.session import get_db
from app.models.ingestion import IngestedChunk, IngestedDocument, IngestedSection
from app.schemas.ingestion import (
    DocumentUploadItemResponse,
    UploadDocumentsResponse,
)
from app.services.ingestion.local_ai_adapter import LocalAIAdapter
from app.services.ingestion.service import DocumentIngestionService
from app.services.ingestion.structure_extractor import ExtractedSection, StructureExtractor

ingestion_router = APIRouter()


@ingestion_router.post("/documents/upload", response_model=UploadDocumentsResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Upload single or multiple QMS documents (.docx, .pdf) for ingestion and processing."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for upload.")

    service = DocumentIngestionService(db=db)
    results: list[DocumentUploadItemResponse] = []
    successful_count = 0
    failed_count = 0

    for upload_file in files:
        original_name = Path(upload_file.filename or "document").name
        try:
            content = await upload_file.read()
            doc_record = service.ingest_bytes(
                filename=original_name,
                content=content,
                actor_email=actor.get("email", "system"),
                organization_id=actor.get("organization_id", "default"),
            )

            is_success = doc_record.upload_status == "uploaded" and doc_record.processing_status != "failed"
            if is_success:
                successful_count += 1
            else:
                failed_count += 1

            results.append(
                DocumentUploadItemResponse(
                    document_id=doc_record.id,
                    original_filename=doc_record.original_filename,
                    file_format=doc_record.file_format,
                    upload_status=doc_record.upload_status,
                    upload_timestamp=doc_record.created_at.isoformat() if doc_record.created_at else datetime.now(timezone.utc).isoformat(),
                    processing_status=doc_record.processing_status,
                    warnings=doc_record.warnings_json or [],
                    error_message=doc_record.error_message,
                )
            )
        except Exception as exc:
            failed_count += 1
            results.append(
                DocumentUploadItemResponse(
                    document_id="DOC-FAILED",
                    original_filename=original_name,
                    file_format="UNKNOWN",
                    upload_status="failed",
                    upload_timestamp=datetime.now(timezone.utc).isoformat(),
                    processing_status="failed",
                    warnings=[],
                    error_message=f"Upload processing failed: {str(exc)}",
                )
            )

    return UploadDocumentsResponse(
        total_uploaded=len(files),
        successful=successful_count,
        failed=failed_count,
        documents=results,
    )


@ingestion_router.get("/documents/ingested")
def list_ingested_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    file_format: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """List all ingested documents with metadata summary and status."""
    query = db.query(IngestedDocument).filter_by(organization_id=actor.get("organization_id", "default"))

    if file_format:
        query = query.filter(IngestedDocument.file_format == file_format.upper())
    if status:
        query = query.filter(IngestedDocument.processing_status == status.lower())

    total = query.count()
    records = query.order_by(desc(IngestedDocument.created_at)).offset(offset).limit(limit).all()

    items = []
    for doc in records:
        meta = doc.metadata_record
        items.append({
            "id": doc.id,
            "filename": doc.original_filename,
            "file_format": doc.file_format,
            "file_size_bytes": doc.file_size_bytes,
            "upload_status": doc.upload_status,
            "processing_status": doc.processing_status,
            "extraction_status": doc.extraction_status,
            "vector_status": getattr(doc, "vector_status", "unindexed") or "unindexed",
            "vector_indexed_at": doc.vector_indexed_at.isoformat() if getattr(doc, "vector_indexed_at", None) else None,
            "ocr_required": doc.ocr_required,
            "total_pages": doc.total_pages,
            "total_sections": doc.total_sections,
            "total_chunks": doc.total_chunks,
            "uploaded_by": doc.uploaded_by,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            "warnings_count": len(doc.warnings_json or []),
            "metadata_summary": {
                "title": meta.document_title if meta else None,
                "document_number": meta.document_number if meta else None,
                "revision": meta.revision_number if meta else None,
                "effective_date": meta.effective_date if meta else None,
                "department": meta.department if meta else None,
                "prepared_by": meta.prepared_by if meta else None,
                "reviewed_by": meta.reviewed_by if meta else None,
                "approved_by": meta.approved_by if meta else None,
            } if meta else None,
        })

    return {"total": total, "limit": limit, "offset": offset, "documents": items}


@ingestion_router.get("/documents/ingested/{document_id}")
def get_ingested_document(
    document_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve full details of an ingested document."""
    doc = db.query(IngestedDocument).filter_by(
        id=document_id, organization_id=actor.get("organization_id", "default")
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Ingested document not found.")

    meta = doc.metadata_record
    return {
        "id": doc.id,
        "filename": doc.original_filename,
        "file_format": doc.file_format,
        "file_size_bytes": doc.file_size_bytes,
        "upload_status": doc.upload_status,
        "processing_status": doc.processing_status,
        "extraction_status": doc.extraction_status,
        "vector_status": getattr(doc, "vector_status", "unindexed") or "unindexed",
        "vector_indexed_at": doc.vector_indexed_at.isoformat() if getattr(doc, "vector_indexed_at", None) else None,
        "ocr_required": doc.ocr_required,
        "total_pages": doc.total_pages,
        "total_sections": doc.total_sections,
        "total_chunks": doc.total_chunks,
        "error_message": doc.error_message,
        "warnings": doc.warnings_json or [],
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        "metadata": {
            "document_title": meta.document_title,
            "document_number": meta.document_number,
            "revision": meta.revision_number,
            "effective_date": meta.effective_date,
            "review_date": meta.review_date,
            "department": meta.department,
            "document_owner": meta.document_owner,
            "prepared_by": meta.prepared_by,
            "reviewed_by": meta.reviewed_by,
            "approved_by": meta.approved_by,
            "purpose": meta.purpose,
            "scope": meta.scope,
            "responsibilities": meta.responsibilities,
            "confidence_scores": meta.confidence_scores or {},
            "source_snippets": meta.source_snippets or {},
        } if meta else None,
    }


@ingestion_router.get("/documents/ingested/{document_id}/sections")
def get_document_sections(
    document_id: str,
    tree: bool = Query(default=False, description="Return hierarchical nested tree if true"),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve extracted sections for an ingested document."""
    doc = db.query(IngestedDocument).filter_by(
        id=document_id, organization_id=actor.get("organization_id", "default")
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Ingested document not found.")

    sections = db.query(IngestedSection).filter_by(document_id=doc.id).order_by(IngestedSection.section_order).all()

    flat_list = [
        {
            "section_id": s.id,
            "section_number": s.section_number,
            "section_title": s.section_title,
            "parent_section_id": s.parent_section_id,
            "level": s.level,
            "section_order": s.section_order,
            "content_text": s.content_text,
            "page_start": s.page_start,
            "page_end": s.page_end,
        }
        for s in sections
    ]

    if not tree:
        return {"document_id": doc.id, "total_sections": len(flat_list), "sections": flat_list}

    # Convert to ExtractedSection objects to use StructureExtractor.build_tree
    extractor_sections = [
        ExtractedSection(
            section_id=s["section_id"],
            section_number=s["section_number"],
            section_title=s["section_title"],
            parent_section_id=s["parent_section_id"],
            level=s["level"],
            section_order=s["section_order"],
            content_text=s["content_text"],
            page_start=s["page_start"],
            page_end=s["page_end"],
        )
        for s in flat_list
    ]
    tree_sections = StructureExtractor().build_tree(extractor_sections)
    return {
        "document_id": doc.id,
        "total_sections": len(flat_list),
        "tree": [s.to_dict() for s in tree_sections],
    }


@ingestion_router.get("/documents/ingested/{document_id}/chunks")
def get_document_chunks(
    document_id: str,
    for_embedding: bool = Query(default=False, description="Format chunks ready for vector embedding models"),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve document chunks with traceability metadata."""
    doc = db.query(IngestedDocument).filter_by(
        id=document_id, organization_id=actor.get("organization_id", "default")
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Ingested document not found.")

    chunks = db.query(IngestedChunk).filter_by(document_id=doc.id).order_by(IngestedChunk.chunk_sequence).all()

    if not for_embedding:
        return {
            "document_id": doc.id,
            "total_chunks": len(chunks),
            "chunks": [
                {
                    "chunk_id": c.id,
                    "section_id": c.section_id,
                    "section_title": c.section_title,
                    "section_number": c.section_number,
                    "document_number": c.document_number,
                    "document_revision": c.document_revision,
                    "chunk_sequence": c.chunk_sequence,
                    "chunk_text": c.chunk_text,
                    "character_count": c.character_count,
                    "token_count_estimate": c.token_count_estimate,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "extraction_status": c.extraction_status,
                    "metadata": c.metadata_json or {},
                }
                for c in chunks
            ],
        }

    adapter = LocalAIAdapter()
    return {
        "document_id": doc.id,
        "model_target": "nomic-embed-text",
        "total_chunks": len(chunks),
        "embedding_payloads": [
            adapter.format_chunk_for_embedding(
                type("ChunkWrapper", (), {
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "document_number": c.document_number,
                    "document_revision": c.document_revision,
                    "section_title": c.section_title,
                    "section_number": c.section_number,
                    "chunk_text": c.chunk_text,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "chunk_sequence": c.chunk_sequence,
                    "character_count": c.character_count,
                })()
            )
            for c in chunks
        ],
    }


@ingestion_router.get("/documents/ingested/{document_id}/json")
def get_document_json(
    document_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve or download the official schema-validated structured JSON output."""
    doc = db.query(IngestedDocument).filter_by(
        id=document_id, organization_id=actor.get("organization_id", "default")
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Ingested document not found.")

    json_path = (Path(settings.aiqms_storage_dir).resolve() / "ingested" / "json" / f"{doc.id}.json")
    if not json_path.is_file():
        raise HTTPException(status_code=404, detail="Structured JSON artifact not found on storage.")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return JSONResponse(content=data)


@ingestion_router.get("/ai/readiness")
def get_ai_readiness():
    """Check readiness for local AI integration with Ollama (nomic-embed-text, qwen3)."""
    adapter = LocalAIAdapter()
    return adapter.get_readiness_report()
