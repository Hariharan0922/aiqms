from datetime import datetime, timezone
import logging
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import re

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, text

from app.core.config import settings
from app.core.dependencies import get_actor
from app.db.session import get_db
from app.models.entities import (Document, DocumentVersion, ValidationRun, ReviewDecision, Approval,
                                 TraceabilityLink, AuditEvent, RequirementReference, EvidenceFile)
from app.schemas.common import (CreateDocumentRequest, UpdateAnswersRequest, GenerateRequest,
                                ReviewRequest, ApproveRequest, RequirementUpdateRequest,
                                EnhanceFromSummaryRequest, EnhanceDocSummaryRequest,
                                GenerateFromSummaryRequest, PreviewIsoDataRequest, CreateRequirementRequest,
                                CreateCustomTemplateRequest, RegenerateSectionRequest, UpdateSectionContentRequest)
from app.services.enhancement_service import ContentEnhancementService
from app.services.nvidia_service import NvidiaService
from app.services.template_mapping_service import TemplateMappingService
from app.services.document_generator import DocumentGenerator
from app.schemas.generated_document import GeneratedDocument, GeneratedSection
from app.services.audit_service import record_event
from app.services.validation_service import ValidationService
from app.services.prompt_service import build_generation_request, PROMPT_VERSION
from app.providers.base import GenerationRequest
from app.providers.registry import ProviderRegistry
from app.providers.openrouter_provider import OpenRouterProvider
from app.templates.registry import list_templates, get_template, add_custom_template, REQUIREMENTS
from app.exporting.render import render_docx, render_pdf
from app.api.v1.ingestion_router import ingestion_router
from app.api.v1.vectors_router import vectors_router
from app.api.v1.search_router import search_router
from app.api.v1.compliance_router import compliance_router
from app.api.v1.ml_compliance_router import ml_compliance_router

router = APIRouter(prefix="/api/v1")
router.include_router(ingestion_router)
router.include_router(vectors_router)
router.include_router(search_router)
router.include_router(compliance_router)
router.include_router(ml_compliance_router)


def _doc_or_404(db: Session, document_id: str, actor: dict) -> Document:
    doc = db.query(Document).filter_by(id=document_id, organization_id=actor["organization_id"]).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


def _current_version(db: Session, doc: Document) -> DocumentVersion:
    version = None
    if doc.current_version_id:
        version = db.query(DocumentVersion).filter_by(id=doc.current_version_id, document_id=doc.id).first()
    if not version:
        version = db.query(DocumentVersion).filter_by(document_id=doc.id).order_by(desc(DocumentVersion.revision)).first()
    if not version:
        raise HTTPException(status_code=500, detail="Document has no version record.")
    return version


def _template_for(doc: Document) -> dict:
    template = get_template(doc.template_id)
    if not template:
        raise HTTPException(status_code=409, detail="Template definition is no longer available.")
    if template["version"] != doc.template_version:
        # Template registry versions are immutable in a release; this check guards accidental drift.
        raise HTTPException(status_code=409, detail="Template version mismatch. Restore the original template version before continuing.")
    return template



def _trace_snapshot(req: RequirementReference | None, code: str) -> dict:
    if req is None:
        return {"source_title": code, "source_name": "Unverified", "source_edition": "", "source_reference": "",
                "source_summary": "", "source_verification_status": "requires_verification", "source_verified_by": None,
                "source_verified_at": None, "source_verification_note": ""}
    return {"source_title": req.title, "source_name": req.source_name, "source_edition": req.source_edition,
            "source_reference": req.source_reference, "source_summary": req.summary,
            "source_verification_status": req.verification_status, "source_verified_by": req.verified_by,
            "source_verified_at": req.verified_at, "source_verification_note": req.verification_note}

def _serialize_version(db: Session, version: DocumentVersion) -> dict:
    latest = db.query(ValidationRun).filter_by(document_version_id=version.id).order_by(desc(ValidationRun.created_at)).first()
    reviews = db.query(ReviewDecision).filter_by(document_version_id=version.id).order_by(ReviewDecision.created_at).all()
    approvals = db.query(Approval).filter_by(document_version_id=version.id).order_by(Approval.created_at).all()
    evidence = db.query(EvidenceFile).filter_by(document_version_id=version.id).order_by(EvidenceFile.uploaded_at.desc()).all()
    return {
        "id": version.id, "revision": version.revision, "status": version.status,
        "answers": version.answers or {}, "applicability": version.applicability or {},
        "content": version.content or {}, "validation_status": version.validation_status,
        "provider": version.provider, "model_id": version.model_id, "prompt_version": version.prompt_version,
        "input_hash": version.input_hash, "created_by": version.created_by,
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "generated_at": version.generated_at.isoformat() if version.generated_at else None,
        "latest_validation": ({"id": latest.id, "ruleset_version": latest.ruleset_version, "passed": latest.passed,
                               "findings": latest.findings, "created_at": latest.created_at.isoformat() if latest.created_at else None} if latest else None),
        "reviews": [{"id": r.id, "reviewer_email": r.reviewer_email, "reviewer_role": r.reviewer_role, "decision": r.decision, "comments": r.comments, "created_at": r.created_at.isoformat()} for r in reviews],
        "approvals": [{"id": a.id, "approver_email": a.approver_email, "approver_role": a.approver_role, "decision": a.decision, "comments": a.comments, "created_at": a.created_at.isoformat()} for a in approvals],
        "evidence": [{"id": e.id, "filename": e.original_filename, "mime_type": e.mime_type, "size_bytes": e.size_bytes,
                      "checksum_sha256": e.checksum_sha256, "uploaded_by": e.uploaded_by, "uploaded_at": e.uploaded_at.isoformat()} for e in evidence],
    }


def _serialize_document(db: Session, doc: Document, include_versions: bool = False) -> dict:
    version = _current_version(db, doc)
    data = {
        "id": doc.id, "organization_id": doc.organization_id, "document_number": doc.document_number,
        "title": doc.title, "document_type": doc.document_type, "template_id": doc.template_id,
        "template_version": doc.template_version, "created_by": doc.created_by,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "current_version": _serialize_version(db, version),
    }
    if include_versions:
        versions = db.query(DocumentVersion).filter_by(document_id=doc.id).order_by(desc(DocumentVersion.revision)).all()
        data["versions"] = [{"id": v.id, "revision": v.revision, "status": v.status, "created_by": v.created_by,
                             "created_at": v.created_at.isoformat() if v.created_at else None} for v in versions]
    return data


def _require_role(actor: dict, *roles: str):
    if actor["role"] not in roles:
        raise HTTPException(status_code=403, detail=f"Requires one of these roles: {', '.join(roles)}.")


def _record_and_commit(db: Session, actor, action: str, entity_type: str, entity_id: str, metadata: dict | None = None):
    record_event(db, actor, action, entity_type, entity_id, metadata)
    db.commit()


@router.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/templates")
def templates():
    return list_templates()


