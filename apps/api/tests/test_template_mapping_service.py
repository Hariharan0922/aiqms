from app.services.template_mapping_service import TemplateMappingService
from app.schemas.generated_document import GeneratedDocument, GeneratedSection


def test_template_mapping_preserves_section_order():
    template = {
        "id": "sop",
        "name": "Standard Operating Procedure",
        "sections": ["purpose", "scope", "responsibilities", "procedure", "records", "references"],
    }
    # Out of order generated sections
    generated = GeneratedDocument(
        title="Sample SOP",
        document_type="Standard Operating Procedure",
        purpose="Sample Purpose",
        scope="Sample Scope",
        sections=[
            GeneratedSection(section_id="records", title="Records", content="Log books retained 5 years."),
            GeneratedSection(section_id="purpose", title="Purpose", content="Control process."),
            GeneratedSection(section_id="procedure", title="Procedure", content="Step 1, step 2."),
            GeneratedSection(section_id="scope", title="Scope", content="All production lines."),
            GeneratedSection(section_id="responsibilities", title="Responsibilities", content="QA Manager is owner."),
            GeneratedSection(section_id="references", title="References", content="ISO 13485:2016."),
        ],
    )

    mapped = TemplateMappingService.map_document_content(template, generated, {})
    assert mapped["title"] == "Sample SOP"
    section_ids = [s["section_id"] for s in mapped["sections"]]
    assert section_ids == ["purpose", "scope", "responsibilities", "procedure", "records", "references"]
    assert mapped["sections"][0]["content"] == "Control process."
    assert mapped["sections"][4]["content"] == "Log books retained 5 years."


def test_template_mapping_handles_missing_sections():
    template = {
        "id": "sop",
        "name": "Standard Operating Procedure",
        "sections": ["purpose", "scope", "procedure"],
    }
    generated = GeneratedDocument(
        title="Partial SOP",
        document_type="Standard Operating Procedure",
        purpose="Purpose text",
        scope="Scope text",
        sections=[
            GeneratedSection(section_id="purpose", title="Purpose", content="Purpose text."),
        ],
    )

    mapped = TemplateMappingService.map_document_content(template, generated, {})
    assert len(mapped["sections"]) == 3
    assert mapped["missing_sections"] == ["scope", "procedure"]
    assert "Missing required section: Scope" in mapped["sections"][1]["unresolved_items"][0]


def test_template_mapping_update_single_section():
    current_content = {
        "title": "Document Title",
        "sections": [
            {"section_id": "sec1", "title": "Section 1", "content": "Original Content 1"},
            {"section_id": "sec2", "title": "Section 2", "content": "Original Content 2"},
        ],
    }
    updated_sec = GeneratedSection(
        section_id="sec2",
        title="Section 2 Updated",
        content="Regenerated Content for Section 2 only",
    )

    updated = TemplateMappingService.update_single_section(current_content, "sec2", updated_sec)
    assert updated["sections"][0]["content"] == "Original Content 1"  # untouched
    assert updated["sections"][1]["content"] == "Regenerated Content for Section 2 only"
    assert updated["sections"][1]["title"] == "Section 2 Updated"
