"""Unit and integration tests for ISO 13485:2016 Machine Learning Model."""

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal, Base, engine
from app.db.migrations import run_migrations
from app.main import app
from app.models.compliance import ISOClause
from app.services.compliance.iso_ml_model import ISO13485MLModel, MODEL_FILE_PATH, SFT_DATASET_PATH
from app.services.compliance.iso_ml_dataset_generator import ISO13485DatasetGenerator


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestISO13485MLModel:
    """Tests for the standalone ISO 13485:2016 Machine Learning Model."""

    def test_model_artifact_exists_and_loads(self, db_session):
        model = ISO13485MLModel(db=db_session)
        assert model.load() is True
        assert model.is_loaded is True
        assert model.clause_classifier is not None
        assert len(model.clause_metadata) == 88

    def test_training_dataset_generation(self, db_session):
        gen = ISO13485DatasetGenerator(db_session)
        samples = gen.generate_classification_dataset()
        assert len(samples) >= 500
        # Check that key canonical clauses are represented
        represented_clauses = set(str(s.clause_number) for s in samples)
        assert "4.2.3" in represented_clauses
        assert "7.5.6" in represented_clauses
        assert "7.5.7" in represented_clauses
        assert "8.2.2" in represented_clauses
        assert "8.5.2" in represented_clauses

    def test_predict_sterilization_validation(self, db_session):
        model = ISO13485MLModel(db=db_session)
        model.load()
        text = "Ethylene oxide sterilization cycle validation per ISO 11135 and sterile barrier packaging integrity testing."
        preds = model.predict_clause(text, top_k=3)
        assert len(preds) == 3
        # Clause 7.5.7 (sterilization validation) or 7.5.6 should be top or top 2
        top_clauses = [str(p["clause_number"]) for p in preds]
        assert "7.5.7" in top_clauses or "7.5.6" in top_clauses
        assert preds[0]["confidence"] > 0.05
        assert preds[0]["requires_record"] is True

    def test_predict_complaint_handling(self, db_session):
        model = ISO13485MLModel(db=db_session)
        model.load()
        text = "Timely complaint handling, investigation of reported medical device failures, and customer feedback evaluation."
        preds = model.predict_clause(text, top_k=3)
        top_clauses = [str(p["clause_number"]) for p in preds]
        assert any(c in top_clauses for c in ["8.2.2", "8.2.1", "8.2.3"])

    def test_audit_procedure_text(self, db_session):
        model = ISO13485MLModel(db=db_session)
        model.load()
        text = "Complaint handling standard operating procedure. All customer complaints shall be investigated and records maintained."
        audit = model.audit_text(text)
        assert audit["target_clause"] in ["8.2.2", "8.2.1", "8.5.2"]
        assert audit["compliance_score"] > 20.0
        assert len(audit["strengths"]) > 0
        assert "verdict" in audit
        assert "normative_reference" in audit

    def test_audit_with_explicit_clause_target(self, db_session):
        model = ISO13485MLModel(db=db_session)
        model.load()
        text = "Standard Operating Procedure for Document Control. All changes must be approved by QA and revision status tracked."
        audit = model.audit_text(text, target_clause_number="4.2.4")
        assert audit["target_clause"] == "4.2.4"
        assert audit["clause_title"] == "Control of documents"
        assert audit["requires_documented_procedure"] is True
        assert audit["requires_record"] is False

        # Verify Clause 4.2.5 requires records
        audit_records = model.audit_text("Batch production records and test logs retention.", target_clause_number="4.2.5")
        assert audit_records["requires_record"] is True

    def test_sft_dataset_file_exists(self):
        assert SFT_DATASET_PATH.exists()
        assert SFT_DATASET_PATH.stat().st_size > 1000


class TestISO13485MLApi:
    """Tests for ISO 13485 ML FastAPI endpoints."""

    def test_api_predict_clause(self, client):
        payload = {
            "text": "Device master record containing specifications, manufacturing procedures, and quality acceptance criteria.",
            "top_k": 3,
        }
        res = client.post("/api/v1/compliance/ml/predict-clause", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert len(data["predictions"]) == 3
        assert str(data["top_match"]["clause_number"]) in ["4.2.3", "4.2.4"]

    def test_api_audit_text(self, client):
        payload = {
            "text": "Standard Operating Procedure for Document Control. All changes must be approved by QA and revision status tracked.",
            "target_clause": "4.2.4",
        }
        res = client.post("/api/v1/compliance/ml/audit", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert str(data["target_clause"]) == "4.2.4"
        assert data["clause_title"] == "Control of documents"
        assert data["compliance_score"] > 30.0

    def test_api_model_info(self, client):
        res = client.get("/api/v1/compliance/ml/model-info")
        assert res.status_code == 200
        data = res.json()
        assert data["version"] == "1.0.0"
        assert data["total_classes"] == 88

    def test_api_sft_dataset_info(self, client):
        res = client.get("/api/v1/compliance/ml/dataset/sft?limit=3")
        assert res.status_code == 200
        data = res.json()
        assert data["total_sft_records"] > 0
        assert len(data["sample_records"]) == 3

    def test_api_verify_and_generate_pipeline(self, client):
        payload = {
            "summary": "Cleanroom particulate monitoring protocol per ISO 14644 and environmental bioburden controls.",
            "template_id": "sop",
            "provider": "offline",  # Use offline rules in test environment to avoid external cloud API latency
        }
        res = client.post("/api/v1/compliance/ml/verify-and-generate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert len(data["pipeline_stages"]) == 4
        assert "ml_verification" in data
        assert "online_resources" in data
        assert "structured_content" in data
        assert "title" in data["structured_content"]
        assert "answers" in data["structured_content"]
        assert "purpose" in data["structured_content"]["answers"]
        assert "procedure_steps" in data["structured_content"]["answers"]
