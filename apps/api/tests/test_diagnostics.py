import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.generated_document import GeneratedSection


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_system_diagnostics_endpoint(client):
    headers = {"X-Actor-Role": "admin", "X-Actor-Email": "admin@example.local"}
    res = client.get("/api/v1/system/diagnostics", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "database" in data
    assert data["database"]["status"] == "ok"
    assert "document_rendering" in data
    assert data["document_rendering"]["docx"] == "ok"
    assert data["document_rendering"]["pdf"] == "ok"
    assert "total_execution_ms" in data


def test_system_test_nvidia_endpoint_mock(client):
    headers = {"X-Actor-Role": "admin", "X-Actor-Email": "admin@example.local"}
    mock_test = {
        "success": True,
        "configured": True,
        "model": "poolside/laguna-xs-2.1",
        "response_time_ms": 240.5,
        "raw_response": '{"status": "OK"}',
    }
    with patch("app.services.nvidia_service.NvidiaService.test_connectivity", return_value=mock_test):
        res = client.post("/api/v1/system/test-nvidia", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["response_time_ms"] == 240.5


def test_create_custom_template_endpoint(client):
    headers = {"X-Actor-Role": "admin", "X-Actor-Email": "admin@example.local"}
    payload = {
        "name": "Sterilization Validation Protocol",
        "category": "Sterilization",
        "description": "Validation protocol for ethylene oxide sterilization.",
        "sections": ["protocol_scope", "biological_indicators", "acceptance_criteria"],
        "fields": [
            {"key": "cycles", "label": "Number of Cycles", "type": "number", "required": True},
            {"key": "eo_concentration", "label": "EO Concentration mg/L", "type": "text", "required": True},
        ],
        "requirements": ["QMS-DOC-CONTROL"],
    }
    res = client.post("/api/v1/templates", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Sterilization Validation Protocol"
    assert len(data["sections"]) == 3
    assert len(data["fields"]) == 2

    # Verify template is retrievable
    get_res = client.get(f"/api/v1/templates/{data['id']}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["category"] == "Sterilization"


def test_section_regeneration_and_update(client):
    headers = {"X-Actor-Role": "author", "X-Actor-Email": "author@example.local"}
    # 1. Create document
    create_res = client.post("/api/v1/documents", json={"template_id": "sop", "title": "Regen Test SOP"}, headers=headers)
    assert create_res.status_code == 201
    doc_id = create_res.json()["id"]

    # 2. Patch initial content into version
    mock_sec = {
        "section_id": "procedure",
        "title": "Procedure",
        "content": "Newly regenerated content via NVIDIA NIM.",
        "requirement_refs": ["QMS-DOC-CONTROL"],
        "unresolved_items": [],
    }

    with patch("app.services.nvidia_service.NvidiaService.regenerate_section", return_value=GeneratedSection(**mock_sec)):
        regen_res = client.post(
            f"/api/v1/documents/{doc_id}/sections/procedure/regenerate",
            json={"guidance": "Focus on particulate testing."},
            headers=headers,
        )
        assert regen_res.status_code == 200
        sections = regen_res.json()["current_version"]["content"]["sections"]
        proc_sec = next((s for s in sections if s["section_id"] == "procedure"), None)
        assert proc_sec is not None
        assert proc_sec["content"] == "Newly regenerated content via NVIDIA NIM."

    # 3. Test direct section update PATCH
    patch_res = client.patch(
        f"/api/v1/documents/{doc_id}/sections/procedure",
        json={"content": "Directly edited content by user.", "title": "Updated Procedure Title"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    sections = patch_res.json()["current_version"]["content"]["sections"]
    proc_sec = next((s for s in sections if s["section_id"] == "procedure"), None)
    assert proc_sec is not None
    assert proc_sec["content"] == "Directly edited content by user."
    assert proc_sec["title"] == "Updated Procedure Title"
