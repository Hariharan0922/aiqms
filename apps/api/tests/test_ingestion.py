import io
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import docx

from app.main import app
from app.db.session import Base, engine, SessionLocal
from app.models.ingestion import IngestedDocument, IngestedDocumentMetadata, IngestedSection, IngestedChunk
from app.services.ingestion.docx_extractor import DocxExtractor
from app.services.ingestion.pdf_extractor import PdfExtractor
from app.services.ingestion.metadata_extractor import MetadataExtractor
from app.services.ingestion.structure_extractor import StructureExtractor
from app.services.ingestion.chunking_engine import ChunkingEngine
from app.services.ingestion.service import DocumentIngestionService
from app.schemas.ingestion import validate_structured_json, STRUCTURED_OUTPUT_JSON_SCHEMA


SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sample_documents"


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(role="author"):
    return {
        "X-Actor-Role": role,
        "X-Actor-Email": f"demo.{role}@example.local",
        "X-Organization-Id": "demo-org",
    }


# ============================================================================
# CATEGORY 1: UNIT TESTS
# ============================================================================

def test_unit_docx_text_extraction(tmp_path):
    """Test 1: DOCX text extraction accurately captures paragraphs and styles."""
    doc_path = tmp_path / "test_doc.docx"
    doc = docx.Document()
    doc.add_heading("1.0 Scope", level=1)
    doc.add_paragraph("This is a test paragraph for extraction verification.")
    doc.add_paragraph("Second paragraph with detailed technical specifications.")
    doc.save(doc_path)

    extractor = DocxExtractor()
    extracted = extractor.extract(doc_path)
    assert len(extracted.errors) == 0
    assert len(extracted.paragraphs) >= 3
    texts = [p.text for p in extracted.paragraphs]
    assert "1.0 Scope" in texts
    assert "This is a test paragraph for extraction verification." in texts


def test_unit_pdf_text_extraction():
    """Test 2: PDF text extraction extracts text from digital PDF."""
    pdf_path = SAMPLE_DOCS_DIR / "ISO-13485-2016-EN.pdf"
    assert pdf_path.exists(), "Sample ISO PDF file must exist"

    extractor = PdfExtractor()
    extracted = extractor.extract(pdf_path)
    assert len(extracted.errors) == 0
    assert extracted.total_pages == 44
    assert len(extracted.paragraphs) > 50
    assert "ISO 13485" in extracted.raw_text


def test_unit_docx_table_extraction(tmp_path):
    """Test 3: DOCX table extraction extracts headers, rows, and cells."""
    doc_path = tmp_path / "test_table.docx"
    doc = docx.Document()
    doc.add_paragraph("Procedure Table")
    table = doc.add_table(rows=3, cols=3)
    headers = ["Step", "Action", "Acceptance Criteria"]
    for i, h in enumerate(headers):
        table.cell(0, i).text = h
    row1 = ["1", "Power On", "Green LED illuminates"]
    for i, val in enumerate(row1):
        table.cell(1, i).text = val
    row2 = ["2", "Prime Line", "No air bubbles detected"]
    for i, val in enumerate(row2):
        table.cell(2, i).text = val
    doc.save(doc_path)

    extractor = DocxExtractor()
    extracted = extractor.extract(doc_path)
    assert len(extracted.tables) == 1
    t = extracted.tables[0]
    assert t.headers == ["Step", "Action", "Acceptance Criteria"]
    assert len(t.rows) == 2
    assert t.rows[0][1] == "Power On"


def test_unit_pdf_page_extraction():
    """Test 4: PDF page extraction maintains page references."""
    pdf_path = SAMPLE_DOCS_DIR / "ISO-13485-2016-EN.pdf"
    extractor = PdfExtractor()
    extracted = extractor.extract(pdf_path)
    assert 1 in extracted.page_texts
    assert 44 in extracted.page_texts
    # Verify paragraphs have page numbers
    page_nums = {p.page_number for p in extracted.paragraphs if p.page_number is not None}
    assert len(page_nums) > 10


