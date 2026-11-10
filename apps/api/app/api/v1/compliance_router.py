import hashlib
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.dependencies import get_actor
from app.db.session import get_db
from app.models.compliance import (
    ISOClause,
    ComplianceTraceabilityItem,
    ComplianceTraceabilityRun,
)
from app.models.ingestion import IngestedDocument
from app.services.compliance.iso_knowledge_service import ISOKnowledgeService
from app.services.compliance.traceability_service import TraceabilityService
from app.services.compliance.llm_evidence_analyzer import (
    LLMEvidenceAnalyzer,
    LLMConnectionError,
    LLMTimeoutError,
    LLMSchemaValidationError,
)
from app.services.compliance.llm_evidence_schema import LLMAnalysisRequest
from app.services.retrieval.semantic_search import ServiceUnavailableError

compliance_router = APIRouter()


class ISOClauseSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="Natural language search query")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of clauses to return")
    category: Optional[str] = Field(None, description="Filter by category")
    level: Optional[int] = Field(None, ge=1, le=4, description="Filter by clause level (1-4)")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum cosine similarity score")


@compliance_router.get("/compliance/iso13485/clauses")
def list_iso_clauses(
    category: Optional[str] = Query(None),
    parent: Optional[str] = Query(None),
    level: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """List standard ISO 13485:2016 clauses available in the knowledge repository."""
    query = db.query(ISOClause)
    if category:
        query = query.filter_by(category=category)
    if parent:
        query = query.filter_by(parent_clause_number=parent)
    if level is not None:
        query = query.filter_by(level=level)
    if q:
        query = query.filter(
            (ISOClause.clause_number.ilike(f"%{q}%"))
            | (ISOClause.title.ilike(f"%{q}%"))
            | (ISOClause.clause_text.ilike(f"%{q}%"))
        )

    clauses = query.order_by(ISOClause.clause_number).all()

    # If database not yet synchronized, sync from primary source PDF
    if not clauses:
        service = ISOKnowledgeService(db=db)
        service.sync_iso_knowledge_base()
        clauses = query.order_by(ISOClause.clause_number).all()

    return {
        "standard": "ISO 13485:2016",
        "total_clauses": len(clauses),
        "clauses": [
            {
                "id": c.id,
                "clause_number": c.clause_number,
                "parent_clause_number": c.parent_clause_number,
                "level": c.level,
                "title": c.title,
                "category": c.category,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "summary": c.summary_requirements,
                "requires_procedure": c.requires_documented_procedure,
                "requires_record": c.requires_record,
                "is_normative": c.is_normative,
                "embedding_status": c.embedding_status,
            }
            for c in clauses
        ],
    }


class CreateISOClauseRequest(BaseModel):
    clause_number: str = Field(..., min_length=1, max_length=20, description="Clause number, e.g. 7.5.12")
    title: str = Field(..., min_length=2, max_length=255, description="Clause title")
    category: str = Field(default="Product realization", max_length=100)
    parent_clause_number: Optional[str] = Field(None, max_length=20)
    level: int = Field(default=3, ge=1, le=4)
    clause_text: str = Field(..., min_length=10, description="Clause text or requirement specification")
    normative_text: Optional[str] = None
    summary_requirements: Optional[str] = None
    requires_documented_procedure: bool = True
    requires_record: bool = True
    is_normative: bool = True
    standard: str = Field(default="ISO 13485:2016")


@compliance_router.post("/compliance/iso13485/clauses", status_code=201)
def create_iso_clause_endpoint(
    body: CreateISOClauseRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Add a new ISO standard clause directly into the knowledge repository via API."""
    existing = db.query(ISOClause).filter_by(clause_number=body.clause_number.strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Clause '{body.clause_number}' already exists in knowledge base.")

    cid = f"iso_{body.clause_number.strip().replace('.', '_')}"
    new_clause = ISOClause(
        id=cid,
        standard=body.standard.strip(),
        clause_number=body.clause_number.strip(),
        parent_clause_number=body.parent_clause_number.strip() if body.parent_clause_number else None,
        level=body.level,
        title=body.title.strip(),
        category=body.category.strip(),
        clause_text=body.clause_text.strip(),
        normative_text=body.normative_text.strip() if body.normative_text else body.clause_text.strip(),
        explanatory_notes="",
        is_normative=body.is_normative,
        summary_requirements=body.summary_requirements.strip() if body.summary_requirements else body.title.strip(),
        requires_documented_procedure=body.requires_documented_procedure,
        requires_record=body.requires_record,
        page_start=1,
        page_end=1,
        subclauses_count=0,
        content_hash=hashlib.sha256(body.clause_text.encode("utf-8")).hexdigest(),
        embedding_status="completed",
    )
    db.add(new_clause)
    db.commit()
    db.refresh(new_clause)
    return {
        "status": "success",
        "message": f"ISO clause {new_clause.clause_number} added successfully to repository.",
        "clause": {
            "id": new_clause.id,
            "clause_number": new_clause.clause_number,
            "title": new_clause.title,
            "category": new_clause.category,
            "standard": new_clause.standard,
            "requires_documented_procedure": new_clause.requires_documented_procedure,
            "requires_record": new_clause.requires_record,
        },
    }


@compliance_router.get("/compliance/iso13485/clauses/{clause_number}")
def get_iso_clause_detail(
    clause_number: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Get single ISO 13485 clause detail with hierarchy, notes and requirement text."""
    service = ISOKnowledgeService(db=db)
    clause = service.get_clause_by_number(clause_number)
    if not clause:
        raise HTTPException(
            status_code=404, detail=f"ISO 13485 clause '{clause_number}' not found."
        )
    return clause


@compliance_router.get("/compliance/iso13485/hierarchy")
def get_iso_clause_hierarchy(
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Get complete nested hierarchy tree of ISO 13485:2016 clauses."""
    service = ISOKnowledgeService(db=db)
    return {
        "standard": "ISO 13485:2016",
        "tree": service.get_hierarchy_tree(),
    }


@compliance_router.post("/compliance/iso13485/sync")
def sync_iso_knowledge_base_endpoint(
    force_reindex: bool = Query(False),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Sync ISO 13485 clauses from primary source PDF into PostgreSQL and ChromaDB."""
    service = ISOKnowledgeService(db=db)
    result = service.sync_iso_knowledge_base(force_reindex=force_reindex)
    return result


@compliance_router.post("/compliance/iso13485/search")
def search_iso_clauses_endpoint(
    req: ISOClauseSearchRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Semantic vector search across ISO 13485:2016 standard clauses."""
    service = ISOKnowledgeService(db=db)
    try:
        results = service.search_clauses(
            query=req.query,
            top_k=req.top_k,
            category=req.category,
            level=req.level,
            min_score=req.min_score,
        )
        return {
            "query": req.query,
            "total_results": len(results),
            "results": results,
        }
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {exc}")


@compliance_router.post("/compliance/iso13485/seed")
def seed_iso_clauses_endpoint(
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Seed or update authoritative ISO 13485:2016 standard clauses in database and ChromaDB."""
    service = ISOKnowledgeService(db=db)
    result = service.sync_iso_knowledge_base()
    return {"message": f"Successfully seeded and synchronized ISO 13485 clauses: {result}"}


class ReviewMappingRequest(BaseModel):
    decision: str = Field(..., description="'verified', 'changes_requested', or 'rejected'")
    comment: str = Field(..., min_length=2, max_length=2000, description="Reviewer justification or notes")


class NotApplicableRequest(BaseModel):
    justification: str = Field(..., min_length=15, max_length=2000, description="Documented rationale for ISO exclusion")


class ManualLinkRequest(BaseModel):
    chunk_id: str = Field(..., description="IngestedChunk ID to link as evidence")


@compliance_router.post("/compliance/verify/{document_id}")
@compliance_router.post("/compliance/traceability/{document_id}")
def generate_document_traceability(
    document_id: str,
    similarity_threshold: float = Query(0.45, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve ISO clauses, document chunks, and generate candidate traceability mappings."""
    service = TraceabilityService(db=db)
    try:
        run = service.generate_candidate_mappings(
            document_id=document_id,
            actor_email=actor.get("email", "system"),
            similarity_threshold=similarity_threshold,
        )
        return {
            "run_id": run.id,
            "document_id": run.document_id,
            "status": run.status,
            "total_clauses": run.total_clauses_evaluated,
            "evidence_identified": run.evidence_identified_count,
            "insufficient_evidence": run.insufficient_evidence_count,
            "not_mapped": run.not_mapped_count,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@compliance_router.get("/compliance/traceability/runs/{run_id}")
def get_traceability_run_summary(
    run_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve traceability run summary and metrics."""
    run = db.query(ComplianceTraceabilityRun).filter_by(id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Traceability run not found.")
    doc = db.query(IngestedDocument).filter_by(id=run.document_id).first()
    return {
        "run_id": run.id,
        "document_id": run.document_id,
        "document_name": doc.original_filename if doc else "Document",
        "standard": run.standard,
        "status": run.status,
        "total_clauses": run.total_clauses_evaluated,
        "not_mapped": run.not_mapped_count,
        "evidence_identified": run.evidence_identified_count,
        "pending_review": run.pending_review_count,
        "verified": run.verified_count,
        "insufficient_evidence": run.insufficient_evidence_count,
        "not_applicable": run.not_applicable_count,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@compliance_router.get("/compliance/traceability/runs/{run_id}/items")
def list_traceability_items(
    run_id: str,
    status: Optional[str] = Query(None, description="Filter by mapping_status"),
    clause: Optional[str] = Query(None, description="Filter by clause_number"),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """List all candidate clause-to-document mappings for a run."""
    query = db.query(ComplianceTraceabilityItem).filter_by(run_id=run_id)
    if status:
        query = query.filter_by(mapping_status=status)
    if clause:
        query = query.filter(ComplianceTraceabilityItem.clause_number.like(f"{clause}%"))

    items = query.order_by(ComplianceTraceabilityItem.clause_number).all()
    return {
        "run_id": run_id,
        "total_items": len(items),
        "items": [
            {
                "id": itm.id,
                "clause_number": itm.clause_number,
                "mapping_status": itm.mapping_status,
                "mapping_confidence": itm.mapping_confidence,
                "document_number": itm.document_number,
                "document_revision": itm.document_revision,
                "section_number": itm.section_number,
                "section_title": itm.section_title,
                "page_start": itm.page_start,
                "page_end": itm.page_end,
                "rules_validation_status": itm.rules_validation_status,
                "reviewed_by": itm.reviewed_by,
                "reviewed_at": itm.reviewed_at.isoformat() if itm.reviewed_at else None,
                "reviewer_decision": itm.reviewer_decision,
            }
            for itm in items
        ],
    }


@compliance_router.get("/compliance/traceability/items/{item_id}")
def get_traceability_item_detail(
    item_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve detailed traceability item including evidence excerpt, rule findings and audit trail."""
    item = db.query(ComplianceTraceabilityItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Traceability item not found.")
    clause = db.query(ISOClause).filter_by(clause_number=item.clause_number).first()
    return {
        "id": item.id,
        "run_id": item.run_id,
        "clause_number": item.clause_number,
        "clause_title": clause.title if clause else item.clause_number,
        "category": clause.category if clause else "General",
        "requires_procedure": clause.requires_documented_procedure if clause else False,
        "requires_record": clause.requires_record if clause else False,
        "mapping_status": item.mapping_status,
        "mapping_confidence": item.mapping_confidence,
        "matched_chunk_id": item.matched_chunk_id,
        "document_id": item.document_id,
        "document_number": item.document_number,
        "document_revision": item.document_revision,
        "section_number": item.section_number,
        "section_title": item.section_title,
        "page_start": item.page_start,
        "page_end": item.page_end,
        "evidence_excerpt": item.evidence_excerpt,
        "rules_validation_status": item.rules_validation_status,
        "rules_findings": item.rules_findings,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "reviewer_decision": item.reviewer_decision,
        "reviewer_comment": item.reviewer_comment,
        "na_justification": item.na_justification,
        "audit_trail": item.audit_trail or [],
    }


@compliance_router.post("/compliance/traceability/items/{item_id}/validate")
def validate_traceability_item_endpoint(
    item_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Execute deterministic rules-based validation on a specific traceability item."""
    service = TraceabilityService(db=db)
    try:
        res = service.validate_item_rules(item_id=item_id)
        return res.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@compliance_router.post("/compliance/traceability/items/{item_id}/submit")
def submit_traceability_item_endpoint(
    item_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Submit a candidate mapping for independent human review."""
    service = TraceabilityService(db=db)
    try:
        updated = service.submit_for_review(item_id=item_id, actor_email=actor.get("email", "system"))
        return {
            "id": updated.id,
            "mapping_status": updated.mapping_status,
            "message": "Item submitted for review.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@compliance_router.post("/compliance/traceability/items/{item_id}/review")
def review_traceability_item_endpoint(
    item_id: str,
    req: ReviewMappingRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Review and verify a traceability mapping item with role authorization."""
    service = TraceabilityService(db=db)
    try:
        item = db.query(ComplianceTraceabilityItem).filter_by(id=item_id).first()
        author_email = None
        if item and item.document_id:
            doc = db.query(IngestedDocument).filter_by(id=item.document_id).first()
            if doc and doc.logs:
                author_email = doc.logs[0].actor_email

        updated = service.review_mapping(
            item_id=item_id,
            decision=req.decision,
            comment=req.comment,
            actor_role=actor.get("role", "author"),
            actor_email=actor.get("email", "reviewer@example.com"),
            author_email=author_email,
        )
        return {
            "id": updated.id,
            "mapping_status": updated.mapping_status,
            "reviewer_decision": updated.reviewer_decision,
            "reviewed_by": updated.reviewed_by,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@compliance_router.post("/compliance/traceability/items/{item_id}/not-applicable")
def set_traceability_item_na_endpoint(
    item_id: str,
    req: NotApplicableRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Mark clause as Not Applicable with documented justification."""
    service = TraceabilityService(db=db)
    try:
        updated = service.set_not_applicable(
            item_id=item_id,
            justification=req.justification,
            actor_email=actor.get("email", "system"),
        )
        return {
            "id": updated.id,
            "mapping_status": updated.mapping_status,
            "na_justification": updated.na_justification,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@compliance_router.post("/compliance/traceability/items/{item_id}/link")
def manual_link_chunk_endpoint(
    item_id: str,
    req: ManualLinkRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Manually link an ingested chunk as supporting evidence."""
    service = TraceabilityService(db=db)
    try:
        updated = service.manual_map_chunk(
            item_id=item_id,
            chunk_id=req.chunk_id,
            actor_email=actor.get("email", "system"),
        )
        return {
            "id": updated.id,
            "mapping_status": updated.mapping_status,
            "matched_chunk_id": updated.matched_chunk_id,
            "section_title": updated.section_title,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@compliance_router.post("/compliance/llm/analyze")
def analyze_evidence_with_llm_endpoint(
    req: LLMAnalysisRequest,
    actor: dict = Depends(get_actor),
):
    """Analyze QMS evidence against an ISO requirement using local Qwen3."""
    analyzer = LLMEvidenceAnalyzer()
    try:
        result = analyzer.analyze_evidence(request=req, actor_email=actor.get("email", "system"))
        return result
    except LLMConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except LLMSchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@compliance_router.post("/compliance/traceability/items/{item_id}/analyze")
def analyze_traceability_item_llm_endpoint(
    item_id: str,
    model_name: str = Query("qwen3:4b"),
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Run local LLM analysis on an existing traceability item and enrich its record."""
    item = db.query(ComplianceTraceabilityItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Traceability item not found.")

    clause = db.query(ISOClause).filter_by(clause_number=item.clause_number).first()
    if not clause:
        raise HTTPException(status_code=404, detail=f"ISO Clause {item.clause_number} not found.")

    req = LLMAnalysisRequest(
        clause_number=clause.clause_number,
        clause_title=clause.title,
        clause_text=clause.normative_text or clause.clause_text,
        summary_requirements=clause.summary_requirements,
        document_number=item.document_number,
        document_revision=item.document_revision,
        section_number=item.section_number,
        section_title=item.section_title,
        page_start=item.page_start,
        page_end=item.page_end,
        evidence_text=item.evidence_excerpt,
        model_name=model_name,
    )

    analyzer = LLMEvidenceAnalyzer()
    try:
        analysis_result = analyzer.analyze_evidence(request=req, actor_email=actor.get("email", "system"))
        structured = analysis_result["structured_analysis"]

        # Persist LLM insights into item record
        item.verdict = structured["verdict"]
        item.ai_reasoning = structured["explanation"]
        item.evidence_quote = structured.get("cited_evidence_excerpt")
        item.recommended_action = structured.get("recommended_remediation")

        trail = list(item.audit_trail or [])
        trail.append(analysis_result["audit_entry"])
        item.audit_trail = trail
        db.commit()

        return {
            "item_id": item.id,
            "clause_number": item.clause_number,
            "verdict": item.verdict,
            "model_name": analysis_result["model_name"],
            "duration_seconds": analysis_result["duration_seconds"],
            "analysis": structured,
        }
    except LLMConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@compliance_router.get("/compliance/llm/benchmark")
def run_llm_benchmark_endpoint(
    actor: dict = Depends(get_actor),
):
    """Run comparative benchmark between qwen3:4b and qwen3:8b."""
    analyzer = LLMEvidenceAnalyzer()
    sample_cases = [
        LLMAnalysisRequest(
            clause_number="7.5.6",
            clause_title="Validation of processes for production and service provision",
            clause_text="The organization shall validate any processes for production where output cannot be verified by monitoring.",
            summary_requirements="- Validate processes prior to implementation\n- Maintain records of validation results",
            document_number="ETPL/SOP/QMS/42",
            document_revision="00",
            section_title="Flow Rate Testing Procedure",
            evidence_text="The organization establishes this documented procedure for evaluating flow rate accuracy. Tests shall be executed at 0.5 ml/min. Records of all flow measurements shall be maintained in the test data sheet.",
            page_start=1,
            page_end=2,
        ),
        LLMAnalysisRequest(
            clause_number="4.2.4",
            clause_title="Control of documents",
            clause_text="Documents required by the quality management system shall be controlled.",
            summary_requirements="- Documented procedure for review and approval prior to issue\n- Identification of changes and revisions",
            document_number="ETPL/SOP/QMS/01",
            document_revision="01",
            section_title="Document Release",
            evidence_text="All quality documents require independent review and management approval prior to release. Obsolete copies must be archived.",
            page_start=3,
            page_end=4,
        ),
    ]

    try:
        return analyzer.run_comparative_benchmark(sample_cases, models=["qwen3:4b", "qwen3:8b"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@compliance_router.get("/compliance/runs/{run_id}")
def get_compliance_run_details(
    run_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve full results and granular findings for an ISO 13485 audit run."""
    run = db.query(ComplianceTraceabilityRun).filter_by(id=run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Traceability run not found.")

    doc = db.query(IngestedDocument).filter_by(id=run.document_id).first()

    items = []
    for itm in run.items:
        clause = db.query(ISOClause).filter_by(id=itm.clause_id).first()
        items.append({
            "id": itm.id,
            "clause_number": itm.clause_number,
            "clause_title": clause.title if clause else "Unknown",
            "category": clause.category if clause else "General",
            "similarity_score": itm.similarity_score,
            "verdict": itm.verdict,
            "ai_reasoning": itm.ai_reasoning,
            "evidence_quote": itm.evidence_quote,
            "gap_description": itm.gap_description,
            "recommended_action": itm.recommended_action,
            "severity": itm.severity,
        })

    return {
        "run_id": run.id,
        "document_id": run.document_id,
        "document_name": doc.original_filename if doc else "Document",
        "standard": run.standard,
        "status": run.status,
        "overall_compliance_score": run.overall_compliance_score,
        "total_clauses_evaluated": run.total_clauses_evaluated,
        "compliant_count": run.compliant_count,
        "partial_count": run.partial_count,
        "gap_count": run.gap_count,
        "not_addressed_count": run.not_applicable_count,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "items": items,
    }


@compliance_router.get("/compliance/matrix/{document_id}")
def get_document_matrix(
    document_id: str,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Retrieve the ISO 13485 traceability matrix for an ingested document."""
    service = TraceabilityService(db=db)
    try:
        return service.get_traceability_matrix(document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