@router.get("/templates/{template_id}")
def template_detail(template_id: str):
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")
    return template


@router.post("/templates", status_code=201)
def create_template_endpoint(body: CreateCustomTemplateRequest, actor: dict = Depends(get_actor)):
    _require_role(actor, "author", "admin")
    created = add_custom_template(body.model_dump())
    return created


@router.get("/system/diagnostics")
def system_diagnostics(db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    """Run full system diagnostics across backend, database, NVIDIA API, template mapping, and rendering."""
    import time
    t0 = time.time()
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "database": {"status": "ok", "latency_ms": 0.0},
        "nvidia_nim": {"status": "not_tested", "latency_ms": None},
        "template_mapping": {"status": "ok"},
        "document_rendering": {"docx": "ok", "pdf": "ok"},
        "all_passed": True,
    }

    # 1. Database check
    try:
        db_t0 = time.time()
        db.execute(text("SELECT 1"))
        results["database"]["latency_ms"] = round((time.time() - db_t0) * 1000, 2)
    except Exception as exc:
        results["database"] = {"status": "error", "error": str(exc)}
        results["all_passed"] = False

    # 2. NVIDIA NIM API check
    try:
        nvidia_svc = NvidiaService()
        nv_test = nvidia_svc.test_connectivity()
        results["nvidia_nim"] = {
            "status": "ok" if nv_test.get("success") else "error",
            "configured": nv_test.get("configured"),
            "model": nv_test.get("model"),
            "latency_ms": nv_test.get("response_time_ms"),
            "error": nv_test.get("error"),
        }
        if not nv_test.get("success") and nv_test.get("configured"):
            results["all_passed"] = False
    except Exception as exc:
        results["nvidia_nim"] = {"status": "error", "error": str(exc)}
        results["all_passed"] = False

    # 3. OpenRouter API check
    try:
        or_provider = OpenRouterProvider()
        or_test = or_provider.test_connectivity()
        results["openrouter"] = {
            "status": "ok" if or_test.get("success") else ("not_configured" if not or_test.get("configured") else "error"),
            "configured": or_test.get("configured"),
            "model": or_test.get("model"),
            "latency_ms": or_test.get("response_time_ms"),
            "error": or_test.get("error"),
        }
    except Exception as exc:
        results["openrouter"] = {"status": "error", "error": str(exc)}

    # 4. Document Generator quick render test
    try:
        mock_doc = type("MockDoc", (), {"title": "Diagnostics Test Document", "document_number": "DIAG-001", "document_type": "Procedure"})()
        mock_ver = type("MockVer", (), {"revision": 1, "status": "draft", "provider": "nvidia", "generated_at": datetime.now(timezone.utc)})()
        mock_cnt = {"title": "Diagnostics Test", "purpose": "Testing generator.", "scope": "System test.", "sections": [{"section_id": "test", "title": "Test Section", "content": "Sample content."}]}
        docx_bytes = DocumentGenerator.generate_docx(mock_doc, mock_ver, mock_cnt)
        pdf_bytes = DocumentGenerator.generate_pdf(mock_doc, mock_ver, mock_cnt)
        results["document_rendering"] = {
            "docx": "ok" if len(docx_bytes) > 100 else "empty",
            "pdf": "ok" if len(pdf_bytes) > 100 else "empty",
        }
    except Exception as exc:
        results["document_rendering"] = {"status": "error", "error": str(exc)}
        results["all_passed"] = False

    results["total_execution_ms"] = round((time.time() - t0) * 1000, 2)
    return results


@router.post("/system/test-nvidia")
def test_nvidia_endpoint(actor: dict = Depends(get_actor)):
    """Test live connectivity to NVIDIA NIM API with real-time response latency measurement."""
    service = NvidiaService()
    return service.test_connectivity()


@router.post("/system/test-openrouter")
def test_openrouter_endpoint(actor: dict = Depends(get_actor)):
    """Test live connectivity and verify key validity against OpenRouter API."""
    provider = OpenRouterProvider()
    return provider.test_connectivity()



@router.get("/providers")
def providers():
    return ProviderRegistry().available()