def test_unit_metadata_extraction(tmp_path):
    """Test 5: Document metadata extraction correctly parses title, number, revision, and dates."""
    doc_path = tmp_path / "metadata_test.docx"
    doc = docx.Document()
    sec = doc.sections[0]
    htable = sec.header.add_table(rows=2, cols=4, width=docx.shared.Inches(6.0))
    htable.cell(0, 1).text = "Standard Operating Procedure for Change Control"
    htable.cell(0, 2).text = "DOCUMENT NO."
    htable.cell(0, 3).text = "SOP-CC-001"
    htable.cell(1, 1).text = "Standard Operating Procedure for Change Control"
    htable.cell(1, 2).text = "REVISION NO."
    htable.cell(1, 3).text = "03"

    doc.add_heading("Purpose", level=1)
    doc.add_paragraph("Define procedures for evaluating changes.")
    doc.save(doc_path)

    extracted = DocxExtractor().extract(doc_path)
    meta = MetadataExtractor().extract_metadata(extracted)

    assert meta.document_title == "Standard Operating Procedure for Change Control"
    assert meta.document_number == "SOP-CC-001"
    assert meta.revision == "03"
    assert meta.confidence_scores["document_number"] >= 0.90


def test_unit_document_number_identification():
    """Test 6: Document number identification matches varied QMS formats."""
    extractor = MetadataExtractor()
    # Test ETPL pattern
    m1 = extractor.DOC_NUM_PATTERNS[1].search("Header line with ETPL/SOP/QMS/43 number")
    assert m1 and m1.group(1) == "ETPL/SOP/QMS/43"

    # Test ISO pattern
    m2 = extractor.DOC_NUM_PATTERNS[2].search("Reference number ISO 13485:2016(E)")
    assert m2 and "ISO 13485:2016" in m2.group(1)


def test_unit_revision_identification():
    """Test 7: Revision identification matches numeric, alphanumeric, and edition formats."""
    extractor = MetadataExtractor()
    m1 = extractor.REV_PATTERNS[0].search("REVISION NO. 02")
    assert m1 and m1.group(1) == "02"

    m2 = extractor.REV_PATTERNS[1].search("Third edition 2016-03-01")
    assert m2 and m2.group(1) == "Third edition"


def test_unit_effective_date_identification():
    """Test 8: Effective date identification parses standard date formats."""
    extractor = MetadataExtractor()
    m1 = extractor.DATE_PATTERNS[0].search("EFFECTIVE DATE: 05/08/2026")
    assert m1 and m1.group(1) == "05/08/2026"

    m2 = extractor.DATE_PATTERNS[1].search("Published 2016-03-01 in Geneva")
    assert m2 and m2.group(1) == "2016-03-01"


def test_unit_section_identification(tmp_path):
    """Test 9: Section identification detects numbered and unnumbered headings."""
    doc_path = tmp_path / "section_test.docx"
    doc = docx.Document()
    doc.add_paragraph("Purpose", style="Normal")  # Unnumbered keyword
    doc.add_paragraph("Purpose content text.")
    doc.add_paragraph("1.0 Scope", style="Heading 1")  # Numbered
    doc.add_paragraph("Scope content text.")
    doc.add_paragraph("2.0 Procedure", style="Heading 1")
    doc.add_paragraph("Procedure content text.")
    doc.save(doc_path)

    extracted = DocxExtractor().extract(doc_path)
    sections = StructureExtractor().extract_structure(extracted)
    titles = [s.section_title for s in sections]
    assert "Purpose" in titles
    assert "Scope" in titles
    assert "Procedure" in titles


def test_unit_subsection_identification(tmp_path):
    """Test 10: Subsection identification creates proper parent-child relationships."""
    doc_path = tmp_path / "subsections.docx"
    doc = docx.Document()
    doc.add_paragraph("4.0 Quality Management System", style="Heading 1")
    doc.add_paragraph("General overview.")
    doc.add_paragraph("4.1 General Requirements", style="Heading 2")
    doc.add_paragraph("Establish, document, implement and maintain a QMS.")
    doc.add_paragraph("4.2 Documentation Requirements", style="Heading 2")
    doc.add_paragraph("The QMS documentation shall include...")
    doc.save(doc_path)

    extracted = DocxExtractor().extract(doc_path)
    struct = StructureExtractor()
    flat_sections = struct.extract_structure(extracted)
    tree = struct.build_tree(flat_sections)

    qms_root = next((s for s in tree if "Quality Management System" in s.section_title), None)
    assert qms_root is not None
    assert len(qms_root.subsections) == 2
    sub_titles = [s.section_title for s in qms_root.subsections]
    assert "General Requirements" in sub_titles
    assert "Documentation Requirements" in sub_titles


