"""ISO 13485 Clause-to-QMS-Document Traceability Service.

Orchestrates:
- Semantic candidate evidence retrieval
- Exact provenance tracking (document, revision, section, page, chunk)
- Deterministic rules-based evidence validation
- Human review and approval workflow with role authorization gates
- Complete immutable audit trails
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.compliance import (
    ISOClause,
    ComplianceTraceabilityItem,
    ComplianceTraceabilityRun,
)
from app.models.ingestion import IngestedChunk, IngestedDocument
from app.services.compliance.rules_engine import (
    DeterministicTraceabilityRulesEngine,
    TraceabilityStatus,
    ValidationResult,
)
from app.services.embedding.ollama_embedder import OllamaEmbeddingClient
from app.services.vector_store.chroma_service import ChromaVectorStoreService

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TraceabilityService:
    """Master orchestrator for ISO 13485 compliance traceability and validation."""

    def __init__(
        self,
        db: Session,
        embedder: Optional[OllamaEmbeddingClient] = None,
        vector_store: Optional[ChromaVectorStoreService] = None,
        rules_engine: Optional[DeterministicTraceabilityRulesEngine] = None,
    ):
        self.db = db
        self.embedder = embedder or OllamaEmbeddingClient()
        self.vector_store = vector_store or ChromaVectorStoreService()
        self.rules_engine = rules_engine or DeterministicTraceabilityRulesEngine()

    def generate_candidate_mappings(
        self,
        document_id: str,
        actor_email: str = "system",
        similarity_threshold: float = 0.45,
    ) -> ComplianceTraceabilityRun:
        """Retrieve QMS chunks and ISO clauses, generate candidate mappings with exact provenance."""
        doc = self.db.query(IngestedDocument).filter_by(id=document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        # Ensure document chunks are indexed in ChromaDB
        if doc.vector_status != "indexed":
            from app.services.embedding.indexing_service import DocumentIndexingService
            indexing_svc = DocumentIndexingService(db=self.db, embedder=self.embedder, vector_store=self.vector_store)
            indexing_svc.index_document(doc.id)

        # Retrieve all authoritative ISO clauses
        clauses = self.db.query(ISOClause).order_by(ISOClause.clause_number).all()
        if not clauses:
            from app.services.compliance.iso_knowledge_service import ISOKnowledgeService
            iso_kb = ISOKnowledgeService(db=self.db)
            iso_kb.sync_iso_knowledge_base()
            clauses = self.db.query(ISOClause).order_by(ISOClause.clause_number).all()

        run = ComplianceTraceabilityRun(
            document_id=doc.id,
            standard="ISO 13485:2016",
            status="running",
            executed_by=actor_email,
            model_name="rules-engine-v1",
        )
        self.db.add(run)
        self.db.commit()

        not_mapped_count = 0
        evidence_identified_count = 0
        insufficient_evidence_count = 0

        # Retrieve chunks for this document
        doc_chunks = self.db.query(IngestedChunk).filter_by(document_id=doc.id).all()
        chunk_map = {c.id: c for c in doc_chunks}

        now_str = utcnow().isoformat()

        # Batch embed all clause queries at once for maximum performance and socket safety
        clause_queries = [
            f"ISO 13485:2016 Clause {clause.clause_number} {clause.title}: {clause.normative_text or clause.clause_text}"
            for clause in clauses
        ]
        query_vectors = self.embedder.embed_batch(clause_queries, prefix="search_query:")

        for idx, clause in enumerate(clauses):
            query_vector = query_vectors[idx]

            # Query ChromaDB collection for chunks of this document
            hits = self.vector_store.query(
                collection_name=ChromaVectorStoreService.COLLECTION_CHUNKS,
                query_embedding=query_vector,
                top_k=1,
                filter_dict={"document_id": doc.id},
            )

            best_hit = hits[0] if hits else None
            sim_score = best_hit["score"] if best_hit else 0.0

            if best_hit and sim_score >= similarity_threshold:
                chunk = chunk_map.get(best_hit["id"])
                meta = best_hit.get("metadata", {})
                
                doc_number = chunk.document_number if chunk and chunk.document_number else meta.get("document_number", doc.original_filename)
                doc_revision = chunk.document_revision if chunk and chunk.document_revision else meta.get("document_revision", "00")
                sec_number = chunk.section_number if chunk and chunk.section_number else meta.get("section_number")
                sec_title = chunk.section_title if chunk and chunk.section_title else meta.get("section_title")
                page_start = chunk.page_start if chunk and chunk.page_start else meta.get("page_start", 1)
                page_end = chunk.page_end if chunk and chunk.page_end else meta.get("page_end", page_start)
                evidence_text = chunk.chunk_text if chunk else best_hit.get("document", "")

                # Run deterministic rules validation on candidate
                validation = self.rules_engine.validate_mapping(
                    clause_number=clause.clause_number,
                    clause_title=clause.title,
                    requires_procedure=clause.requires_documented_procedure,
                    requires_record=clause.requires_record,
                    document_id=doc.id,
                    document_number=doc_number,
                    document_revision=doc_revision,
                    section_number=sec_number,
                    section_title=sec_title,
                    page_start=page_start,
                    evidence_excerpt=evidence_text,
                    current_status=TraceabilityStatus.EVIDENCE_IDENTIFIED,
                )

                if validation.passed:
                    status = TraceabilityStatus.EVIDENCE_IDENTIFIED
                    evidence_identified_count += 1
                else:
                    status = TraceabilityStatus.INSUFFICIENT_EVIDENCE
                    insufficient_evidence_count += 1

                item = ComplianceTraceabilityItem(
                    run_id=run.id,
                    clause_id=clause.id,
                    clause_number=clause.clause_number,
                    matched_chunk_id=chunk.id if chunk else best_hit["id"],
                    document_id=doc.id,
                    document_number=doc_number,
                    document_revision=doc_revision,
                    section_number=sec_number,
                    section_title=sec_title,
                    page_start=page_start,
                    page_end=page_end,
                    evidence_excerpt=evidence_text,
                    mapping_status=status,
                    mapping_confidence=round(sim_score, 4),
                    similarity_score=round(sim_score, 4),
                    rules_validation_status="passed" if validation.passed else "failed",
                    rules_findings=validation.to_dict(),
                    audit_trail=[
                        {
                            "timestamp": now_str,
                            "actor": actor_email,
                            "action": "candidate_evidence_identified",
                            "new_status": status,
                            "confidence": round(sim_score, 4),
                            "note": f"Matched section: {sec_title or sec_number}",
                        }
                    ],
                )
            else:
                # No candidate evidence in document
                not_mapped_count += 1
                item = ComplianceTraceabilityItem(
                    run_id=run.id,
                    clause_id=clause.id,
                    clause_number=clause.clause_number,
                    matched_chunk_id=None,
                    document_id=doc.id,
                    document_number=None,
                    document_revision=None,
                    section_number=None,
                    section_title=None,
                    page_start=None,
                    page_end=None,
                    evidence_excerpt=None,
                    mapping_status=TraceabilityStatus.NOT_MAPPED,
                    mapping_confidence=0.0,
                    similarity_score=round(sim_score, 4),
                    rules_validation_status="unvalidated",
                    rules_findings={
                        "passed": False,
                        "status": TraceabilityStatus.NOT_MAPPED,
                        "findings": [
                            {
                                "code": "NO_CANDIDATE_EVIDENCE",
                                "severity": "info",
                                "rule_name": "Evidence Identification",
                                "message": f"No candidate sections found in {doc.original_filename} exceeding similarity threshold {similarity_threshold}.",
                                "field_path": "evidence_excerpt",
                            }
                        ],
                    },
                    audit_trail=[
                        {
                            "timestamp": now_str,
                            "actor": actor_email,
                            "action": "unmapped_clause_recorded",
                            "new_status": TraceabilityStatus.NOT_MAPPED,
                        }
                    ],
                )

            self.db.add(item)

        # Update run summary
        run.status = "completed"
        run.completed_at = utcnow()
        run.total_clauses_evaluated = len(clauses)
        run.not_mapped_count = not_mapped_count
        run.evidence_identified_count = evidence_identified_count
        run.insufficient_evidence_count = insufficient_evidence_count
        run.pending_review_count = 0
        run.verified_count = 0
        run.not_applicable_count = 0
        self.db.commit()

        logger.info(
            "Traceability run %s completed: %d identified, %d insufficient, %d not mapped.",
            run.id,
            evidence_identified_count,
            insufficient_evidence_count,
            not_mapped_count,
        )
        return run

    def validate_item_rules(self, item_id: str) -> ValidationResult:
        """Run deterministic rules engine on a specific traceability item."""
        item = self.db.query(ComplianceTraceabilityItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"Traceability item {item_id} not found.")

        clause = self.db.query(ISOClause).filter_by(clause_number=item.clause_number).first()
        req_proc = clause.requires_documented_procedure if clause else False
        req_rec = clause.requires_record if clause else False
        title = clause.title if clause else item.clause_number

        result = self.rules_engine.validate_mapping(
            clause_number=item.clause_number,
            clause_title=title,
            requires_procedure=req_proc,
            requires_record=req_rec,
            document_id=item.document_id,
            document_number=item.document_number,
            document_revision=item.document_revision,
            section_number=item.section_number,
            section_title=item.section_title,
            page_start=item.page_start,
            evidence_excerpt=item.evidence_excerpt,
            current_status=item.mapping_status,
            na_justification=item.na_justification,
            reviewer_role=None,
            is_verified_requested=False,
        )

        item.rules_validation_status = "passed" if result.passed else "failed"
        item.rules_findings = result.to_dict()
        self.db.commit()
        return result

    def submit_for_review(self, item_id: str, actor_email: str) -> ComplianceTraceabilityItem:
        """Transition mapping item to 'Pending review' state."""
        item = self.db.query(ComplianceTraceabilityItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"Traceability item {item_id} not found.")

        if item.mapping_status not in [TraceabilityStatus.EVIDENCE_IDENTIFIED, TraceabilityStatus.INSUFFICIENT_EVIDENCE]:
            raise ValueError(f"Cannot submit item with status '{item.mapping_status}' for review.")

        # Run validation before submitting
        validation = self.validate_item_rules(item_id)
        if validation.has_critical_findings:
            raise ValueError("Cannot submit for review while critical rule findings remain unresolved.")

        item.mapping_status = TraceabilityStatus.PENDING_REVIEW
        trail = list(item.audit_trail or [])
        trail.append(
            {
                "timestamp": utcnow().isoformat(),
                "actor": actor_email,
                "action": "submitted_for_review",
                "new_status": TraceabilityStatus.PENDING_REVIEW,
            }
        )
        item.audit_trail = trail
        self.db.commit()
        return item

    def review_mapping(
        self,
        item_id: str,
        decision: str,  # "verified", "changes_requested", "rejected"
        comment: str,
        actor_role: str,
        actor_email: str,
        author_email: Optional[str] = None,
    ) -> ComplianceTraceabilityItem:
        """Human reviewer decision recording with strict role authorization and separation of duties."""
        item = self.db.query(ComplianceTraceabilityItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"Traceability item {item_id} not found.")

        clause = self.db.query(ISOClause).filter_by(clause_number=item.clause_number).first()
        req_proc = clause.requires_documented_procedure if clause else False
        req_rec = clause.requires_record if clause else False
        title = clause.title if clause else item.clause_number

        now_str = utcnow().isoformat()

        if decision == "verified":
            # Run deterministic rules with verification checks
            validation = self.rules_engine.validate_mapping(
                clause_number=item.clause_number,
                clause_title=title,
                requires_procedure=req_proc,
                requires_record=req_rec,
                document_id=item.document_id,
                document_number=item.document_number,
                document_revision=item.document_revision,
                section_number=item.section_number,
                section_title=item.section_title,
                page_start=item.page_start,
                evidence_excerpt=item.evidence_excerpt,
                current_status=item.mapping_status,
                reviewer_role=actor_role,
                reviewer_email=actor_email,
                author_email=author_email,
                is_verified_requested=True,
            )

            if not validation.passed:
                first_blocking = next((f.message for f in validation.findings if f.severity in ["critical", "major"]), "Validation failed")
                raise ValueError(f"Verification blocked by rules engine: {first_blocking}")

            item.mapping_status = TraceabilityStatus.VERIFIED_BY_REVIEWER
            item.rules_validation_status = "passed"
            item.rules_findings = validation.to_dict()
        else:
            # Changes requested or rejected
            item.mapping_status = TraceabilityStatus.INSUFFICIENT_EVIDENCE
            item.rules_validation_status = "failed"

        item.reviewed_by = actor_email
        item.reviewed_at = utcnow()
        item.reviewer_decision = decision
        item.reviewer_comment = comment

        trail = list(item.audit_trail or [])
        trail.append(
            {
                "timestamp": now_str,
                "actor": actor_email,
                "role": actor_role,
                "action": f"reviewer_{decision}",
                "new_status": item.mapping_status,
                "comment": comment,
            }
        )
        item.audit_trail = trail
        self.db.commit()
        return item

    def set_not_applicable(
        self,
        item_id: str,
        justification: str,
        actor_email: str,
    ) -> ComplianceTraceabilityItem:
        """Mark a clause as Not Applicable with documented justification."""
        item = self.db.query(ComplianceTraceabilityItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"Traceability item {item_id} not found.")

        clause = self.db.query(ISOClause).filter_by(clause_number=item.clause_number).first()
        title = clause.title if clause else item.clause_number

        validation = self.rules_engine.validate_mapping(
            clause_number=item.clause_number,
            clause_title=title,
            requires_procedure=False,
            requires_record=False,
            current_status=TraceabilityStatus.NOT_APPLICABLE,
            na_justification=justification,
        )

        if not validation.passed:
            first_err = next((f.message for f in validation.findings if f.severity == "critical"), "Invalid exclusion")
            raise ValueError(f"Not-Applicable justification rejected: {first_err}")

        item.mapping_status = TraceabilityStatus.NOT_APPLICABLE
        item.na_justification = justification
        item.rules_validation_status = "passed"
        item.rules_findings = validation.to_dict()

        trail = list(item.audit_trail or [])
        trail.append(
            {
                "timestamp": utcnow().isoformat(),
                "actor": actor_email,
                "action": "marked_not_applicable",
                "new_status": TraceabilityStatus.NOT_APPLICABLE,
                "justification": justification,
            }
        )
        item.audit_trail = trail
        self.db.commit()
        return item

    def manual_map_chunk(
        self,
        item_id: str,
        chunk_id: str,
        actor_email: str,
    ) -> ComplianceTraceabilityItem:
        """Manually link a specific chunk as evidence for a clause."""
        item = self.db.query(ComplianceTraceabilityItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"Traceability item {item_id} not found.")

        chunk = self.db.query(IngestedChunk).filter_by(id=chunk_id).first()
        if not chunk:
            raise ValueError(f"Chunk {chunk_id} not found.")

        item.matched_chunk_id = chunk.id
        item.document_id = chunk.document_id
        item.document_number = chunk.document_number
        item.document_revision = chunk.document_revision
        item.section_number = chunk.section_number
        item.section_title = chunk.section_title
        item.page_start = chunk.page_start
        item.page_end = chunk.page_end
        item.evidence_excerpt = chunk.chunk_text
        item.mapping_status = TraceabilityStatus.EVIDENCE_IDENTIFIED
        item.mapping_confidence = 1.0  # Manual link by human

        # Validate with rules engine
        validation = self.validate_item_rules(item_id)
        if not validation.passed:
            item.mapping_status = TraceabilityStatus.INSUFFICIENT_EVIDENCE

        trail = list(item.audit_trail or [])
        trail.append(
            {
                "timestamp": utcnow().isoformat(),
                "actor": actor_email,
                "action": "manual_chunk_linked",
                "chunk_id": chunk.id,
                "new_status": item.mapping_status,
            }
        )
        item.audit_trail = trail
        self.db.commit()
        return item

    def get_traceability_matrix(self, document_id: str) -> Dict[str, Any]:
        """Retrieve the latest ISO 13485 traceability matrix for an ingested document."""
        doc = self.db.query(IngestedDocument).filter_by(id=document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        run = (
            self.db.query(ComplianceTraceabilityRun)
            .filter_by(document_id=document_id)
            .order_by(ComplianceTraceabilityRun.created_at.desc())
            .first()
        )
        if not run:
            return {
                "document_id": document_id,
                "document_name": doc.original_filename,
                "has_run": False,
                "run_id": None,
                "status": "not_started",
                "total_clauses": 88,
                "metrics": {
                    "verified": 0,
                    "evidence_identified": 0,
                    "pending_review": 0,
                    "insufficient_evidence": 0,
                    "not_mapped": 88,
                    "not_applicable": 0,
                },
                "items": [],
            }

        items = (
            self.db.query(ComplianceTraceabilityItem)
            .filter_by(run_id=run.id)
            .order_by(ComplianceTraceabilityItem.clause_number)
            .all()
        )

        clauses = self.db.query(ISOClause).all()
        clause_map = {c.clause_number: c for c in clauses}

        items_data = []
        for itm in items:
            cl = clause_map.get(itm.clause_number)
            items_data.append({
                "id": itm.id,
                "run_id": itm.run_id,
                "clause_number": itm.clause_number,
                "clause_title": cl.title if cl else itm.clause_number,
                "category": cl.category if cl else "General",
                "requires_procedure": cl.requires_documented_procedure if cl else False,
                "requires_record": cl.requires_record if cl else False,
                "normative_text": cl.normative_text if cl else "",
                "mapping_status": itm.mapping_status,
                "mapping_confidence": itm.mapping_confidence,
                "matched_chunk_id": itm.matched_chunk_id,
                "document_id": itm.document_id,
                "document_number": itm.document_number,
                "document_revision": itm.document_revision,
                "section_number": itm.section_number,
                "section_title": itm.section_title,
                "page_start": itm.page_start,
                "page_end": itm.page_end,
                "evidence_excerpt": itm.evidence_excerpt,
                "rules_validation_status": itm.rules_validation_status,
                "rules_findings": itm.rules_findings,
                "reviewed_by": itm.reviewed_by,
                "reviewed_at": itm.reviewed_at.isoformat() if itm.reviewed_at else None,
                "reviewer_decision": itm.reviewer_decision,
                "reviewer_comment": itm.reviewer_comment,
                "na_justification": itm.na_justification,
                "audit_trail": itm.audit_trail or [],
                "verdict": itm.verdict or "not_addressed",
                "ai_reasoning": itm.ai_reasoning,
                "reasoning": itm.ai_reasoning or "",
            })

        return {
            "document_id": doc.id,
            "document_name": doc.original_filename,
            "has_run": True,
            "run_id": run.id,
            "status": run.status,
            "standard": run.standard,
            "total_clauses": run.total_clauses_evaluated,
            "metrics": {
                "verified": run.verified_count,
                "evidence_identified": run.evidence_identified_count,
                "pending_review": run.pending_review_count,
                "insufficient_evidence": run.insufficient_evidence_count,
                "not_mapped": run.not_mapped_count,
                "not_applicable": run.not_applicable_count,
            },
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "items": items_data,
        }

