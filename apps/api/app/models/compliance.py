from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


def uid() -> str:
    return str(uuid4())


def run_id_factory() -> str:
    return f"RUN-{uuid4().hex[:8].upper()}"


def item_id_factory() -> str:
    return f"ITM-{uuid4().hex[:8].upper()}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ISOClause(Base):
    __tablename__ = "iso_clauses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g. "ISO-13485-4.2.4"
    standard: Mapped[str] = mapped_column(String(50), default="ISO 13485:2016", index=True)
    clause_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # "4.2.4"
    parent_clause_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)  # "4.2"
    level: Mapped[int] = mapped_column(Integer, default=1, index=True)  # 1 for '4', 2 for '4.2', 3 for '4.2.4'
    title: Mapped[str] = mapped_column(String(300))  # "Control of records"
    clause_text: Mapped[str] = mapped_column(Text)  # Complete verbatim ISO 13485 clause text
    normative_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Core requirement text without notes
    explanatory_notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # Explanatory NOTE sections
    is_normative: Mapped[bool] = mapped_column(Boolean, default=True)
    summary_requirements: Mapped[str] = mapped_column(Text)  # Key mandatory requirements summary
    requires_documented_procedure: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_record: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(100), default="General", index=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subclauses_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    embedding_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    vector_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ComplianceTraceabilityRun(Base):
    __tablename__ = "compliance_traceability_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=run_id_factory)
    document_id: Mapped[str] = mapped_column(ForeignKey("ingested_documents.id", ondelete="CASCADE"), index=True)
    standard: Mapped[str] = mapped_column(String(50), default="ISO 13485:2016")
    status: Mapped[str] = mapped_column(String(30), default="running")  # running, completed, failed
    overall_compliance_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 100.0%
    total_clauses_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    not_mapped_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_identified_count: Mapped[int] = mapped_column(Integer, default=0)
    pending_review_count: Mapped[int] = mapped_column(Integer, default=0)
    verified_count: Mapped[int] = mapped_column(Integer, default=0)
    insufficient_evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    not_applicable_count: Mapped[int] = mapped_column(Integer, default=0)
    compliant_count: Mapped[int] = mapped_column(Integer, default=0)
    partial_count: Mapped[int] = mapped_column(Integer, default=0)
    gap_count: Mapped[int] = mapped_column(Integer, default=0)
    summary_findings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_name: Mapped[str] = mapped_column(String(50), default="qwen3:4b")
    executed_by: Mapped[str] = mapped_column(String(240), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["ComplianceTraceabilityItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ComplianceTraceabilityItem.clause_number"
    )


class ComplianceTraceabilityItem(Base):
    __tablename__ = "compliance_traceability_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=item_id_factory)
    run_id: Mapped[str] = mapped_column(ForeignKey("compliance_traceability_runs.id", ondelete="CASCADE"), index=True)
    clause_id: Mapped[str] = mapped_column(ForeignKey("iso_clauses.id"), index=True)
    clause_number: Mapped[str] = mapped_column(String(30), index=True)
    matched_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("ingested_chunks.id", ondelete="SET NULL"), nullable=True)
    
    # Exact source document provenance
    document_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    section_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Canonical Traceability Statuses:
    # 'not_mapped', 'evidence_identified', 'pending_review', 'verified_by_reviewer', 'insufficient_evidence', 'not_applicable'
    mapping_status: Mapped[str] = mapped_column(String(50), default="not_mapped", index=True)
    mapping_confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 1.0 confidence
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Deterministic rules-based validation findings
    rules_validation_status: Mapped[str] = mapped_column(String(50), default="unvalidated")  # passed, failed, warning
    rules_findings: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Human Review Workflow
    reviewed_by: Mapped[str | None] = mapped_column(String(240), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)  # verified, rejected, changes_requested
    reviewer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    na_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Audit trail
    audit_trail: Mapped[list] = mapped_column(JSON, default=list)

    # Advisory evaluation fields
    verdict: Mapped[str] = mapped_column(String(30), default="not_addressed")  # compliant, partially_compliant, gap_detected, not_addressed
    ai_reasoning: Mapped[str] = mapped_column(Text, default="")
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    gap_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="major")  # critical, major, minor, info
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[ComplianceTraceabilityRun] = relationship(back_populates="items")