def test_unit_document_chunking(tmp_path):
    """Test 11: Document chunking maintains structure, size constraints, and traceability."""
    doc_path = tmp_path / "chunk_test.docx"
    doc = docx.Document()
    doc.add_paragraph("1.0 Operating Procedure", style="Heading 1")
    # Add 2500 characters of text to force multiple chunks
    doc.add_paragraph("Standard line of text for chunking testing. " * 60)
    doc.save(doc_path)

    extracted = DocxExtractor().extract(doc_path)
    sections = StructureExtractor().extract_structure(extracted)
    engine = ChunkingEngine(max_chunk_chars=800, overlap_chars=100)
    chunks = engine.create_chunks("DOC-TEST-1", "SOP-01", "01", sections)

    assert len(chunks) >= 2
    for c in chunks:
        assert c.document_id == "DOC-TEST-1"
        assert c.chunk_sequence >= 1
        assert c.character_count <= 1100  # Within tolerance
        assert c.section_title == "Operating Procedure"


def test_unit_json_schema_validation():
    """Test 12: JSON schema validation verifies valid schemas and catches missing required keys."""
    valid_payload = {
        "document_id": "DOC-1234",
        "filename": "sop.docx",
        "format": "DOCX",
        "metadata": {
            "document_title": "SOP",
            "document_number": "SOP-01",
            "revision": "01",
            "effective_date": "2026-01-01",
            "department": "QA"
        },
        "sections": [
            {
                "section_id": "SEC-01",
                "section_number": "1.0",
                "section_title": "Scope",
                "parent_section_id": None,
                "level": 1,
                "section_order": 1,
                "content_text": "Scope text",
                "page_start": 1,
                "page_end": 1
            }
        ],
        "chunks": [
            {
                "chunk_id": "CHK-01",
                "document_id": "DOC-1234",
                "document_number": "SOP-01",
                "document_revision": "01",
                "section_title": "Scope",
                "section_number": "1.0",
                "chunk_text": "### Scope\nScope text",
                "page_number": 1,
                "page_start": 1,
                "page_end": 1,
                "chunk_sequence": 1,
                "character_count": 20,
                "token_count_estimate": 5,
                "extraction_status": "success",
                "metadata": {}
            }
        ],
        "processing_status": "completed",
        "extraction_status": "success",
        "ocr_required": False,
        "warnings": [],
        "errors": [],
        "extracted_at": "2026-10-30T00:00:00Z"
    }

    is_valid, errors = validate_structured_json(valid_payload)
    assert is_valid is True, f"Valid payload should pass: {errors}"

    # Invalidate required field
    invalid_payload = dict(valid_payload)
    del invalid_payload["chunks"]
    is_valid_inv, errors_inv = validate_structured_json(invalid_payload)
    assert is_valid_inv is False
    assert any("'chunks' is a required property" in e for e in errors_inv)


def test_unit_unsupported_file_rejection():
    """Test 13: Unsupported file formats (.txt, .exe, .xlsx) are rejected with clear messages."""
    service = DocumentIngestionService()
    # TXT rejection
    v1, f1, err1 = service.validate_file("document.txt", b"plain text")
    assert v1 is False
    assert "Unsupported file extension" in err1

    # XLSX forward-compatibility rejection
    v2, f2, err2 = service.validate_file("data.xlsx", b"some bytes")
    assert v2 is False
    assert "Milestone 3" in err2


def test_unit_corrupted_file_handling():
    """Test 14: Corrupted DOCX and PDF files are handled safely without crashing."""
    service = DocumentIngestionService()
    # Bad DOCX bytes
    fake_docx = b"PK\x03\x04not-a-real-zip-archive-corrupted-bytes"
    doc_res = service.ingest_bytes("corrupted.docx", fake_docx)
    assert doc_res.processing_status == "failed"
    assert "Corrupted" in (doc_res.error_message or "")

    # Bad PDF bytes
    fake_pdf = b"%PDF-1.4 bad pdf content EOF"
    pdf_res = service.ingest_bytes("corrupted.pdf", fake_pdf)
    assert pdf_res.processing_status == "failed"


def test_unit_empty_document_handling():
    """Test 15: Empty 0-byte document is rejected safely."""
    service = DocumentIngestionService()
    v, fmt, err = service.validate_file("empty.docx", b"")
    assert v is False
    assert "empty" in err.lower()


# ============================================================================
# CATEGORY 2: INTEGRATION TESTS
# ============================================================================

