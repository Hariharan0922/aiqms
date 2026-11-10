"""Tests for Milestones 3.5 and 3.6: ISO 13485 Clause-to-QMS Traceability and Rules Engine.

Verifies:
- Correct source mapping with exact document provenance.
- Incorrect/insufficient source mapping detection.
- Missing document references handling (ID, number, section, page).
- Invalid document revisions (draft, temp, empty).
- Missing evidence text.
- Conflicting evidence detection.
- Unverified mappings cannot be approved automatically.
- Reviewer permissions and separation of author/reviewer duties.
- Not-applicable justification validation and Clause 1.2 exclusion limits.
- End-to-end traceability candidate generation and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import Base, SessionLocal, engine
from app.db.migrations import run_migrations
from app.models.compliance import (
    ISOClause,
    ComplianceTraceabilityItem,
    ComplianceTraceabilityRun,
)
from app.models.ingestion import IngestedDocument, IngestedChunk
from app.services.compliance.rules_engine import (
    DeterministicTraceabilityRulesEngine,
    TraceabilityStatus,
)
from app.services.compliance.traceability_service import TraceabilityService


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    session = SessionLocal()

    # Ensure at least one test document and chunk exists in test DB
    doc = session.query(IngestedDocument).first()
    if not doc:
        doc = IngestedDocument(
            id="DOC-TEST-001",
            organization_id="default",
            original_filename="Functionality performance testing.docx",
            file_format="DOCX",
            file_size_bytes=120000,
            checksum_sha256="abc123testchecksum",
            storage_path="sample_documents/Functionality performance testing.docx",
            upload_status="completed",
            processing_status="completed",
            vector_status="indexed",
        )
        session.add(doc)
        session.commit()

        # Add sample chunks
        chunk1 = IngestedChunk(
            id="CHK-TEST-001",
            document_id=doc.id,
            document_number="ETPL/SOP/QMS/42",
            document_revision="00",
            section_number="4.0",
            section_title="Flow Rate Testing Procedure",
            chunk_text=(
                "The organization establishes this documented procedure for evaluating flow rate accuracy. "
                "Tests shall be executed at 0.5 ml/min. Records of all flow measurements shall be maintained "
                "in the test data sheet."
            ),
            page_start=1,
            page_end=2,
            chunk_sequence=1,
            character_count=200,
            embedding_status="completed",
        )
        session.add(chunk1)
        session.commit()

    yield session
    session.close()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestDeterministicTraceabilityRulesEngine:
    """Independently test the deterministic rules engine across all compliance edge cases."""

    def setup_method(self):
        self.engine = DeterministicTraceabilityRulesEngine()

    def test_correct_source_mapping(self):
        """Valid source mapping with substantive procedural and record evidence."""
        res = self.engine.validate_mapping(
            clause_number="4.2.4",
            clause_title="Control of documents",
            requires_procedure=True,
            requires_record=True,
            document_id="DOC-001",
            document_number="ETPL/SOP/QMS/01",
            document_revision="02",
            section_number="4.0",
            section_title="Document Approval and Distribution",
            page_start=3,
            evidence_excerpt=(
                "The organization shall follow this documented procedure for reviewing, approving and "
                "releasing all quality management system documents. Records of document change requests "
                "shall be maintained in the document register."
            ),
            current_status=TraceabilityStatus.EVIDENCE_IDENTIFIED,
        )
        assert res.passed is True
        assert res.status == TraceabilityStatus.EVIDENCE_IDENTIFIED
        assert len(res.findings) == 0

    def test_missing_document_references(self):
        """Missing document ID, document number, and page references."""
        res = self.engine.validate_mapping(
            clause_number="4.2.4",
            clause_title="Control of documents",
            requires_procedure=True,
            requires_record=False,
            document_id=None,
            document_number="",
            document_revision="01",
            section_number=None,
            section_title=None,
            page_start=None,
            evidence_excerpt="Standard procedure for document control shall be followed.",
            current_status=TraceabilityStatus.EVIDENCE_IDENTIFIED,
        )
        assert res.passed is False
        assert res.status == TraceabilityStatus.INSUFFICIENT_EVIDENCE
        finding_codes = [f.code for f in res.findings]
        assert "MISSING_DOC_ID" in finding_codes
        assert "MISSING_DOC_NUMBER" in finding_codes
        assert "MISSING_SECTION_REF" in finding_codes

    def test_invalid_revisions(self):
        """Draft, temporary, or unapproved revisions must be rejected."""
        for bad_rev in ["draft", "temp", "wip", "none", ""]:
            res = self.engine.validate_mapping(
                clause_number="7.5.1",
                clause_title="Control of production and service provision",
                requires_procedure=False,
                requires_record=False,
                document_id="DOC-002",
                document_number="ETPL/WI/05",
                document_revision=bad_rev,
                section_number="1.0",
                section_title="Assembly Instructions",
                page_start=2,
                evidence_excerpt="Production shall be conducted under controlled environmental parameters.",
                current_status=TraceabilityStatus.EVIDENCE_IDENTIFIED,
            )
            assert res.passed is False
            finding_codes = [f.code for f in res.findings]
            assert any("REVISION" in code for code in finding_codes)

    def test_missing_and_insufficient_evidence(self):
        """Empty or excessively brief evidence text must be flagged."""
        # Case 1: Empty evidence
        res_empty = self.engine.validate_mapping(
            clause_number="7.5.6",
            clause_title="Validation of processes",
            requires_procedure=False,
            requires_record=True,
            document_id="DOC-003",
            document_number="ETPL/VAL/01",
            document_revision="00",
            section_number="2.0",
            section_title="Process Validation",
            page_start=5,
            evidence_excerpt="",
            current_status=TraceabilityStatus.NOT_MAPPED,
        )
        assert res_empty.passed is False
        assert res_empty.status == TraceabilityStatus.NOT_MAPPED
        assert any(f.code == "MISSING_EVIDENCE" for f in res_empty.findings)

        # Case 2: Insufficient length
        res_short = self.engine.validate_mapping(
            clause_number="7.5.6",
            clause_title="Validation of processes",
            requires_procedure=False,
            requires_record=True,
            document_id="DOC-003",
            document_number="ETPL/VAL/01",
            document_revision="00",
            section_number="2.0",
            section_title="Process Validation",
            page_start=5,
            evidence_excerpt="Validation is done.",
            current_status=TraceabilityStatus.EVIDENCE_IDENTIFIED,
        )
        assert res_short.passed is False
        assert any(f.code == "INSUFFICIENT_EVIDENCE_LENGTH" for f in res_short.findings)

    def test_missing_mandatory_procedure_control(self):
        """When an ISO clause mandates a procedure, technical excerpts lacking procedural controls fail."""
        res = self.engine.validate_mapping(
            clause_number="7.5.7",
            clause_title="Particular requirements for sterilization validation",
            requires_procedure=True,  # Mandates documented procedure
            requires_record=False,
            document_id="DOC-004",
            document_number="ETPL/SPEC/01",
            document_revision="01",
            section_number="3.2",
            section_title="Device Specifications",
            page_start=8,
            # Text has no procedural or SOP control keywords
            evidence_excerpt="The device is sterilized using ethylene oxide gas at an external facility with standard dosage.",
            current_status=TraceabilityStatus.EVIDENCE_IDENTIFIED,
        )
        assert res.passed is False
        assert any(f.code == "MISSING_PROCEDURAL_CONTROL" for f in res.findings)

    def test_conflicting_evidence_detection(self):
        """Evidence with contradictory statements triggers critical conflict finding."""
        conflicting_text = (
            "If the functionality test fails, personnel must quarantine the unit immediately; "
            "however, operators may continue without quarantine if production deadlines are tight."
        )
        res = self.engine.validate_mapping(
            clause_number="8.3.2",
            clause_title="Actions in response to nonconforming product detected before delivery",
            requires_procedure=True,
            requires_record=True,
            document_id="DOC-005",
            document_number="ETPL/SOP/QMS/42",
            document_revision="00",
            section_number="6.0",
            section_title="Failure Handling",
            page_start=4,
            evidence_excerpt=conflicting_text,
            current_status=TraceabilityStatus.EVIDENCE_IDENTIFIED,
        )
        assert res.passed is False
        assert any(f.code == "CONFLICTING_EVIDENCE" for f in res.findings)

    def test_not_applicable_justification_validity(self):
        """Clause 1.2 prohibits excluding Clause 4/5. Clauses 6-8 require substantive justification."""
        # Case 1: Prohibited exclusion of Clause 4.2.3 (Medical device file)
        res_prohibited = self.engine.validate_mapping(
            clause_number="4.2.3",
            clause_title="Medical device file",
            requires_procedure=False,
            requires_record=True,
            current_status=TraceabilityStatus.NOT_APPLICABLE,
            na_justification="We do not make medical device files.",
        )
        assert res_prohibited.passed is False
        assert any(f.code == "INVALID_NA_EXCLUSION" for f in res_prohibited.findings)

        # Case 2: Permissible exclusion with substantive rationale (e.g. 7.5.5 Sterile requirements for non-sterile device)
        res_valid_na = self.engine.validate_mapping(
            clause_number="7.5.5",
            clause_title="Particular requirements for sterile medical devices",
            requires_procedure=True,
            requires_record=True,
            current_status=TraceabilityStatus.NOT_APPLICABLE,
            na_justification="The device is non-sterile and does not require sterilization or sterile packaging.",
        )
        assert res_valid_na.passed is True
        assert res_valid_na.status == TraceabilityStatus.NOT_APPLICABLE

        # Case 3: Empty justification on permissible clause
        res_empty_na = self.engine.validate_mapping(
            clause_number="7.5.4",
            clause_title="Servicing activities",
            requires_procedure=True,
            requires_record=True,
            current_status=TraceabilityStatus.NOT_APPLICABLE,
            na_justification="N/A",
        )
        assert res_empty_na.passed is False
        assert any(f.code == "MISSING_NA_JUSTIFICATION" for f in res_empty_na.findings)

    def test_reviewer_authorization_and_separation_of_duties(self):
        """Authors cannot verify own mappings; only reviewers/admins can verify."""
        evidence = (
            "The organization establishes a documented procedure for internal audits. "
            "Audit reports and corrective action records shall be maintained."
        )

        # Case 1: Author tries to verify own mapping
        res_author = self.engine.validate_mapping(
            clause_number="8.2.4",
            clause_title="Internal audit",
            requires_procedure=True,
            requires_record=True,
            document_id="DOC-006",
            document_number="ETPL/SOP/QMS/12",
            document_revision="01",
            section_number="3.0",
            section_title="Audit Procedure",
            page_start=2,
            evidence_excerpt=evidence,
            reviewer_role="author",
            reviewer_email="alice@company.com",
            author_email="alice@company.com",
            is_verified_requested=True,
        )
        assert res_author.passed is False
        finding_codes = [f.code for f in res_author.findings]
        assert "UNAUTHORIZED_REVIEWER_ROLE" in finding_codes
        assert "AUTHOR_CANNOT_VERIFY_OWN_WORK" in finding_codes

        # Case 2: Authorized independent reviewer
        res_reviewer = self.engine.validate_mapping(
            clause_number="8.2.4",
            clause_title="Internal audit",
            requires_procedure=True,
            requires_record=True,
            document_id="DOC-006",
            document_number="ETPL/SOP/QMS/12",
            document_revision="01",
            section_number="3.0",
            section_title="Audit Procedure",
            page_start=2,
            evidence_excerpt=evidence,
            reviewer_role="reviewer",
            reviewer_email="bob.reviewer@company.com",
            author_email="alice@company.com",
            is_verified_requested=True,
        )
        assert res_reviewer.passed is True
        assert res_reviewer.status == TraceabilityStatus.VERIFIED_BY_REVIEWER


class TestTraceabilityWorkflowAndAPI:
    """Verify end-to-end traceability service and FastAPI endpoints."""

    def test_traceability_candidate_generation_and_provenance(self, db_session: Session):
        service = TraceabilityService(db=db_session)

        # Find or create a test document
        doc = db_session.query(IngestedDocument).first()
        assert doc is not None, "At least one ingested document must exist"

        run = service.generate_candidate_mappings(
            document_id=doc.id,
            actor_email="qa.lead@company.com",
            similarity_threshold=0.40,
        )
        assert run.status == "completed"
        assert run.total_clauses_evaluated == 88

        # Verify candidate mappings have exact provenance
        items = db_session.query(ComplianceTraceabilityItem).filter_by(run_id=run.id).all()
        assert len(items) == 88

        identified = [i for i in items if i.mapping_status == TraceabilityStatus.EVIDENCE_IDENTIFIED]
        for itm in identified:
            assert itm.document_id == doc.id
            assert itm.document_revision is not None
            assert itm.page_start is not None
            assert itm.evidence_excerpt is not None
            assert len(itm.audit_trail) >= 1

    def test_human_review_workflow_transition(self, db_session: Session):
        service = TraceabilityService(db=db_session)
        doc = db_session.query(IngestedDocument).first()
        run = db_session.query(ComplianceTraceabilityRun).filter_by(document_id=doc.id, status="completed").first()
        if not run:
            run = service.generate_candidate_mappings(document_id=doc.id)

        item = db_session.query(ComplianceTraceabilityItem).filter_by(run_id=run.id).first()
        assert item is not None

        # Ensure valid evidence for review transition test
        item.mapping_status = TraceabilityStatus.EVIDENCE_IDENTIFIED
        item.evidence_excerpt = (
            "The organization establishes this documented procedure for internal quality audits. "
            "Audit records and corrective action reports shall be maintained in the audit registry."
        )
        item.document_number = "ETPL/SOP/QMS/42"
        item.document_revision = "00"
        item.section_number = "4.0"
        item.section_title = "Audit Procedure"
        item.page_start = 1
        item.audit_trail = [{"timestamp": "2026-10-30T10:00:00Z", "action": "candidate_evidence_identified"}]
        db_session.commit()

        # 1. Submit for review
        submitted = service.submit_for_review(item.id, actor_email="author@company.com")
        assert submitted.mapping_status == TraceabilityStatus.PENDING_REVIEW

        # 2. Reviewer approves
        verified = service.review_mapping(
            item_id=item.id,
            decision="verified",
            comment="Section 4.0 adequately addresses procedure and record requirements.",
            actor_role="reviewer",
            actor_email="independent.reviewer@company.com",
            author_email="author@company.com",
        )
        assert verified.mapping_status == TraceabilityStatus.VERIFIED_BY_REVIEWER
        assert verified.reviewed_by == "independent.reviewer@company.com"
        assert verified.reviewer_decision == "verified"
        assert len(verified.audit_trail) >= 3

    def test_traceability_api_endpoints(self, client: TestClient, db_session: Session):
        service = TraceabilityService(db=db_session)
        doc = db_session.query(IngestedDocument).first()
        run = db_session.query(ComplianceTraceabilityRun).filter_by(document_id=doc.id, status="completed").first()
        if not run:
            run = service.generate_candidate_mappings(document_id=doc.id)

        # GET run summary
        res = client.get(f"/api/v1/compliance/traceability/runs/{run.id}")
        assert res.status_code == 200
        data = res.json()
        assert data["run_id"] == run.id
        assert data["total_clauses"] == 88

        # GET run items list
        res_items = client.get(f"/api/v1/compliance/traceability/runs/{run.id}/items")
        assert res_items.status_code == 200
        assert res_items.json()["total_items"] == 88

        # GET single item detail
        sample_item = run.items[0]
        res_detail = client.get(f"/api/v1/compliance/traceability/items/{sample_item.id}")
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["clause_number"] == sample_item.clause_number
        assert "rules_findings" in detail_data
        assert "audit_trail" in detail_data
