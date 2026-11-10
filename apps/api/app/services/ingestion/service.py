from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ingestion import (
    IngestedChunk,
    IngestedDocument,
    IngestedDocumentMetadata,
    IngestedSection,
    IngestionLog,
)
from app.services.ingestion.base import BaseDocumentExtractor, ExtractedDocument
from app.services.ingestion.chunking_engine import ChunkingEngine
from app.services.ingestion.docx_extractor import DocxExtractor
from app.services.ingestion.json_generator import JsonGenerator
from app.services.ingestion.metadata_extractor import MetadataExtractor
from app.services.ingestion.pdf_extractor import PdfExtractor
from app.services.ingestion.structure_extractor import StructureExtractor


class DocumentIngestionService:
    """Master orchestrator for the AIQMS Document Ingestion and Processing Engine."""

    ALLOWED_EXTENSIONS = {".docx", ".pdf"}
    MAGIC_SIGNATURES = {
        ".docx": [b"PK\x03\x04"],
        ".pdf": [b"%PDF"],
    }

    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.docx_extractor = DocxExtractor()
        self.pdf_extractor = PdfExtractor()
        self.metadata_extractor = MetadataExtractor()
        self.structure_extractor = StructureExtractor()
        self.chunking_engine = ChunkingEngine(max_chunk_chars=1200, overlap_chars=150)
        self.json_generator = JsonGenerator()

        # Configured storage directories
        self.storage_base = Path(settings.aiqms_storage_dir).resolve()
        self.upload_dir = self.storage_base / "ingested" / "original"
        self.json_dir = self.storage_base / "ingested" / "json"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, filename: str, content: bytes) -> tuple[bool, str, str]:
        """Validate file extension, size, and magic bytes.

        Returns (is_valid, file_format, error_detail).
        """
        raw_ext = Path(filename).suffix.lower()

        if raw_ext == ".xlsx":
            return False, "XLSX", "Spreadsheet format (.xlsx) will be supported in Milestone 3. Currently supported: .docx, .pdf"

        if raw_ext not in self.ALLOWED_EXTENSIONS:
            return False, "", f"Unsupported file extension '{raw_ext}'. Allowed formats: .docx, .pdf"

        max_bytes = settings.max_upload_mb * 1024 * 1024
        if len(content) > max_bytes:
            return False, raw_ext[1:].upper(), f"File size ({len(content) / (1024*1024):.2f} MB) exceeds maximum allowed limit ({settings.max_upload_mb} MB)."

        if len(content) == 0:
            return False, raw_ext[1:].upper(), "Uploaded file is empty (0 bytes)."

        # Validate magic signatures
        signatures = self.MAGIC_SIGNATURES.get(raw_ext, [])
        if signatures and not any(content.startswith(sig) for sig in signatures):
            return False, raw_ext[1:].upper(), f"File content does not match expected {raw_ext.upper()} magic byte signature (possible corruption or disguised file type)."

        return True, raw_ext[1:].upper(), ""

    async def ingest_uploaded_file(
        self,
        file: UploadFile,
        actor_email: str = "system",
        organization_id: str = "default",
    ) -> IngestedDocument:
        """Process an uploaded file through the complete ingestion pipeline."""
        original_filename = Path(file.filename or "document").name
        # Secure filename: strip dangerous traversal characters
        clean_filename = re.sub(r"[^A-Za-z0-9._\- ]+", "_", original_filename)

        content = await file.read()
        return self.ingest_bytes(
            filename=clean_filename,
            content=content,
            actor_email=actor_email,
            organization_id=organization_id,
        )

    def ingest_bytes(
        self,
        filename: str,
        content: bytes,
        actor_email: str = "system",
        organization_id: str = "default",
    ) -> IngestedDocument:
        """Process raw bytes through the ingestion pipeline."""
        now = datetime.now(timezone.utc)
        doc_id = f"DOC-{uuid4().hex[:8].upper()}"
        suffix = Path(filename).suffix.lower()

        is_valid, file_format, error_msg = self.validate_file(filename, content)

        checksum = hashlib.sha256(content).hexdigest() if content else ""
        storage_filename = f"{uuid4().hex}{suffix}"
        target_path = self.upload_dir / storage_filename

        # If invalid, record failed document record
        if not is_valid:
            doc_record = IngestedDocument(
                id=doc_id,
                organization_id=organization_id,
                original_filename=filename,
                file_format=file_format or "UNKNOWN",
                file_size_bytes=len(content),
                checksum_sha256=checksum,
                storage_path=str(target_path),
                upload_status="failed",
                processing_status="failed",
                extraction_status="failed",
                error_message=error_msg,
                uploaded_by=actor_email,
                created_at=now,
            )
            if self.db:
                self.db.add(doc_record)
                self.db.commit()
                self.db.refresh(doc_record)
            return doc_record

        # Safely store file on disk
        target_path.write_bytes(content)

        doc_record = IngestedDocument(
            id=doc_id,
            organization_id=organization_id,
            original_filename=filename,
            file_format=file_format,
            file_size_bytes=len(content),
            checksum_sha256=checksum,
            storage_path=str(target_path),
            upload_status="uploaded",
            processing_status="processing",
            extraction_status="not_started",
            uploaded_by=actor_email,
            created_at=now,
        )
        if self.db:
            self.db.add(doc_record)
            self.db.commit()
            self.db.refresh(doc_record)

        # Select extractor
        extractor: BaseDocumentExtractor
        if file_format == "DOCX":
            extractor = self.docx_extractor
        elif file_format == "PDF":
            extractor = self.pdf_extractor
        else:
            doc_record.processing_status = "failed"
            doc_record.error_message = f"Unsupported file format: {file_format}"
            if self.db:
                self.db.commit()
            return doc_record

        # Extract text and content
        extracted_doc: ExtractedDocument = extractor.extract(target_path)
        extracted_doc.filename = filename

        if extracted_doc.errors:
            doc_record.processing_status = "failed"
            doc_record.extraction_status = "failed"
            doc_record.error_message = "; ".join(extracted_doc.errors)
            doc_record.warnings_json = extracted_doc.warnings
            if self.db:
                self._record_log(doc_id, "extraction", "failed", doc_record.error_message)
                self.db.commit()
            return doc_record

        # Extract metadata
        metadata = self.metadata_extractor.extract_metadata(extracted_doc)

        # Extract structure and sections
        sections = self.structure_extractor.extract_structure(extracted_doc)

        # Generate chunks
        chunks = self.chunking_engine.create_chunks(
            document_id=doc_id,
            document_number=metadata.document_number,
            document_revision=metadata.revision,
            sections=sections,
        )

        # Generate schema-validated structured JSON
        proc_status = "ocr_required" if extracted_doc.ocr_required else "completed"
        ext_status = "partial" if extracted_doc.ocr_required else "success"

        json_data, is_valid, validation_errors = self.json_generator.generate(
            document_id=doc_id,
            extracted_doc=extracted_doc,
            metadata=metadata,
            sections=sections,
            chunks=chunks,
            processing_status=proc_status,
            extraction_status=ext_status,
        )

        # Save structured JSON
        json_file_path = self.json_dir / f"{doc_id}.json"
        self.json_generator.save_json(json_data, json_file_path)

        # Update database entities
        doc_record.total_pages = extracted_doc.total_pages
        doc_record.total_sections = len(sections)
        doc_record.total_chunks = len(chunks)
        doc_record.processing_status = proc_status
        doc_record.extraction_status = ext_status
        doc_record.ocr_required = extracted_doc.ocr_required
        doc_record.warnings_json = list(extracted_doc.warnings) + list(metadata.warnings)
        if validation_errors:
            doc_record.warnings_json.extend([f"JSON validation warning: {e}" for e in validation_errors])
        doc_record.processed_at = datetime.now(timezone.utc)

        if self.db:
            # Metadata entity
            meta_entity = IngestedDocumentMetadata(
                document_id=doc_id,
                document_title=metadata.document_title,
                document_number=metadata.document_number,
                revision_number=metadata.revision,
                effective_date=metadata.effective_date,
                review_date=metadata.review_date,
                department=metadata.department,
                document_owner=metadata.document_owner,
                prepared_by=metadata.prepared_by,
                reviewed_by=metadata.reviewed_by,
                approved_by=metadata.approved_by,
                purpose=metadata.purpose,
                scope=metadata.scope,
                responsibilities=metadata.responsibilities,
                confidence_scores=metadata.confidence_scores,
                source_snippets=metadata.source_snippets,
            )
            self.db.add(meta_entity)

            # Sections entities
            sec_entity_map: dict[str, IngestedSection] = {}
            for s in sections:
                sec_entity = IngestedSection(
                    id=s.section_id,
                    document_id=doc_id,
                    section_number=s.section_number,
                    section_title=s.section_title,
                    parent_section_id=s.parent_section_id,
                    section_order=s.section_order,
                    level=s.level,
                    content_text=s.content_text,
                    page_start=s.page_start,
                    page_end=s.page_end,
                )
                self.db.add(sec_entity)
                sec_entity_map[s.section_id] = sec_entity

            # Chunks entities
            for c in chunks:
                chunk_entity = IngestedChunk(
                    id=c.chunk_id,
                    document_id=doc_id,
                    section_id=c.section_id if c.section_id in sec_entity_map else None,
                    document_number=c.document_number,
                    document_revision=c.document_revision,
                    section_title=c.section_title,
                    section_number=c.section_number,
                    chunk_text=c.chunk_text,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    chunk_sequence=c.chunk_sequence,
                    character_count=c.character_count,
                    token_count_estimate=c.token_count_estimate,
                    extraction_status=c.extraction_status,
                    content_hash=c.content_hash,
                    metadata_json=c.metadata,
                )
                self.db.add(chunk_entity)

            self._record_log(doc_id, "ingestion", "success", f"Ingested {len(sections)} sections, {len(chunks)} chunks.")
            self.db.commit()
            self.db.refresh(doc_record)

        return doc_record

    def _record_log(self, doc_id: str, step: str, status: str, message: str) -> None:
        if self.db:
            log = IngestionLog(
                document_id=doc_id,
                step=step,
                status=status,
                message=message,
            )
            self.db.add(log)