@router.get("/requirements")
def requirements(db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    rows = db.query(RequirementReference).order_by(RequirementReference.code).all()
    return [{"code":r.code, "title":r.title, "source_name":r.source_name, "source_edition":r.source_edition,
             "source_reference":r.source_reference, "summary":r.summary, "verification_status":r.verification_status,
             "verified_by":r.verified_by, "verified_at":r.verified_at.isoformat() if r.verified_at else None,
             "verification_note":r.verification_note} for r in rows]


@router.post("/requirements", status_code=201)
def create_requirement(
    body: CreateRequirementRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor)
):
    """Add a new ISO standard or regulatory requirement reference to the repository via API."""
    _require_role(actor, "admin", "author")
    code = body.code.strip().upper()
    existing = db.query(RequirementReference).filter_by(code=code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Requirement code '{code}' already exists.")

    req = RequirementReference(
        code=code,
        title=body.title.strip(),
        source_name=body.source_name.strip(),
        source_edition=body.source_edition.strip(),
        source_reference=body.source_reference.strip(),
        summary=body.summary.strip(),
        verification_status=body.verification_status,
        verified_by=actor["email"] if body.verification_status == "verified" else None,
        verified_at=datetime.now(timezone.utc) if body.verification_status == "verified" else None,
        verification_note=body.verification_note.strip() or ("Verified via API" if body.verification_status == "verified" else ""),
    )
    db.add(req)
    _record_and_commit(db, actor, "requirement.created", "requirement_reference", code, {"title": body.title})
    return {
        "code": req.code,
        "title": req.title,
        "source_name": req.source_name,
        "source_edition": req.source_edition,
        "source_reference": req.source_reference,
        "summary": req.summary,
        "verification_status": req.verification_status,
        "verified_by": req.verified_by,
        "verified_at": req.verified_at.isoformat() if req.verified_at else None,
        "verification_note": req.verification_note,
    }


@router.patch("/requirements/{requirement_code}")
def update_requirement(requirement_code: str, body: RequirementUpdateRequest, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "admin")
    req = db.query(RequirementReference).filter_by(code=requirement_code).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement reference not found.")
    if body.verification_status not in {"requires_verification", "verified"}:
        raise HTTPException(status_code=422, detail="verification_status must be requires_verification or verified.")
    if body.verification_status == "verified" and not body.verification_note.strip():
        raise HTTPException(status_code=422, detail="A verification note is required before a mapping can be marked verified.")
    if body.verification_status == "verified" and (
        body.source_reference.strip().lower() in {"to be mapped against licensed standard text", "not mapped", "unverified"}
        or "verify applicable" in body.source_edition.strip().lower()
    ):
        raise HTTPException(status_code=422, detail="Replace starter placeholder metadata with the exact source edition and reference before marking it verified.")
    req.source_edition = body.source_edition.strip()
    req.source_reference = body.source_reference.strip()
    req.summary = body.summary.strip()
    req.verification_status = body.verification_status
    req.verification_note = body.verification_note.strip()[:4000]
    req.verified_by = actor["email"] if body.verification_status == "verified" else None
    req.verified_at = datetime.now(timezone.utc) if body.verification_status == "verified" else None
    affected_links = db.query(TraceabilityLink).filter_by(requirement_code=requirement_code).all()
    impacted_version_ids = {link.document_version_id for link in affected_links}
    for version_id in impacted_version_ids:
        version = db.query(DocumentVersion).filter_by(id=version_id).first()
        if not version or version.status == "released":
            continue
        link = db.query(TraceabilityLink).filter_by(document_version_id=version_id, requirement_code=requirement_code).first()
        if link:
            for key, value in _trace_snapshot(req, requirement_code).items():
                setattr(link, key, value)
        version.validation_status = "not_run"
        version.content = {}
        version.provider = None; version.model_id = None; version.prompt_version = None; version.input_hash = None; version.generated_at = None
        version.status = "draft"
        doc = db.query(Document).filter_by(id=version.document_id).first()
        if doc: doc.updated_at = datetime.now(timezone.utc)
    record_event(db, actor, "requirement.mapping_updated", "requirement_reference", requirement_code,
                 {"verification_status": body.verification_status, "impacted_versions": len(impacted_version_ids)})
    db.commit()
    return {"code":req.code, "title":req.title, "source_name":req.source_name, "source_edition":req.source_edition,
            "source_reference":req.source_reference, "summary":req.summary, "verification_status":req.verification_status,
            "verified_by":req.verified_by, "verified_at":req.verified_at.isoformat() if req.verified_at else None,
            "verification_note":req.verification_note, "impacted_versions":len(impacted_version_ids)}


@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    docs = db.query(Document).filter_by(organization_id=actor["organization_id"]).all()
    status_counts = {key: 0 for key in ["draft", "validated", "generated", "in_review", "awaiting_approval", "changes_requested", "released"]}
    blocking_findings = 0
    for doc in docs:
        version = _current_version(db, doc)
        status_counts[version.status] = status_counts.get(version.status, 0) + 1
        run = db.query(ValidationRun).filter_by(document_version_id=version.id).order_by(desc(ValidationRun.created_at)).first()
        if run:
            blocking_findings += sum(1 for f in run.findings if f.get("blocks_generation") and not f.get("resolved"))
    return {"total_documents": len(docs), "status_counts": status_counts, "blocking_findings": blocking_findings,
            "pending_reviews": status_counts.get("in_review", 0), "pending_approvals": status_counts.get("awaiting_approval", 0)}


@router.get("/documents")
def documents(db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    docs = db.query(Document).filter_by(organization_id=actor["organization_id"]).order_by(desc(Document.updated_at)).all()
    return [_serialize_document(db, doc) for doc in docs]


@router.post("/documents", status_code=201)
def create_document(body: CreateDocumentRequest, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "author", "admin")
    template = get_template(body.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")
    short = datetime.now(timezone.utc).strftime("%Y%m%d")
    serial = str(uuid4()).split("-")[0].upper()
    doc = Document(organization_id=actor["organization_id"], document_number=f"QMS-{short}-{serial}", title=body.title,
                   document_type=template["name"], template_id=template["id"], template_version=template["version"], created_by=actor["email"])
    db.add(doc); db.flush()
    applicability = {code: {"status": "pending", "rationale": ""} for code in template.get("requirements", [])}
    version = DocumentVersion(document_id=doc.id, revision=1, status="draft", answers=body.answers or {}, applicability=applicability,
                              content={}, validation_status="not_run", created_by=actor["email"])
    db.add(version); db.flush(); doc.current_version_id = version.id
    for code in template.get("requirements", []):
        source = db.query(RequirementReference).filter_by(code=code).first()
        db.add(TraceabilityLink(document_version_id=version.id, requirement_code=code, **_trace_snapshot(source, code),
                                verification_status="not_verified", evidence_refs=[], notes=""))
    _record_and_commit(db, actor, "document.created", "document", doc.id, {"template_id": template["id"], "revision": 1})
    return _serialize_document(db, doc, include_versions=True)


@router.post("/documents/enhance-from-summary")
async def enhance_from_summary(
    body: EnhanceFromSummaryRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor)
):
    """Enhance a user's topic summary into structured ISO 13485 QMS fields and applicability."""
    _require_role(actor, "author", "admin")
    service = ContentEnhancementService(db=db)
    try:
        enhanced = await service.enhance_topic_summary(
            template_id=body.template_id,
            summary=body.summary,
            organization_name=body.organization_name,
            provider_name=body.provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Enhancement service error: {exc}") from exc

    if not body.create_document:
        return enhanced

    template = get_template(body.template_id)
    short = datetime.now(timezone.utc).strftime("%Y%m%d")
    serial = str(uuid4()).split("-")[0].upper()
    doc = Document(
        organization_id=actor["organization_id"],
        document_number=f"QMS-{short}-{serial}",
        title=enhanced["title"],
        document_type=template["name"],
        template_id=template["id"],
        template_version=template["version"],
        created_by=actor["email"],
    )
    db.add(doc)
    db.flush()

    version = DocumentVersion(
        document_id=doc.id,
        revision=1,
        status="draft",
        answers=enhanced["answers"],
        applicability=enhanced["applicability"],
        content={},
        validation_status="not_run",
        created_by=actor["email"],
    )
    db.add(version)
    db.flush()
    doc.current_version_id = version.id

    for code in template.get("requirements", []):
        source = db.query(RequirementReference).filter_by(code=code).first()
        choice = enhanced["applicability"].get(code, {})
        status = "applicability_recorded" if choice.get("status") in {"applicable", "not_applicable"} else "not_verified"
        db.add(
            TraceabilityLink(
                document_version_id=version.id,
                requirement_code=code,
                **_trace_snapshot(source, code),
                verification_status=status,
                evidence_refs=[],
                notes=choice.get("rationale", ""),
            )
        )

    try:
        val_run = ValidationService(db).validate(doc, version, template, actor)
        version.validation_status = "passed" if val_run.passed else "failed"
    except Exception:
        pass

    _record_and_commit(
        db,
        actor,
        "document.created_from_enhanced_summary",
        "document",
        doc.id,
        {
            "template_id": template["id"],
            "provider": enhanced["provider"],
            "summary_length": len(body.summary),
        },
    )
    return _serialize_document(db, doc, include_versions=True)


@router.post("/documents/{document_id}/enhance-from-summary")
async def enhance_existing_document(
    document_id: str,
    body: EnhanceDocSummaryRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor)
):
    """Enhance and populate an existing draft document's inputs from a topic summary."""
    _require_role(actor, "author", "admin")
    doc = _doc_or_404(db, document_id, actor)
    version = _current_version(db, doc)
    if version.status in {"in_review", "awaiting_approval", "released", "approved"}:
        raise HTTPException(
            status_code=409,
            detail="Document is locked in review/release. Create a new revision or request changes to edit.",
        )

    template = _template_for(doc)
    service = ContentEnhancementService(db=db)
    try:
        enhanced = await service.enhance_topic_summary(
            template_id=doc.template_id,
            summary=body.summary,
            organization_name=body.organization_name,
            provider_name=body.provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Enhancement service error: {exc}") from exc

    doc.title = enhanced["title"]
    doc.updated_at = datetime.now(timezone.utc)
    version.answers = enhanced["answers"]
    version.applicability = enhanced["applicability"]

    for link in db.query(TraceabilityLink).filter_by(document_version_id=version.id).all():
        choice = enhanced["applicability"].get(link.requirement_code, {})
        link.verification_status = "applicability_recorded" if choice.get("status") in {"applicable", "not_applicable"} else "not_verified"
        link.notes = choice.get("rationale", "")

    try:
        val_run = ValidationService(db).validate(doc, version, template, actor)
        version.validation_status = "passed" if val_run.passed else "failed"
    except Exception:
        pass

    _record_and_commit(
        db,
        actor,
        "document.enhanced_from_summary",
        "document",
        doc.id,
        {"provider": enhanced["provider"], "summary_length": len(body.summary)},
    )
    return _serialize_document(db, doc, include_versions=True)


def detect_template_for_summary(summary: str, default: str = "sop") -> str:
    """Intelligently map user summary to the best matching ISO standard template."""
    s = summary.lower()
    if any(k in s for k in ["audit", "internal audit", "auditor", "audit program"]):
        return "internal-audit"
    if any(k in s for k in ["risk", "hazard", "fmea", "iso 14971", "risk management", "residual risk"]):
        return "risk-management"
    if any(k in s for k in ["capa", "corrective action", "preventive action", "nonconform", "root cause"]):
        return "capa"
    if any(k in s for k in ["complaint", "customer feedback", "vigilance", "adverse event"]):
        return "complaint-handling"
    if any(k in s for k in ["supplier", "vendor", "outsourced", "purchasing control", "supplier evaluation"]):
        return "supplier-evaluation"
    if any(k in s for k in ["change control", "ecn", "eco", "engineering change", "design change"]):
        return "change-control"
    if any(k in s for k in ["design verification", "design validation", "v&v", "design control", "design input"]):
        return "design-validation"
    if any(k in s for k in ["training", "competency", "qualification", "employee training"]):
        return "training-procedure"
    if any(k in s for k in ["quality manual", "qms scope", "management representative"]):
        return "quality-manual"
    return default


@router.post("/qms/generate-from-summary", status_code=201)
@router.post("/documents/generate-from-summary", status_code=201)
async def generate_qms_from_summary(
    body: GenerateFromSummaryRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor)
):
    """
    Cloud-generate expected ISO standard QMS document data directly from a short summary.

    1. Selects or auto-detects target ISO standard template.
    2. Enhances the summary with formal ISO 13485:2016 quality controls & clause requirements via Cloud AI (NVIDIA NIM).
    3. Runs deterministic quality validation against ISO requirements.
    4. Automatically executes full document section generation via NVIDIA NIM API.
    5. Returns the complete generated document, ISO standard clause traceability, and download links.
    """
    _require_role(actor, "author", "admin")

    template_id = body.template_id
    if not template_id or template_id.strip().lower() in {"auto", "default", ""}:
        template_id = detect_template_for_summary(body.summary)

    template = get_template(template_id)
    if not template:
        available = [t["id"] for t in list_templates()]
        raise HTTPException(
            status_code=400,
            detail=f"Template '{template_id}' is invalid. Available templates: {available}"
        )

    service = ContentEnhancementService(db=db)
    target_provider = body.provider if body.provider and body.provider != "default" else ("nvidia" if settings.nvidia_api_key else "offline")

    try:
        enhanced = await service.enhance_topic_summary(
            template_id=template["id"],
            summary=body.summary,
            organization_name=body.organization_name,
            provider_name=target_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cloud AI enhancement error: {exc}") from exc

    short = datetime.now(timezone.utc).strftime("%Y%m%d")
    serial = str(uuid4()).split("-")[0].upper()
    doc = Document(
        organization_id=actor["organization_id"],
        document_number=f"QMS-{short}-{serial}",
        title=enhanced["title"],
        document_type=template["name"],
        template_id=template["id"],
        template_version=template["version"],
        created_by=actor["email"],
    )
    db.add(doc)
    db.flush()

    version = DocumentVersion(
        document_id=doc.id,
        revision=1,
        status="draft",
        answers=enhanced["answers"],
        applicability=enhanced["applicability"],
        content={},
        validation_status="not_run",
        created_by=actor["email"],
    )
    db.add(version)
    db.flush()
    doc.current_version_id = version.id

    for code in template.get("requirements", []):
        source = db.query(RequirementReference).filter_by(code=code).first()
        choice = enhanced["applicability"].get(code, {})
        status = "applicability_recorded" if choice.get("status") in {"applicable", "not_applicable"} else "not_verified"
        db.add(
            TraceabilityLink(
                document_version_id=version.id,
                requirement_code=code,
                **_trace_snapshot(source, code),
                verification_status=status,
                evidence_refs=[],
                notes=choice.get("rationale", ""),
            )
        )

    val_run = ValidationService(db).validate(doc, version, template, actor)

    if body.auto_generate_sections and val_run.passed:
        requirement_rows = db.query(RequirementReference).all()
        requirement_map = {
            r.code: {
                "title": r.title,
                "source_name": r.source_name,
                "source_reference": r.source_reference,
                "verification_status": r.verification_status,
                "summary": r.summary,
            }
            for r in requirement_rows
        }

        instructions, prompt, digest = build_generation_request(doc, version, template, requirement_map, [])
        request = GenerationRequest(
            system_instructions=instructions,
            prompt=prompt,
            output_schema=GeneratedDocument.model_json_schema(),
        )

        try:
            provider_instance = ProviderRegistry().get(target_provider)
            response = await provider_instance.generate(request)
            generated = GeneratedDocument.model_validate(response.content)

            expected_sections_order = template.get("sections", [])
            expected_sections = set(expected_sections_order)

            if len(generated.sections) == len(expected_sections_order):
                for idx, section in enumerate(generated.sections):
                    if section.section_id not in expected_sections:
                        matched = next((s for s in expected_sections_order if s.lower() in section.title.lower()), None)
                        section.section_id = matched if matched else expected_sections_order[idx]

            actual_sections = [section.section_id for section in generated.sections]
            unknown_sections = set(actual_sections) - expected_sections
            missing_sections = expected_sections - set(actual_sections)
            if not unknown_sections and not missing_sections:
                allowed_requirements = set(template.get("requirements", []))
                for section in generated.sections:
                    cleaned_refs = []
                    for ref in (section.requirement_refs or []):
                        ref_str = str(ref).strip()
                        if ref_str in allowed_requirements:
                            cleaned_refs.append(ref_str)
                        else:
                            matched = next((c_code for c_code in allowed_requirements if c_code in ref_str), None)
                            if matched:
                                cleaned_refs.append(matched)
                            else:
                                first_token = ref_str.split()[0].rstrip(":,;()[]") if ref_str.split() else ""
                                matched_token = next((c_code for c_code in allowed_requirements if c_code.lower() == first_token.lower()), None)
                                if matched_token:
                                    cleaned_refs.append(matched_token)
                    section.requirement_refs = list(dict.fromkeys(cleaned_refs))
                    section.evidence_refs = []

                mapped_content = TemplateMappingService.map_document_content(
                    template=template,
                    generated=generated,
                    answers=version.answers or {},
                    metadata={"document_number": doc.document_number, "revision": version.revision},
                )

                version.content = mapped_content
                version.provider = response.provider
                version.model_id = response.model_id
                version.prompt_version = PROMPT_VERSION
                version.input_hash = digest
                version.generated_at = datetime.now(timezone.utc)
                version.status = "generated"

                links = db.query(TraceabilityLink).filter_by(document_version_id=version.id).all()
                for link in links:
                    sections = [s for s in mapped_content.get("sections", []) if link.requirement_code in (s.get("requirement_refs") or [])]
                    link.section_id = ",".join(s.get("section_id", "") for s in sections)
                    link.verification_status = "linked_unverified" if sections else "not_linked"
                    link.notes = "Generated link only; human verification is required."
        except Exception as exc:
            logger.warning("Cloud generation failed during auto-generate from summary: %s", exc)

    doc.updated_at = datetime.now(timezone.utc)
    _record_and_commit(
        db,
        actor,
        "document.generated_from_summary",
        "document",
        doc.id,
        {
            "template_id": template["id"],
            "provider": enhanced.get("provider"),
            "summary_length": len(body.summary),
            "status": version.status,
        },
    )

    return {
        "status": "success",
        "message": "ISO standard QMS document created and generated from summary successfully.",
        "standard": body.standard,
        "document": {
            "id": doc.id,
            "document_number": doc.document_number,
            "title": doc.title,
            "document_type": doc.document_type,
            "template_id": template["id"],
            "template_name": template["name"],
            "category": template["category"],
            "status": version.status,
            "validation_status": version.validation_status,
            "provider": version.provider or enhanced.get("provider"),
            "model_id": version.model_id or enhanced.get("model_id"),
            "created_at": doc.created_at.isoformat(),
            "generated_at": version.generated_at.isoformat() if version.generated_at else None,
        },
        "iso_standards_context": {
            "standard": body.standard,
            "relevant_clauses": enhanced.get("relevant_iso_clauses", []),
            "requirements_addressed": template.get("requirements", []),
        },
        "enhancement_summary": enhanced.get("enhancement_summary", ""),
        "answers": version.answers,
        "applicability": version.applicability,
        "generated_content": version.content or {},
        "export_urls": {
            "docx": f"/api/v1/documents/{doc.id}/export?format=docx",
            "pdf": f"/api/v1/documents/{doc.id}/export?format=pdf",
        },
    }


@router.post("/qms/preview-iso-data")
async def preview_iso_data(
    body: PreviewIsoDataRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor)
):
    """
    Stateless ISO Data Generator: Send short QMS details and receive expected ISO standard fields,
    applicable ISO 13485 clauses, and quality requirements without creating a document in the database.
    """
    template_id = body.template_id
    if not template_id or template_id.strip().lower() in {"auto", "default", ""}:
        template_id = detect_template_for_summary(body.summary)

    template = get_template(template_id)
    if not template:
        available = [t["id"] for t in list_templates()]
        raise HTTPException(
            status_code=400,
            detail=f"Template '{template_id}' is invalid. Available templates: {available}"
        )

    service = ContentEnhancementService(db=db)
    target_provider = body.provider if body.provider and body.provider != "default" else ("nvidia" if settings.nvidia_api_key else "offline")

    try:
        enhanced = await service.enhance_topic_summary(
            template_id=template["id"],
            summary=body.summary,
            organization_name=body.organization_name,
            provider_name=target_provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cloud AI enhancement error: {exc}") from exc

    return {
        "status": "success",
        "standard": body.standard,
        "template": {
            "id": template["id"],
            "name": template["name"],
            "category": template["category"],
            "description": template["description"],
            "sections": template.get("sections", []),
            "requirements": template.get("requirements", []),
        },
        "title": enhanced.get("title"),
        "answers": enhanced.get("answers", {}),
        "applicability": enhanced.get("applicability", {}),
        "relevant_iso_clauses": enhanced.get("relevant_iso_clauses", []),
        "enhancement_summary": enhanced.get("enhancement_summary", ""),
        "provider": enhanced.get("provider"),
        "model_id": enhanced.get("model_id"),
    }


@router.get("/documents/{document_id}")
def document_detail(document_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    doc = _doc_or_404(db, document_id, actor)
    return _serialize_document(db, doc, include_versions=True)


@router.patch("/documents/{document_id}/answers")
def update_answers(document_id: str, body: UpdateAnswersRequest, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "author", "admin")
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc)
    if version.status in {"in_review", "awaiting_approval", "released", "approved"}:
        raise HTTPException(status_code=409, detail="Inputs are locked in the current workflow state. Request changes or create a new revision after release.")
    changed = False
    if body.answers is not None and body.answers != (version.answers or {}):
        version.answers = body.answers; changed = True
    if body.applicability is not None and body.applicability != (version.applicability or {}):
        template = _template_for(doc)
        allowed = set(template.get("requirements", []))
        if set(body.applicability) - allowed:
            raise HTTPException(status_code=422, detail="Applicability includes requirements that are not part of this template.")
        merged = dict(version.applicability or {})
        for code, decision in body.applicability.items():
            if not isinstance(decision, dict) or decision.get("status") not in {"pending", "applicable", "not_applicable"}:
                raise HTTPException(status_code=422, detail=f"Invalid applicability decision for {code}.")
            merged[code] = {"status": decision.get("status"), "rationale": str(decision.get("rationale", ""))[:4000]}
        version.applicability = merged; changed = True
        for link in db.query(TraceabilityLink).filter_by(document_version_id=version.id).all():
            choice = merged.get(link.requirement_code, {})
            link.verification_status = "applicability_recorded" if choice.get("status") in {"applicable", "not_applicable"} else "not_verified"
            link.notes = choice.get("rationale", "")
    if changed:
        doc.updated_at = datetime.now(timezone.utc)
        version.validation_status = "not_run"
        version.status = "draft"
        version.content = {}
        version.provider = None; version.model_id = None; version.prompt_version = None; version.input_hash = None; version.generated_at = None
        record_event(db, actor, "document.inputs_updated", "document_version", version.id, {"answers_changed": body.answers is not None, "applicability_changed": body.applicability is not None})
    db.commit()
    return _serialize_document(db, doc, include_versions=True)


@router.post("/documents/{document_id}/validate")
def validate_document(document_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "author", "reviewer", "admin")
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc); template = _template_for(doc)
    if version.status in {"in_review", "awaiting_approval", "released", "approved"}:
        raise HTTPException(status_code=409, detail="Cannot validate while this revision is under review or released.")
    result = ValidationService(db).validate(doc, version, template, actor)
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    return result.model_dump(mode="json")


@router.post("/documents/{document_id}/resolve-findings")
def resolve_findings(document_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    # Resolution of data errors must happen by editing inputs; this endpoint is reserved for documented warning dispositions.
    raise HTTPException(status_code=410, detail="Finding overrides are disabled in this MVP. Correct source data or resolve the explicit applicability decision instead.")


@router.get("/documents/{document_id}/prompt-preview")
def prompt_preview(document_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc); template = _template_for(doc)
    try:
        ValidationService(db).assert_generation_allowed(version)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    requirement_rows = db.query(RequirementReference).all()
    requirement_map = {r.code: {"title":r.title, "source_name":r.source_name, "source_reference":r.source_reference,
                                "verification_status":r.verification_status, "summary":r.summary} for r in requirement_rows}
    evidence = db.query(EvidenceFile).filter_by(document_version_id=version.id).all()
    evidence_summaries = [{"id": e.id, "filename": e.original_filename, "checksum_sha256": e.checksum_sha256,
                           "note": "File metadata only; file contents were not extracted by this MVP."} for e in evidence]
    instructions, prompt, digest = build_generation_request(doc, version, template, requirement_map, evidence_summaries)
    return {"document_id":doc.id, "document_version_id":version.id, "revision":version.revision,
            "prompt_version":PROMPT_VERSION, "input_hash":digest, "system_instructions":instructions, "prompt":prompt,
            "provider_note":"The prompt contains user-supplied organization data. Review it before sending it to an external AI provider."}


@router.post("/documents/{document_id}/generate")
async def generate_document(document_id: str, body: GenerateRequest, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "author", "admin")
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc); template = _template_for(doc)
    if version.status in {"in_review", "awaiting_approval", "released", "approved"}:
        raise HTTPException(status_code=409, detail="This revision is locked for review or has been released.")
    try:
        ValidationService(db).assert_generation_allowed(version)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    requirement_rows = db.query(RequirementReference).all()
    requirement_map = {r.code: {"title":r.title, "source_name":r.source_name, "source_reference":r.source_reference,
                                "verification_status":r.verification_status, "summary":r.summary} for r in requirement_rows}
    evidence = db.query(EvidenceFile).filter_by(document_version_id=version.id).all()
    evidence_summaries = [{"id": e.id, "filename": e.original_filename, "checksum_sha256": e.checksum_sha256,
                           "note": "File metadata only; file contents were not extracted by this MVP."} for e in evidence]
    instructions, prompt, digest = build_generation_request(doc, version, template, requirement_map, evidence_summaries)
    request = GenerationRequest(system_instructions=instructions, prompt=prompt, output_schema=GeneratedDocument.model_json_schema())
    
    target_provider = body.provider if body.provider and body.provider != "default" else ("nvidia" if settings.nvidia_api_key else "offline")
    try:
        provider = ProviderRegistry().get(target_provider)
        response = await provider.generate(request)
        generated = GeneratedDocument.model_validate(response.content)
        expected_sections_order = template.get("sections", [])
        expected_sections = set(expected_sections_order)

        # Normalize section_ids if model used numbering (1, 2, 3...) or title matches
        if len(generated.sections) == len(expected_sections_order):
            for idx, section in enumerate(generated.sections):
                if section.section_id not in expected_sections:
                    # Check title match first
                    matched = next((s for s in expected_sections_order if s.lower() in section.title.lower()), None)
                    if matched:
                        section.section_id = matched
                    else:
                        section.section_id = expected_sections_order[idx]

        actual_sections = [section.section_id for section in generated.sections]
        unknown_sections = set(actual_sections) - expected_sections
        missing_sections = expected_sections - set(actual_sections)
        if unknown_sections or missing_sections:
            raise ValueError(f"Generated output section mismatch. Missing: {sorted(missing_sections)}; unknown: {sorted(unknown_sections)}")
        allowed_requirements = set(template.get("requirements", []))
        for section in generated.sections:
            # Normalize requirement_refs if model returned descriptions/clauses e.g. "QMS-DOC-CONTROL (Clause 4.2.4 Control of documents)"
            cleaned_refs = []
            for ref in (section.requirement_refs or []):
                ref_str = str(ref).strip()
                if ref_str in allowed_requirements:
                    cleaned_refs.append(ref_str)
                else:
                    # Check if an allowed requirement code is contained in the string
                    matched = next((code for code in allowed_requirements if code in ref_str), None)
                    if matched:
                        cleaned_refs.append(matched)
                    else:
                        first_token = ref_str.split()[0].rstrip(":,;()[]") if ref_str.split() else ""
                        matched_token = next((code for code in allowed_requirements if code.lower() == first_token.lower()), None)
                        if matched_token:
                            cleaned_refs.append(matched_token)
            section.requirement_refs = list(dict.fromkeys(cleaned_refs))

            # Filter evidence references to available IDs
            available_evidence_ids = {e.id for e in evidence}
            section.evidence_refs = [e_id for e_id in (section.evidence_refs or []) if e_id in available_evidence_ids]

        # Template mapping engine preserves strict layout and ordering
        mapped_content = TemplateMappingService.map_document_content(
            template=template,
            generated=generated,
            answers=version.answers or {},
            metadata={"document_number": doc.document_number, "revision": version.revision},
        )
    except HTTPException:
        raise
    except Exception as exc:
        record_event(db, actor, "document.generation_failed", "document_version", version.id,
                     {"provider": target_provider, "error_type": type(exc).__name__})
        db.commit()
        message = str(exc)
        if len(message) > 500: message = message[:500]
        raise HTTPException(status_code=502, detail=f"Generation failed or returned invalid structured content: {message}") from exc
    doc.updated_at = datetime.now(timezone.utc)
    version.content = mapped_content
    version.provider = response.provider; version.model_id = response.model_id
    version.prompt_version = PROMPT_VERSION; version.input_hash = digest
    version.generated_at = datetime.now(timezone.utc); version.status = "generated"
    # Connect generated sections to internal requirement references. This is a content link, not verified conformity.
    links = db.query(TraceabilityLink).filter_by(document_version_id=version.id).all()
    for link in links:
        sections = [s for s in mapped_content.get("sections", []) if link.requirement_code in (s.get("requirement_refs") or [])]
        link.section_id = ",".join(s.get("section_id", "") for s in sections)
        link.verification_status = "linked_unverified" if sections else "not_linked"
        link.notes = "Generated link only; human verification is required."
    record_event(db, actor, "document.generated", "document_version", version.id,
                 {"provider": response.provider, "model_id": response.model_id, "prompt_version": PROMPT_VERSION, "input_hash": digest})
    db.commit()
    return _serialize_document(db, doc, include_versions=True)


@router.post("/documents/{document_id}/sections/{section_id}/regenerate")
def regenerate_single_section(
    document_id: str,
    section_id: str,
    body: RegenerateSectionRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Regenerate a single document section using NVIDIA NIM without overwriting other approved sections."""
    _require_role(actor, "author", "admin")
    doc = _doc_or_404(db, document_id, actor)
    version = _current_version(db, doc)
    if version.status in {"in_review", "awaiting_approval", "released", "approved"}:
        raise HTTPException(status_code=409, detail="This revision is locked for review or has been released.")

    template = _template_for(doc)
    current_content = version.content or {}
    sec_title = section_id.replace("_", " ").title()

    for s in current_content.get("sections", []):
        if s.get("section_id") == section_id:
            sec_title = s.get("title", sec_title)
            break

    try:
        if version.provider == "openrouter" or (not settings.nvidia_api_key and settings.openrouter_api_key):
            provider = OpenRouterProvider()
            updated_sec = provider.regenerate_section(
                section_id=section_id,
                section_title=sec_title,
                template=template,
                answers=version.answers or {},
                current_content=current_content,
                user_guidance=body.guidance,
            )
        else:
            service = NvidiaService()
            updated_sec = service.regenerate_section(
                section_id=section_id,
                section_title=sec_title,
                template=template,
                answers=version.answers or {},
                current_content=current_content,
                user_guidance=body.guidance,
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Section regeneration failed: {exc}") from exc

    updated_content = TemplateMappingService.update_single_section(current_content, section_id, updated_sec)
    version.content = updated_content
    doc.updated_at = datetime.now(timezone.utc)
    _record_and_commit(db, actor, "document.section_regenerated", "document", doc.id, {"section_id": section_id})
    return _serialize_document(db, doc, include_versions=True)


@router.patch("/documents/{document_id}/sections/{section_id}")
def update_single_section_content(
    document_id: str,
    section_id: str,
    body: UpdateSectionContentRequest,
    db: Session = Depends(get_db),
    actor: dict = Depends(get_actor),
):
    """Update and save user edits to a specific document section."""
    _require_role(actor, "author", "admin")
    doc = _doc_or_404(db, document_id, actor)
    version = _current_version(db, doc)
    if version.status in {"in_review", "awaiting_approval", "released", "approved"}:
        raise HTTPException(status_code=409, detail="This revision is locked for review or has been released.")

    current_content = version.content or {}
    sec_title = body.title or section_id.replace("_", " ").title()
    updated_sec = GeneratedSection(
        section_id=section_id,
        title=sec_title,
        content=body.content,
        requirement_refs=body.requirement_refs or [],
        unresolved_items=body.unresolved_items or [],
    )
    updated_content = TemplateMappingService.update_single_section(current_content, section_id, updated_sec)
    version.content = updated_content
    doc.updated_at = datetime.now(timezone.utc)
    _record_and_commit(db, actor, "document.section_updated", "document", doc.id, {"section_id": section_id})
    return _serialize_document(db, doc, include_versions=True)



@router.post("/documents/{document_id}/submit-review")
def submit_review(document_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "author", "admin")
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc)
    if version.status != "generated" or not version.content:
        raise HTTPException(status_code=409, detail="Generate and verify a draft before submitting it for review.")
    if version.validation_status != "passed":
        raise HTTPException(status_code=409, detail="Validation is not passed or is stale.")
    version.status = "in_review"; doc.updated_at = datetime.now(timezone.utc)
    _record_and_commit(db, actor, "document.submitted_for_review", "document_version", version.id, {})
    return _serialize_document(db, doc, include_versions=True)


@router.post("/documents/{document_id}/review")
def review_document(document_id: str, body: ReviewRequest, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "reviewer", "admin")
    if body.decision not in {"accept", "changes_requested"}:
        raise HTTPException(status_code=422, detail="Decision must be accept or changes_requested.")
    if body.decision == "changes_requested" and not body.comments.strip():
        raise HTTPException(status_code=422, detail="Comments are required when requesting changes.")
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc)
    if version.status != "in_review":
        raise HTTPException(status_code=409, detail="This revision is not awaiting review.")
    if actor["email"].lower() == version.created_by.lower():
        raise HTTPException(status_code=403, detail="The author cannot review their own revision in this workflow.")
    db.add(ReviewDecision(document_version_id=version.id, reviewer_email=actor["email"], reviewer_role=actor["role"],
                          decision=body.decision, comments=body.comments.strip()))
    version.status = "awaiting_approval" if body.decision == "accept" else "changes_requested"; doc.updated_at = datetime.now(timezone.utc)
    _record_and_commit(db, actor, "document.reviewed", "document_version", version.id, {"decision": body.decision})
    return _serialize_document(db, doc, include_versions=True)


@router.post("/documents/{document_id}/approve")
def approve_document(document_id: str, body: ApproveRequest, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "approver", "admin")
    if body.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="Decision must be approve or reject.")
    if body.decision == "reject" and not body.comments.strip():
        raise HTTPException(status_code=422, detail="Comments are required when rejecting a document.")
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc)
    if version.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail="A reviewer must accept this revision before approval.")
    if actor["email"].lower() == version.created_by.lower():
        raise HTTPException(status_code=403, detail="The author cannot approve their own revision.")
    latest_review = db.query(ReviewDecision).filter_by(document_version_id=version.id).order_by(desc(ReviewDecision.created_at)).first()
    if latest_review and actor["email"].lower() == latest_review.reviewer_email.lower():
        raise HTTPException(status_code=403, detail="The approving identity must be different from the reviewing identity.")
    if body.decision == "approve":
        template = _template_for(doc)
        req_rows = db.query(RequirementReference).filter(RequirementReference.code.in_(template.get("requirements", []))).all()
        verified_codes = {r.code for r in req_rows if r.verification_status == "verified" and r.source_reference.strip() and r.source_edition.strip() and r.verification_note.strip()}
        unverified = sorted(set(template.get("requirements", [])) - verified_codes)
        if unverified:
            raise HTTPException(status_code=409, detail="Release is blocked until the requirement mappings are verified in the Requirements library: " + ", ".join(unverified))
    db.add(Approval(document_version_id=version.id, approver_email=actor["email"], approver_role=actor["role"],
                    decision=body.decision, comments=body.comments.strip()))
    version.status = "released" if body.decision == "approve" else "changes_requested"; doc.updated_at = datetime.now(timezone.utc)
    _record_and_commit(db, actor, "document.approval_decided", "document_version", version.id,
                       {"decision": body.decision, "revision": version.revision})
    return _serialize_document(db, doc, include_versions=True)


@router.post("/documents/{document_id}/new-revision", status_code=201)
def create_new_revision(document_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "author", "admin")
    doc = _doc_or_404(db, document_id, actor); old = _current_version(db, doc)
    if old.status != "released":
        raise HTTPException(status_code=409, detail="A new controlled revision can be created only from a released revision.")
    template = _template_for(doc)
    new = DocumentVersion(document_id=doc.id, revision=old.revision + 1, status="draft", answers=dict(old.answers or {}),
                          applicability=dict(old.applicability or {}), content={}, validation_status="not_run", created_by=actor["email"])
    db.add(new); db.flush(); doc.current_version_id = new.id; doc.updated_at = datetime.now(timezone.utc)
    for code in template.get("requirements", []):
        source = db.query(RequirementReference).filter_by(code=code).first()
        db.add(TraceabilityLink(document_version_id=new.id, requirement_code=code, **_trace_snapshot(source, code),
                                verification_status="not_verified", evidence_refs=[], notes=""))
    _record_and_commit(db, actor, "document.revision_created", "document_version", new.id, {"from_revision": old.revision, "revision": new.revision})
    return _serialize_document(db, doc, include_versions=True)


@router.get("/documents/{document_id}/traceability")
def document_traceability(document_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc)
    rows = db.query(TraceabilityLink).filter_by(document_version_id=version.id).all()
    result = []
    for link in rows:
        result.append({"id":link.id, "requirement_code":link.requirement_code, "title":link.source_title or link.requirement_code,
                       "source_name":link.source_name, "source_edition":link.source_edition,
                       "source_reference":link.source_reference, "summary":link.source_summary,
                       "source_verification_status":link.source_verification_status,
                       "source_verified_by":link.source_verified_by,
                       "source_verified_at":link.source_verified_at.isoformat() if link.source_verified_at else None,
                       "source_verification_note":link.source_verification_note,
                       "applicability":(version.applicability or {}).get(link.requirement_code, {"status":"pending","rationale":""}),
                       "section_id":link.section_id, "verification_status":link.verification_status,
                       "evidence_refs":link.evidence_refs or [], "notes":link.notes})
    return {"document_id":doc.id, "document_version_id":version.id, "revision":version.revision, "links":result}


@router.get("/documents/{document_id}/versions")
def document_versions(document_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    doc = _doc_or_404(db, document_id, actor)
    versions = db.query(DocumentVersion).filter_by(document_id=doc.id).order_by(desc(DocumentVersion.revision)).all()
    return [{"id":v.id, "revision":v.revision, "status":v.status, "created_by":v.created_by,
             "created_at":v.created_at.isoformat() if v.created_at else None,
             "generated_at":v.generated_at.isoformat() if v.generated_at else None,
             "provider":v.provider, "input_hash":v.input_hash} for v in versions]


ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".csv", ".xlsx", ".png", ".jpg", ".jpeg"}

@router.post("/documents/{document_id}/evidence", status_code=201)
async def upload_evidence(document_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "author", "admin")
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc)
    if version.status in {"in_review", "awaiting_approval", "released", "approved"}:
        raise HTTPException(status_code=409, detail="Evidence is locked during review or after release. Create a new revision if needed.")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported evidence file type. Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    body = await file.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds configured upload limit ({settings.max_upload_mb} MB).")
    storage_dir = (Path(settings.aiqms_storage_dir) / "evidence").resolve(); storage_dir.mkdir(parents=True, exist_ok=True)
    key = f"{uuid4().hex}{suffix}"; target = storage_dir / key
    target.write_bytes(body)
    checksum = hashlib.sha256(body).hexdigest()
    evidence = EvidenceFile(document_version_id=version.id, original_filename=Path(file.filename or "evidence").name[:255], storage_key=str(target),
                            mime_type=file.content_type or "application/octet-stream", size_bytes=len(body), checksum_sha256=checksum,
                            uploaded_by=actor["email"], classification="internal")
    db.add(evidence); db.flush(); version.validation_status = "not_run"; version.status = "draft"; version.content = {}; doc.updated_at = datetime.now(timezone.utc)
    record_event(db, actor, "evidence.uploaded", "evidence_file", evidence.id, {"filename": evidence.original_filename, "size_bytes": len(body), "sha256": checksum})
    db.commit(); db.refresh(evidence)
    return {"id":evidence.id, "filename":evidence.original_filename, "size_bytes":evidence.size_bytes, "checksum_sha256":checksum,
            "uploaded_at":evidence.uploaded_at.isoformat() if evidence.uploaded_at else None}


@router.get("/documents/{document_id}/evidence/{evidence_id}")
def download_evidence(document_id: str, evidence_id: str, db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc)
    evidence = db.query(EvidenceFile).filter_by(id=evidence_id, document_version_id=version.id).first()
    if not evidence or not Path(evidence.storage_key).is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found.")
    return StreamingResponse(open(evidence.storage_key, "rb"), media_type=evidence.mime_type,
                             headers={"Content-Disposition": f'attachment; filename="{evidence.original_filename.replace(chr(34), "")}"'})


@router.get("/documents/{document_id}/export")
def export_document(document_id: str, format: str = Query(default="docx", pattern="^(docx|pdf)$"),
                    db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    doc = _doc_or_404(db, document_id, actor); version = _current_version(db, doc)
    if not version.content:
        raise HTTPException(status_code=409, detail="Generate a draft before exporting.")
    if version.status != "released" and actor["role"] not in {"author", "reviewer", "approver", "admin"}:
        raise HTTPException(status_code=403, detail="Not authorized to export this draft.")
    if format == "docx":
        data = render_docx(doc, version, version.content); media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        data = render_pdf(doc, version, version.content); media = "application/pdf"
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{doc.document_number}_R{version.revision}_{'controlled' if version.status == 'released' else 'DRAFT'}") + f".{format}"
    record_event(db, actor, "document.exported", "document_version", version.id, {"format":format, "status":version.status}); db.commit()
    from io import BytesIO
    return StreamingResponse(BytesIO(data), media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/reviews/queue")
def review_queue(db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "reviewer", "approver", "admin")
    docs = db.query(Document).filter_by(organization_id=actor["organization_id"]).order_by(desc(Document.updated_at)).all()
    result = []
    for doc in docs:
        version = _current_version(db, doc)
        if (actor["role"] in {"reviewer", "admin"} and version.status == "in_review") or (actor["role"] in {"approver", "admin"} and version.status == "awaiting_approval"):
            result.append({"document_id":doc.id, "document_number":doc.document_number, "title":doc.title,
                           "revision":version.revision, "status":version.status, "created_by":version.created_by})
    return result


@router.get("/audit")
def audit_events(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), actor: dict = Depends(get_actor)):
    _require_role(actor, "admin", "reviewer", "approver")
    events = db.query(AuditEvent).filter_by(organization_id=actor["organization_id"]).order_by(desc(AuditEvent.created_at)).limit(limit).all()
    return [{"id":e.id, "actor_email":e.actor_email, "actor_role":e.actor_role, "action":e.action,
             "entity_type":e.entity_type, "entity_id":e.entity_id, "metadata":e.metadata_json,
             "created_at":e.created_at.isoformat() if e.created_at else None} for e in events]
