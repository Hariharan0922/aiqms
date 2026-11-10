import pytest
from app.services.web_analysis_service import web_analysis_service
from app.services.enhancement_service import ContentEnhancementService
from app.providers.offline_provider import OfflineProvider
from app.providers.base import GenerationRequest
from app.services.document_generator import DocumentGenerator


@pytest.mark.anyio
async def test_web_analysis_short_inputs():
    """Verify web analysis service analyzes 1-2 words or brief inputs."""
    analysis = await web_analysis_service.analyze_topic("cleanroom")
    assert analysis["matched_domain"] == "cleanroom"
    assert "ISO 14644" in analysis["primary_standard"]
    assert len(analysis["quantitative_benchmarks"]) >= 5

    analysis_capa = await web_analysis_service.analyze_topic("capa")
    assert analysis_capa["matched_domain"] == "capa"
    assert "ISO 13485" in analysis_capa["primary_standard"]


@pytest.mark.anyio
async def test_enhancement_concise_word_budgets():
    """Verify ContentEnhancementService adheres to reconfigured section word budgets."""
    svc = ContentEnhancementService()
    res = await svc.enhance_topic_summary("sop", "cleanroom particulate", provider_name="offline")
    assert res["template_id"] == "sop"
    purpose_words = len(res["answers"]["purpose"].split())
    scope_words = len(res["answers"]["scope"].split())
    assert 20 <= purpose_words <= 40, f"purpose had {purpose_words} words (expected 20-40)"
    assert 20 <= scope_words <= 30, f"scope had {scope_words} words (expected 20-30)"
    assert "ISO 13485:2016" in res["answers"]["purpose"]


@pytest.mark.anyio
async def test_offline_provider_exact_section_word_ranges():
    """Verify offline generator produces all 7 sections within the reconfigured platform specification."""
    p = OfflineProvider()
    req = GenerationRequest(
        system_instructions="You draft quality management system documents.",
        prompt='{"document_number": "QMS-2026-TEST", "revision": 1, "title": "Cleanroom Monitoring SOP", "document_type": "SOP", "sections": ["purpose", "scope", "responsibilities", "reference", "procedure", "records", "revision_history"], "answers": {}}',
        output_schema={},
    )
    resp = await p.generate(req)
    sections = resp.content["sections"]
    assert len(sections) == 7

    expected_ids = ["purpose", "scope", "responsibilities", "reference", "procedure", "records", "revision_history"]
    assert [s["section_id"] for s in sections] == expected_ids

    spec_ranges = {
        "purpose": (20, 40, "§4.1"),
        "scope": (20, 30, "§1.2"),
        "responsibilities": (20, 50, "§5.5"),
        "reference": (30, 60, "§4.2.1"),
        "procedure": (30, 70, "§7.1"),
        "records": (25, 45, "§4.2.5"),
        "revision_history": (25, 40, "§4.2.4"),
    }

    for sec in sections:
        sid = sec["section_id"]
        min_w, max_w, required_clause = spec_ranges[sid]
        word_count = len(sec["content"].split())
        assert min_w <= word_count <= max_w, f"Section '{sid}' has {word_count} words (expected {min_w}-{max_w})"
        assert required_clause in sec["content"], f"Section '{sid}' missing required clause reference '{required_clause}'"

    # Verify DOCX and PDF generation
    doc_mock = type("DocMock", (), {"title": "Cleanroom SOP", "document_number": "QMS-001", "document_type": "SOP"})()
    ver_mock = type("VerMock", (), {"revision": 1, "status": "released", "provider": "NVIDIA NIM", "generated_at": None})()
    docx_bytes = DocumentGenerator.generate_docx(doc_mock, ver_mock, resp.content)
    pdf_bytes = DocumentGenerator.generate_pdf(doc_mock, ver_mock, resp.content)
    assert len(docx_bytes) > 1000
    assert len(pdf_bytes) > 1000
