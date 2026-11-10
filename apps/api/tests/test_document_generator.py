from datetime import datetime, timezone
from app.services.document_generator import DocumentGenerator


class MockDoc:
    title = "Test Standard Operating Procedure"
    document_number = "SOP-TEST-2026-001"
    document_type = "Standard Operating Procedure"


class MockVersion:
    revision = 1
    status = "draft"
    provider = "nvidia"
    generated_at = datetime.now(timezone.utc)


def test_docx_generation():
    doc = MockDoc()
    ver = MockVersion()
    content = {
        "title": "Cleanroom Particulate SOP",
        "purpose": "Define environmental monitoring protocols.",
        "scope": "All ISO Class 7 cleanrooms.",
        "sections": [
            {
                "section_id": "procedure",
                "title": "Sampling Procedure",
                "content": "Perform particle counts at 0.5 and 5.0 micron channels.",
                "requirement_refs": ["QMS-DOC-CONTROL"],
                "unresolved_items": ["Calibrate particle counter annually."],
            }
        ],
        "open_issues": ["Action limit notification workflow pending."],
        "review_notes": ["Approved by Quality Operations."],
    }

    docx_bytes = DocumentGenerator.generate_docx(doc, ver, content)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 1000
    # Genuine DOCX zip header
    assert docx_bytes[:4] == b"PK\x03\x04"


def test_pdf_generation():
    doc = MockDoc()
    ver = MockVersion()
    content = {
        "title": "Cleanroom Particulate SOP",
        "purpose": "Define environmental monitoring protocols.",
        "scope": "All ISO Class 7 cleanrooms.",
        "sections": [
            {
                "section_id": "procedure",
                "title": "Sampling Procedure",
                "content": "Perform particle counts at 0.5 and 5.0 micron channels.",
                "requirement_refs": ["QMS-DOC-CONTROL"],
                "unresolved_items": [],
            }
        ],
    }

    pdf_bytes = DocumentGenerator.generate_pdf(doc, ver, content)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    # Genuine PDF header
    assert pdf_bytes[:4] == b"%PDF"