def test_integration_full_docx_workflow(client):
    """Integration Test: Upload DOCX -> Process -> Store -> Verify DB & API."""
    doc_bytes = (SAMPLE_DOCS_DIR / "Device assembly.docx").read_bytes()
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers("author"),
        files={"files": ("Device assembly.docx", doc_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_uploaded"] == 1
    assert data["successful"] == 1
    uploaded_doc = data["documents"][0]
    doc_id = uploaded_doc["document_id"]
    assert doc_id.startswith("DOC-")
    assert uploaded_doc["processing_status"] == "completed"

    # Verify document details retrieval
    detail_res = client.get(f"/api/v1/documents/ingested/{doc_id}", headers=auth_headers())
    assert detail_res.status_code == 200
    doc_details = detail_res.json()
    assert doc_details["filename"] == "Device assembly.docx"
    assert doc_details["metadata"]["document_number"] == "ETPL/SOP/QMS/43"
    assert doc_details["metadata"]["revision"] == "00"
    assert doc_details["metadata"]["effective_date"] == "05/08/2026"

    # Verify sections retrieval
    sec_res = client.get(f"/api/v1/documents/ingested/{doc_id}/sections", headers=auth_headers())
    assert sec_res.status_code == 200
    assert sec_res.json()["total_sections"] > 5

    # Verify chunks retrieval
    chk_res = client.get(f"/api/v1/documents/ingested/{doc_id}/chunks", headers=auth_headers())
    assert chk_res.status_code == 200
    assert chk_res.json()["total_chunks"] > 5

    # Verify structured JSON retrieval
    json_res = client.get(f"/api/v1/documents/ingested/{doc_id}/json", headers=auth_headers())
    assert json_res.status_code == 200
    json_body = json_res.json()
    is_valid, validation_errors = validate_structured_json(json_body)
    assert is_valid is True, f"JSON output must strictly validate: {validation_errors}"


def test_integration_full_pdf_workflow(client):
    """Integration Test: Upload PDF -> Process -> Store -> Verify DB & API."""
    pdf_bytes = (SAMPLE_DOCS_DIR / "ISO-13485-2016-EN.pdf").read_bytes()
    response = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers("author"),
        files={"files": ("ISO-13485-2016-EN.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["successful"] == 1
    doc_id = data["documents"][0]["document_id"]

    # Verify details
    detail_res = client.get(f"/api/v1/documents/ingested/{doc_id}", headers=auth_headers())
    assert detail_res.status_code == 200
    doc_details = detail_res.json()
    assert doc_details["total_pages"] == 44
    assert doc_details["metadata"]["document_number"] == "ISO 13485:2016(E)"
    assert doc_details["metadata"]["revision"] == "Third edition"


# ============================================================================
# CATEGORY 3: REAL-DOCUMENT TESTING
# ============================================================================

def test_real_doc_device_assembly():
    """Real Document Test: Device assembly.docx verifies document number, revision, dates, tables."""
    db = SessionLocal()
    try:
        service = DocumentIngestionService(db=db)
        content = (SAMPLE_DOCS_DIR / "Device assembly.docx").read_bytes()
        doc = service.ingest_bytes("Device assembly.docx", content)

        assert doc.processing_status == "completed"
        meta = doc.metadata_record
        assert meta is not None
        assert meta.document_number == "ETPL/SOP/QMS/43"
        assert meta.revision_number == "00"
        assert meta.effective_date == "05/08/2026"
        assert meta.prepared_by == "CH. Rebcha Jashmitha"
        assert meta.reviewed_by == "Dr. A. Lakshmi Sangeetha"
        assert meta.approved_by == "Dr. A. Balaji Ganesh"
        assert meta.department == "QA/RA"
        assert meta.purpose is not None and "assembly of medical devices" in meta.purpose
        assert doc.total_sections > 10
        assert doc.total_chunks > 10
    finally:
        db.close()


def test_real_doc_functionality_performance_testing():
    """Real Document Test: Functionality performance testing.docx verifies tables and metadata."""
    db = SessionLocal()
    try:
        service = DocumentIngestionService(db=db)
        content = (SAMPLE_DOCS_DIR / "Functionality performance testing.docx").read_bytes()
        doc = service.ingest_bytes("Functionality performance testing.docx", content)

        assert doc.processing_status == "completed"
        meta = doc.metadata_record
        assert meta is not None
        assert meta.document_number == "ETPL/SOP/SOP/37"
        assert meta.revision_number == "00"
        assert meta.effective_date == "02/04/2026"
        assert meta.prepared_by == "S. B. Nivetha"
        assert meta.reviewed_by == "Dr. Prakash Rajiah"
        assert meta.approved_by == "Dr. A. Balaji Ganesh"
        assert meta.purpose is not None and "Functionality and Performance testing" in meta.purpose
    finally:
        db.close()


def test_real_doc_dmf():
    """Real Document Test: DMF.docx (Device Master File) with large multi-chapter content."""
    db = SessionLocal()
    try:
        service = DocumentIngestionService(db=db)
        content = (SAMPLE_DOCS_DIR / "DMF.docx").read_bytes()
        doc = service.ingest_bytes("DMF.docx", content)

        assert doc.processing_status == "completed"
        meta = doc.metadata_record
        assert meta is not None
        assert meta.document_number == "ETPL/DMF/00"
        assert meta.revision_number == "02"
        assert meta.effective_date == "10/07/2026"
        assert doc.total_sections > 20
        assert doc.total_chunks > 30
    finally:
        db.close()


def test_real_doc_iso_13485_pdf():
    """Real Document Test: ISO-13485-2016-EN.pdf maintains page references and extracts standard metadata."""
    db = SessionLocal()
    try:
        service = DocumentIngestionService(db=db)
        content = (SAMPLE_DOCS_DIR / "ISO-13485-2016-EN.pdf").read_bytes()
        doc = service.ingest_bytes("ISO-13485-2016-EN.pdf", content)

        assert doc.processing_status == "completed"
        assert doc.total_pages == 44
        meta = doc.metadata_record
        assert meta is not None
        assert meta.document_number == "ISO 13485:2016(E)"
        assert meta.revision_number == "Third edition"
        assert meta.effective_date == "2016-03-01"
    finally:
        db.close()


# ============================================================================
# CATEGORY 4: FAILURE TESTING
# ============================================================================

def test_failure_unsupported_extensions(client):
    """Failure Test: Rejection of unsupported extensions (.exe, .zip, .txt, .xlsx)."""
    # .txt
    r1 = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers(),
        files={"files": ("malicious.exe", b"binary executable data", "application/octet-stream")}
    )
    assert r1.status_code == 200
    res1 = r1.json()["documents"][0]
    assert res1["upload_status"] == "failed"
    assert "Unsupported file extension" in res1["error_message"]

    # .xlsx
    r2 = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers(),
        files={"files": ("matrix.xlsx", b"excel binary", "application/vnd.ms-excel")}
    )
    assert r2.status_code == 200
    res2 = r2.json()["documents"][0]
    assert res2["upload_status"] == "failed"
    assert "Milestone 3" in res2["error_message"]


def test_failure_empty_file(client):
    """Failure Test: Empty 0-byte file rejected."""
    r = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers(),
        files={"files": ("zero.docx", b"", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert r.status_code == 200
    res = r.json()["documents"][0]
    assert res["upload_status"] == "failed"
    assert "empty" in res["error_message"].lower()


def test_failure_corrupted_magic_bytes(client):
    """Failure Test: Extension mismatch (e.g. text file renamed to .pdf)."""
    r = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers(),
        files={"files": ("disguised.pdf", b"This is plain text not PDF", "application/pdf")}
    )
    assert r.status_code == 200
    res = r.json()["documents"][0]
    assert res["upload_status"] == "failed"
    assert "magic byte signature" in res["error_message"]


def test_failure_scanned_pdf_detection(tmp_path):
    """Failure Test: Scanned PDF without text layer flags ocr_required."""
    import reportlab.pdfgen.canvas as canvas
    scanned_path = tmp_path / "scanned_simulated.pdf"
    c = canvas.Canvas(str(scanned_path))
    # Draw blank white rect to simulate image/scanned page without text stream
    c.rect(0, 0, 500, 700, fill=1)
    c.showPage()
    c.save()

    extractor = PdfExtractor()
    extracted = extractor.extract(scanned_path)
    assert extracted.ocr_required is True
    assert extracted.is_scanned is True
    assert any("OCR is required" in w for w in extracted.warnings)


def test_failure_missing_metadata(tmp_path):
    """Failure Test: Document with no metadata returns nulls without inventing data."""
    doc_path = tmp_path / "no_meta.docx"
    doc = docx.Document()
    doc.add_paragraph("Just arbitrary narrative with no document number, revision or author.")
    doc.save(doc_path)

    extracted = DocxExtractor().extract(doc_path)
    meta = MetadataExtractor().extract_metadata(extracted)
    assert meta.document_number is None
    assert meta.revision is None
    assert meta.effective_date is None
    assert meta.approved_by is None
    assert len(meta.warnings) >= 3


def test_ai_readiness_endpoint(client):
    """Test AI Readiness endpoint reports local AI status and embedding readiness."""
    res = client.get("/api/v1/ai/readiness")
    assert res.status_code == 200
    data = res.json()
    assert data["engine_mode"] == "rules_first_deterministic"
    assert data["llm_mutation_blocked"] is True
    assert data["target_embedding_model"] == "nomic-embed-text"
