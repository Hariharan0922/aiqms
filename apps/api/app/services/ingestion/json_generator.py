from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Optional

from app.schemas.ingestion import (
    DocumentChunkSchema,
    DocumentMetadataSchema,
    DocumentSectionSchema,
    StructuredDocumentOutput,
    validate_structured_json,
)
from app.services.ingestion.base import ExtractedDocument
from app.services.ingestion.chunking_engine import DocumentChunk
from app.services.ingestion.metadata_extractor import MetadataExtractionResult
from app.services.ingestion.structure_extractor import ExtractedSection


class JsonGenerator:
    """Generates schema-validated structured JSON output for ingested documents."""

    def generate(
        self,
        document_id: str,
        extracted_doc: ExtractedDocument,
        metadata: MetadataExtractionResult,
        sections: list[ExtractedSection],
        chunks: list[DocumentChunk],
        processing_status: str = "completed",
        extraction_status: str = "success",
    ) -> tuple[dict[str, Any], bool, list[str]]:
        now_iso = datetime.now(timezone.utc).isoformat()

        meta_schema = DocumentMetadataSchema(
            document_title=metadata.document_title,
            document_number=metadata.document_number,
            revision=metadata.revision,
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

        section_schemas = [
            DocumentSectionSchema(
                section_id=s.section_id,
                section_number=s.section_number,
                section_title=s.section_title,
                parent_section_id=s.parent_section_id,
                level=s.level,
                section_order=s.section_order,
                content_text=s.content_text,
                page_start=s.page_start,
                page_end=s.page_end,
                subsections=[],
            )
            for s in sections
        ]

        chunk_schemas = [
            DocumentChunkSchema(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_number=c.document_number,
                document_revision=c.document_revision,
                section_title=c.section_title,
                section_number=c.section_number,
                chunk_text=c.chunk_text,
                page_number=c.page_number,
                page_start=c.page_start,
                page_end=c.page_end,
                chunk_sequence=c.chunk_sequence,
                character_count=c.character_count,
                token_count_estimate=c.token_count_estimate,
                extraction_status=c.extraction_status,
                metadata=c.metadata,
            )
            for c in chunks
        ]

        all_warnings = list(extracted_doc.warnings) + list(metadata.warnings)
        all_errors = list(extracted_doc.errors)

        output = StructuredDocumentOutput(
            document_id=document_id,
            filename=extracted_doc.filename,
            format=extracted_doc.file_format,
            metadata=meta_schema,
            sections=section_schemas,
            chunks=chunk_schemas,
            processing_status=processing_status,
            extraction_status=extraction_status,
            ocr_required=extracted_doc.ocr_required,
            warnings=all_warnings,
            errors=all_errors,
            extracted_at=now_iso,
        )

        data = output.model_dump()
        is_valid, validation_errors = validate_structured_json(data)

        return data, is_valid, validation_errors

    def save_json(self, data: dict[str, Any], output_path: Path) -> Path:
        """Save structured JSON to storage path."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return output_path
