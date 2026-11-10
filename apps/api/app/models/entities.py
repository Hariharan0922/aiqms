from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


def uid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    document_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    document_type: Mapped[str] = mapped_column(String(80), index=True)
    template_id: Mapped[str] = mapped_column(String(100))
    template_version: Mapped[str] = mapped_column(String(30), default="1.0.0")
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document", foreign_keys="DocumentVersion.document_id", cascade="all, delete-orphan")


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "revision", name="uq_document_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    applicability: Mapped[dict] = mapped_column(JSON, default=dict)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_status: Mapped[str] = mapped_column(String(30), default="not_run")
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document: Mapped[Document] = relationship(back_populates="versions", foreign_keys=[document_id])


class ValidationRun(Base):
    __tablename__ = "validation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    ruleset_version: Mapped[str] = mapped_column(String(30))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    reviewer_email: Mapped[str] = mapped_column(String(240))
    reviewer_role: Mapped[str] = mapped_column(String(40))
    decision: Mapped[str] = mapped_column(String(40))
    comments: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    approver_email: Mapped[str] = mapped_column(String(240))
    approver_role: Mapped[str] = mapped_column(String(40))
    decision: Mapped[str] = mapped_column(String(40))
    comments: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TraceabilityLink(Base):
    __tablename__ = "traceability_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    requirement_code: Mapped[str] = mapped_column(String(100), index=True)
    # Snapshot the source mapping per document version so later library edits cannot rewrite history.
    source_title: Mapped[str] = mapped_column(String(240), default="")
    source_name: Mapped[str] = mapped_column(String(240), default="")
    source_edition: Mapped[str] = mapped_column(String(80), default="")
    source_reference: Mapped[str] = mapped_column(String(160), default="")
    source_summary: Mapped[str] = mapped_column(Text, default="")
    source_verification_status: Mapped[str] = mapped_column(String(40), default="requires_verification")
    source_verified_by: Mapped[str | None] = mapped_column(String(240), nullable=True)
    source_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_verification_note: Mapped[str] = mapped_column(Text, default="")
    section_id: Mapped[str] = mapped_column(String(120), default="")
    verification_status: Mapped[str] = mapped_column(String(40), default="not_verified")
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    actor_email: Mapped[str] = mapped_column(String(240))
    actor_role: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RequirementReference(Base):
    __tablename__ = "requirement_references"
    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(240))
    source_name: Mapped[str] = mapped_column(String(240), default="")
    source_edition: Mapped[str] = mapped_column(String(80), default="")
    source_reference: Mapped[str] = mapped_column(String(160), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    verification_status: Mapped[str] = mapped_column(String(40), default="requires_verification")
    verified_by: Mapped[str | None] = mapped_column(String(240), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_note: Mapped[str] = mapped_column(Text, default="")


class EvidenceFile(Base):
    __tablename__ = "evidence_files"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str] = mapped_column(String(240))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    classification: Mapped[str] = mapped_column(String(40), default="internal")
