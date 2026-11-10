import asyncio
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.services.enhancement_service import ContentEnhancementService

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def headers(role="author"):
    return {"x-actor-role": role, "x-actor-email": f"demo.{role}@example.local", "x-organization-id": "demo-org"}


def test_deterministic_offline_enhancement():
    service = ContentEnhancementService()
    summary = "Cleaning assembly line between production shifts using 70% IPA, weekly HEPA filter tests, and logging particle counts."
    res = asyncio.run(service.enhance_topic_summary(template_id="sop", summary=summary, provider_name="offline"))

    assert res["template_id"] == "sop"
    assert "Clean" in res["title"] or "Standard Operating Procedure" in res["title"]
    assert "answers" in res
    answers = res["answers"]
    assert "purpose" in answers
    assert len(answers["purpose"]) >= 20
    assert "scope" in answers
    assert "procedure_steps" in answers
    assert "70% IPA" in answers["procedure_steps"] or "IPA" in answers["procedure_steps"]
    assert "records" in answers
    assert "applicability" in res
    assert "QMS-DOC-CONTROL" in res["applicability"]


def test_enhance_api_preview_mode(client):
    payload = {
        "template_id": "capa",
        "summary": "Nonconformance found in lot 409 where catheter balloon burst during pressure test. Need containment and investigation.",
        "provider": "offline",
        "create_document": False
    }
    resp = client.post("/api/v1/documents/enhance-from-summary", json=payload, headers=headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["template_id"] == "capa"
    assert "answers" in data
    assert "root_cause_method" in data["answers"]
    assert "containment_process" in data["answers"]


def test_enhance_api_create_document_mode(client):
    payload = {
        "template_id": "sop",
        "summary": "Calibration procedure for digital micrometers and calipers used on medical implant assembly line.",
        "organization_name": "BioPrecision Implants Ltd.",
        "provider": "offline",
        "create_document": True
    }
    resp = client.post("/api/v1/documents/enhance-from-summary", json=payload, headers=headers())
    assert resp.status_code == 200, resp.text
    doc = resp.json()
    assert doc["id"] is not None
    assert doc["document_number"].startswith("QMS-")
    version = doc["current_version"]
    assert version["answers"]["organization_name"] == "BioPrecision Implants Ltd."
    assert len(version["answers"]["procedure_steps"]) >= 30
    assert version["validation_status"] in ["passed", "failed"]


def test_enhance_existing_document(client):
    # First create a basic blank document
    create_resp = client.post(
        "/api/v1/documents",
        json={"template_id": "sop", "title": "Blank Calibration SOP", "answers": {}},
        headers=headers()
    )
    assert create_resp.status_code == 201, create_resp.text
    doc_id = create_resp.json()["id"]

    # Now enhance it from a summary
    enhance_payload = {
        "summary": "Disinfection of packaging workstations using ultraviolet UV-C irradiation and bactericidal wipes every 8 hours.",
        "provider": "offline"
    }
    resp = client.post(f"/api/v1/documents/{doc_id}/enhance-from-summary", json=enhance_payload, headers=headers())
    assert resp.status_code == 200, resp.text
    updated_doc = resp.json()
    version = updated_doc["current_version"]
    assert "UV-C" in version["answers"]["procedure_steps"] or "disinfection" in version["answers"]["procedure_steps"].lower()
