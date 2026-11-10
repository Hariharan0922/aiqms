from sqlalchemy.orm import Session
from app.models.entities import ValidationRun, DocumentVersion, RequirementReference
from app.rules.engine import RulesEngine, RULESET_VERSION, generation_gate
from app.schemas.validation import ValidationResult
from app.services.audit_service import record_event

class ValidationService:
    def __init__(self, db: Session):
        self.db = db
        self.engine = RulesEngine()

    def validate(self, document, version, template, actor):
        rows = self.db.query(RequirementReference).filter(RequirementReference.code.in_(template.get("requirements", []))).all()
        verified = {row.code for row in rows if row.verification_status == "verified" and row.source_reference.strip() and row.source_edition.strip() and row.verification_note.strip()}
        findings = self.engine.evaluate(template, version.answers or {}, version.applicability or {}, verified_requirements=verified)
        payloads = [item.model_dump(mode="json") for item in findings]
        can_generate = generation_gate(payloads)
        run = ValidationRun(document_version_id=version.id, ruleset_version=RULESET_VERSION,
                            passed=can_generate, findings=payloads)
        self.db.add(run)
        version.validation_status = "passed" if can_generate else "failed"
        if version.status not in {"released", "approved", "in_review", "awaiting_approval"}:
            if not can_generate:
                version.status = "draft"
            elif version.content and version.provider:
                version.status = "generated"
            else:
                version.status = "validated"
        record_event(self.db, actor, "document.validated", "document_version", version.id,
                     {"ruleset_version": RULESET_VERSION, "passed": can_generate, "finding_count": len(payloads)})
        self.db.flush()
        return ValidationResult(document_version_id=version.id, ruleset_version=RULESET_VERSION,
                                passed=can_generate, can_generate=can_generate, findings=findings)

    def assert_generation_allowed(self, version):
        latest = self.db.query(ValidationRun).filter_by(document_version_id=version.id).order_by(ValidationRun.created_at.desc()).first()
        if latest is None or not latest.passed:
            raise ValueError("Run validation and resolve all blocking findings before generation.")
        # A change after validation invalidates readiness; answers edits explicitly reset this state.
        if version.validation_status != "passed":
            raise ValueError("Validation is stale. Run validation again before generation.")
