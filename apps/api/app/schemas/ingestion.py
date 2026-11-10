from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
try:
    import jsonschema
except ImportError:
    jsonschema = None


class DocumentUploadItemResponse(BaseModel):
    document_id: str
    original_filename: str
    file_format: str
    upload_status: str
    upload_timestamp: str
    processing_status: str
    warnings: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UploadDocumentsResponse(BaseModel):
    total_uploaded: int
    successful: int
    failed: int
    documents: list[DocumentUploadItemResponse]


class DocumentMetadataSchema(BaseModel):
    document_title: Optional[str] = None
    document_number: Optional[str] = None
    revision: Optional[str] = None
    effective_date: Optional[str] = None
    review_date: Optional[str] = None
    department: Optional[str] = None
    document_owner: Optional[str] = None
    prepared_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None
    responsibilities: Optional[str] = None
    confidence_scores: dict[str, float] = Field(default_factory=dict)
    source_snippets: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class DocumentSectionSchema(BaseModel):
    section_id: str
    section_number: Optional[str] = None
    section_title: str
    parent_section_id: Optional[str] = None
    level: int = 1
    section_order: int = 0
    content_text: str = ""
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    subsections: list["DocumentSectionSchema"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkSchema(BaseModel):
    chunk_id: str
    document_id: str
    document_number: Optional[str] = None
    document_revision: Optional[str] = None
    section_title: Optional[str] = None
    section_number: Optional[str] = None
    chunk_text: str
    page_number: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    chunk_sequence: int = 1
    character_count: int = 0
    token_count_estimate: int = 0
    extraction_status: str = "success"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class StructuredDocumentOutput(BaseModel):
    document_id: str
    filename: str
    format: str
    metadata: DocumentMetadataSchema
    sections: list[DocumentSectionSchema] = Field(default_factory=list)
    chunks: list[DocumentChunkSchema] = Field(default_factory=list)
    processing_status: str = "completed"
    extraction_status: str = "success"
    ocr_required: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    extracted_at: str

    model_config = ConfigDict(from_attributes=True)


# Official JSON Schema for validating generated structured JSON output
STRUCTURED_OUTPUT_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "AIQMSStructuredDocumentOutput",
    "type": "object",
    "required": [
        "document_id",
        "filename",
        "format",
        "metadata",
        "sections",
        "chunks",
        "processing_status",
        "warnings"
    ],
    "properties": {
        "document_id": {"type": "string"},
        "filename": {"type": "string"},
        "format": {"type": "string", "enum": ["DOCX", "PDF", "XLSX"]},
        "metadata": {
            "type": "object",
            "properties": {
                "document_title": {"type": ["string", "null"]},
                "document_number": {"type": ["string", "null"]},
                "revision": {"type": ["string", "null"]},
                "effective_date": {"type": ["string", "null"]},
                "review_date": {"type": ["string", "null"]},
                "department": {"type": ["string", "null"]},
                "document_owner": {"type": ["string", "null"]},
                "prepared_by": {"type": ["string", "null"]},
                "reviewed_by": {"type": ["string", "null"]},
                "approved_by": {"type": ["string", "null"]},
                "purpose": {"type": ["string", "null"]},
                "scope": {"type": ["string", "null"]},
                "responsibilities": {"type": ["string", "null"]},
                "confidence_scores": {"type": "object"},
                "source_snippets": {"type": "object"}
            },
            "required": ["document_title", "document_number", "revision", "effective_date"]
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["section_id", "section_title", "section_order"],
                "properties": {
                    "section_id": {"type": "string"},
                    "section_number": {"type": ["string", "null"]},
                    "section_title": {"type": "string"},
                    "parent_section_id": {"type": ["string", "null"]},
                    "level": {"type": "integer"},
                    "section_order": {"type": "integer"},
                    "content_text": {"type": "string"},
                    "page_start": {"type": ["integer", "null"]},
                    "page_end": {"type": ["integer", "null"]}
                }
            }
        },
        "chunks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["chunk_id", "document_id", "chunk_text", "chunk_sequence", "character_count"],
                "properties": {
                    "chunk_id": {"type": "string"},
                    "document_id": {"type": "string"},
                    "document_number": {"type": ["string", "null"]},
                    "document_revision": {"type": ["string", "null"]},
                    "section_title": {"type": ["string", "null"]},
                    "section_number": {"type": ["string", "null"]},
                    "chunk_text": {"type": "string"},
                    "page_number": {"type": ["integer", "null"]},
                    "page_start": {"type": ["integer", "null"]},
                    "page_end": {"type": ["integer", "null"]},
                    "chunk_sequence": {"type": "integer"},
                    "character_count": {"type": "integer"},
                    "token_count_estimate": {"type": "integer"},
                    "extraction_status": {"type": "string"},
                    "metadata": {"type": "object"}
                }
            }
        },
        "processing_status": {"type": "string"},
        "extraction_status": {"type": "string"},
        "ocr_required": {"type": "boolean"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "errors": {"type": "array", "items": {"type": "string"}},
        "extracted_at": {"type": "string"}
    }
}


def validate_structured_json(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate data against the official structured output JSON schema."""
    if jsonschema is not None:
        validator = jsonschema.Draft7Validator(STRUCTURED_OUTPUT_JSON_SCHEMA)
        errors = [e.message for e in validator.iter_errors(data)]
        return len(errors) == 0, errors
    return True, []
