import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def headers(role="author", email=None):
    return {"X-Actor-Role": role, "X-Actor-Email": email or f"demo.{role}@example.local", "X-Organization-Id": "demo-org"}


def test_full_document_lifecycle_offline_provider(client):
    templates = client.get("/api/v1/templates").json()
    assert len(templates) >= 8
    sop = next(t for t in templates if t["id"] == "sop")
    created = client.post("/api/v1/documents", headers=headers(), json={"template_id": "sop", "title": "Test document control SOP", "answers": {}})
    assert created.status_code == 201, created.text
    doc = created.json(); doc_id = doc["id"]
    assert doc["current_version"]["status"] == "draft"

    answers = {
        "organization_name": "Example Medical Devices Ltd",
        "process_owner": "Quality Manager",
        "purpose": "Define a consistent controlled process for document lifecycle management.",
        "scope": "Applies to QMS documents used by the organization across defined business sites.",
        "procedure_steps": "Create a request, review the content, approve the revision, publish the controlled copy, and archive superseded copies.",
        "records": "Document master list, review record, approval record, change history.",
        "reviewer_role": "Independent Quality Reviewer",
        "approver_role": "Quality Director",
    }
    applicability = {code: {"status": "applicable", "rationale": "Applicable to the described QMS process."} for code in sop["requirements"]}
    patched = client.patch(f"/api/v1/documents/{doc_id}/answers", headers=headers(), json={"answers": answers, "applicability": applicability})
    assert patched.status_code == 200, patched.text

    validation = client.post(f"/api/v1/documents/{doc_id}/validate", headers=headers(), json={})
    assert validation.status_code == 200, validation.text
    assert validation.json()["can_generate"] is True
    assert any(f["code"] == "REQUIREMENT_MAPPING_UNVERIFIED" for f in validation.json()["findings"])
    # The starter mapping should be clearly flagged until an admin verifies it.
    for code in sop["requirements"]:
        verified = client.patch(f"/api/v1/requirements/{code}", headers=headers("admin"), json={
            "source_edition": "TEST FIXTURE ONLY — not an ISO source",
            "source_reference": f"test-fixture/{code}",
            "summary": "Automated test fixture used only to validate lifecycle enforcement.",
            "verification_status": "verified",
            "verification_note": "Test-only fixture; does not represent verification of an actual ISO clause mapping.",
        })
        assert verified.status_code == 200, verified.text
    validation_after_source_update = client.post(f"/api/v1/documents/{doc_id}/validate", headers=headers(), json={})
    assert validation_after_source_update.status_code == 200
    assert not any(f["code"] == "REQUIREMENT_MAPPING_UNVERIFIED" for f in validation_after_source_update.json()["findings"])
    preview = client.get(f"/api/v1/documents/{doc_id}/prompt-preview", headers=headers())
    assert preview.status_code == 200, preview.text
    assert preview.json()["prompt_version"] and preview.json()["input_hash"]

    generated = client.post(f"/api/v1/documents/{doc_id}/generate", headers=headers(), json={"provider": "offline"})
    assert generated.status_code == 200, generated.text
    version = generated.json()["current_version"]
    assert version["status"] == "generated"
    assert len(version["content"]["sections"]) == len(sop["sections"])

    submitted = client.post(f"/api/v1/documents/{doc_id}/submit-review", headers=headers(), json={})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["current_version"]["status"] == "in_review"

    reviewed = client.post(f"/api/v1/documents/{doc_id}/review", headers=headers("reviewer"), json={"decision": "accept", "comments": "Draft reviewed; outstanding source mappings remain subject to verification."})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["current_version"]["status"] == "awaiting_approval"

    approved = client.post(f"/api/v1/documents/{doc_id}/approve", headers=headers("approver"), json={"decision": "approve", "comments": "Approved for the configured document scope."})
    assert approved.status_code == 200, approved.text
    assert approved.json()["current_version"]["status"] == "released"

    docx = client.get(f"/api/v1/documents/{doc_id}/export?format=docx", headers=headers("approver"))
    pdf = client.get(f"/api/v1/documents/{doc_id}/export?format=pdf", headers=headers("approver"))
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    trace = client.get(f"/api/v1/documents/{doc_id}/traceability", headers=headers("reviewer"))
    assert trace.status_code == 200 and len(trace.json()["links"]) == len(sop["requirements"])
    locked = client.patch(f"/api/v1/documents/{doc_id}/answers", headers=headers(), json={"answers": {**answers, "purpose": "A changed released purpose statement that is intentionally different."}})
    assert locked.status_code == 409
    revision = client.post(f"/api/v1/documents/{doc_id}/new-revision", headers=headers(), json={})
    assert revision.status_code == 201, revision.text
    assert revision.json()["current_version"]["revision"] == 2
    assert revision.json()["current_version"]["status"] == "draft"


