from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


def uid() -> str:
    return str(uuid4())


def doc_id_factory() -> str:
    return f"DOC-{uuid4().hex[:8].upper()}"


def chunk_id_factory() -> str:
    return f"CHK-{uuid4().hex[:8].upper()}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IngestedDocument(Base):
    __tablename__ = "ingested_documents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=doc_id_factory)
    organization_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    file_format: Mapped[str] = mapped_column(String(10), index=True)  # DOCX, PDF, XLSX (future)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    upload_status: Mapped[str] = mapped_column(String(30), default="uploaded")
    processing_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    extraction_status: Mapped[str] = mapped_column(String(30), default="not_started")
    ocr_required: Mapped[bool] = mapped_column(Boolean, default=False)
    total_pages: Mapped[int] = mapped_column(Integer, default=0)
    total_sections: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    vector_status: Mapped[str] = mapped_column(String(30), default="unindexed", index=True)
    vector_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    uploaded_by: Mapped[str] = mapped_column(String(240), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata_record: Mapped["IngestedDocumentMetadata | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    sections: Mapped[list["IngestedSection"]] = relationship(
        back_populates="document", order_by="IngestedSection.section_order", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["IngestedChunk"]] = relationship(
        back_populates="document", order_by="IngestedChunk.chunk_sequence", cascade="all, delete-orphan"
    )
    logs: Mapped[list["IngestionLog"]] = relationship(
        back_populates="document", order_by="IngestionLog.created_at", cascade="all, delete-orphan"
    )


class IngestedDocumentMetadata(Base):
    __tablename__ = "ingested_document_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("ingested_documents.id", ondelete="CASCADE"), unique=True, index=True
    )
    document_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    revision_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    document_owner: Mapped[str | None] = mapped_column(String(240), nullable=True)
    prepared_by: Mapped[str | None] = mapped_column(String(240), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(240), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(240), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    source_snippets: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    document: Mapped[IngestedDocument] = relationship(back_populates="metadata_record")


class IngestedSection(Base):
    __tablename__ = "ingested_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("ingested_documents.id", ondelete="CASCADE"), index=True
    )
    section_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    section_title: Mapped[str] = mapped_column(String(300))
    parent_section_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    section_order: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    content_text: Mapped[str] = mapped_column(Text, default="")
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[IngestedDocument] = relationship(back_populates="sections")


class IngestedChunk(Base):
    __tablename__ = "ingested_chunks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=chunk_id_factory)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("ingested_documents.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[str | None] = mapped_column(
        ForeignKey("ingested_sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    section_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_sequence: Mapped[int] = mapped_column(Integer, default=1)
    character_count: Mapped[int] = mapped_column(Integer, default=0)
    token_count_estimate: Mapped[int] = mapped_column(Integer, default=0)
    extraction_status: Mapped[str] = mapped_column(String(30), default="success")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    embedding_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    embedding_model: Mapped[str | None] = mapped_column(String(50), nullable=True, default="nomic-embed-text")
    embedding_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vector_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[IngestedDocument] = relationship(back_populates="chunks")


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("ingested_documents.id", ondelete="CASCADE"), index=True
    )
    step: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[IngestedDocument] = relationship(back_populates="logs")