def test_missing_fields_prevent_generation(client):
    created = client.post("/api/v1/documents", headers=headers(), json={"template_id": "capa", "title": "CAPA sample document", "answers": {}})
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    result = client.post(f"/api/v1/documents/{doc_id}/validate", headers=headers(), json={}).json()
    assert result["can_generate"] is False
    assert any(f["code"] == "FIELD_REQUIRED" for f in result["findings"])
    response = client.post(f"/api/v1/documents/{doc_id}/generate", headers=headers(), json={"provider":"offline"})
    assert response.status_code == 409


def test_author_role_cannot_access_approval_endpoint(client):
    # Exercise the role boundary with a released test lifecycle handled by the primary test.
    response = client.post("/api/v1/documents/not-a-document/approve", headers=headers("author"), json={"decision":"approve"})
    assert response.status_code == 403


def test_not_applicable_decision_requires_rationale(client):
    created = client.post("/api/v1/documents", headers=headers(), json={"template_id": "sop", "title": "SOP Applicability Sample", "answers": {}})
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    template = client.get("/api/v1/templates/sop").json()
    answers = {field["key"]: ("A sufficiently detailed example value for a required quality document field." if field.get("type") == "textarea" else "Example value") for field in template["fields"]}
    # Increase common required fields to meet their configured minimum lengths.
    answers.update({"organization_name":"Example Medical Devices Ltd", "process_owner":"Quality Manager",
                    "purpose":"Define the quality-controlled purpose and expected process outcome for this SOP.",
                    "scope":"Applies to the described quality management activities and relevant business processes.",
                    "procedure_steps":"Receive request, assess scope, draft changes, independently review, authorize, publish, and archive the controlled revision.",
                    "records":"Master list, reviewed copy, approval record and change history.",
                    "reviewer_role":"Independent quality reviewer", "approver_role":"Quality director"})
    applicability = {code: {"status":"applicable", "rationale":"This internal mapping is considered relevant for the sample scope."} for code in template["requirements"]}
    applicability[template["requirements"][0]] = {"status":"not_applicable", "rationale":""}
    response = client.patch(f"/api/v1/documents/{doc_id}/answers", headers=headers(), json={"answers":answers, "applicability":applicability})
    assert response.status_code == 200
    result = client.post(f"/api/v1/documents/{doc_id}/validate", headers=headers(), json={}).json()
    assert result["can_generate"] is False
    assert any(item["code"] == "APPLICABILITY_RATIONALE_REQUIRED" for item in result["findings"])


def test_unverified_source_mapping_blocks_release(client):
    template = client.get("/api/v1/templates/capa").json()
    created = client.post("/api/v1/documents", headers=headers(), json={"template_id": "capa", "title": "CAPA release gate test", "answers": {}})
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    answers = {field["key"]: "Test fixture information with sufficient detail for the configured validation rule." for field in template["fields"]}
    applicability = {code: {"status": "applicable", "rationale": "Applicable for a workflow test only."} for code in template["requirements"]}
    saved = client.patch(f"/api/v1/documents/{doc_id}/answers", headers=headers(), json={"answers": answers, "applicability": applicability})
    assert saved.status_code == 200, saved.text
    validation = client.post(f"/api/v1/documents/{doc_id}/validate", headers=headers(), json={})
    assert validation.status_code == 200 and validation.json()["can_generate"] is True
    assert any(f["code"] == "REQUIREMENT_MAPPING_UNVERIFIED" for f in validation.json()["findings"])
    generated = client.post(f"/api/v1/documents/{doc_id}/generate", headers=headers(), json={"provider": "offline"})
    assert generated.status_code == 200, generated.text
    submitted = client.post(f"/api/v1/documents/{doc_id}/submit-review", headers=headers(), json={})
    assert submitted.status_code == 200, submitted.text
    reviewed = client.post(f"/api/v1/documents/{doc_id}/review", headers=headers("reviewer"), json={"decision": "accept", "comments": "Review complete for release gate test."})
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(f"/api/v1/documents/{doc_id}/approve", headers=headers("approver"), json={"decision": "approve", "comments": "Attempting a release while source mappings remain unverified."})
    assert approved.status_code == 409
    assert "Release is blocked" in approved.json()["detail"]
