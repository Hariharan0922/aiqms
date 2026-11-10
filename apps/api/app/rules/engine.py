from datetime import date
from typing import Any
from app.schemas.validation import ValidationFinding, ValidationResult, Severity

RULESET_VERSION = "1.0.0"


class RulesEngine:
    """Deterministic rules only; no model call happens in this module."""
    def evaluate(self, template: dict, answers: dict[str, Any], applicability: dict[str, Any], verified_requirements: set[str] | None = None) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        verified_requirements = verified_requirements or set()
        for field in template.get("fields", []):
            key = field["key"]
            value = answers.get(key)
            required = bool(field.get("required", False))
            required_if = field.get("required_if")
            if required_if:
                required = required or answers.get(required_if.get("field")) == required_if.get("equals")
            empty = value is None or (isinstance(value, str) and not value.strip()) or value == []
            if required and empty:
                findings.append(ValidationFinding(
                    code="FIELD_REQUIRED", field_path=key, severity=Severity.BLOCKER,
                    message=f"{field['label']} is required.", question=field.get("question") or f"Please provide {field['label'].lower()}.",
                    blocks_generation=True,
                ))
                continue
            if empty:
                continue
            if field.get("type") in {"text", "textarea", "select", "date"} and not isinstance(value, str):
                findings.append(ValidationFinding(code="FIELD_TYPE_INVALID", field_path=key, severity=Severity.ERROR,
                    message=f"{field['label']} must be text.", question=f"Enter a valid value for {field['label']}.", blocks_generation=True))
                continue
            if isinstance(value, str):
                min_length = int(field.get("min_length", 0))
                if len(value.strip()) < min_length:
                    findings.append(ValidationFinding(code="FIELD_TOO_SHORT", field_path=key, severity=Severity.ERROR,
                        message=f"{field['label']} must contain at least {min_length} characters.",
                        question=f"Please add more detail to {field['label'].lower()}.", blocks_generation=True))
                options = field.get("options")
                if options and value not in options:
                    findings.append(ValidationFinding(code="FIELD_OPTION_INVALID", field_path=key, severity=Severity.ERROR,
                        message=f"Select a valid option for {field['label']}.", blocks_generation=True))
                if field.get("type") == "date":
                    try:
                        date.fromisoformat(value)
                    except ValueError:
                        findings.append(ValidationFinding(code="FIELD_DATE_INVALID", field_path=key, severity=Severity.ERROR,
                            message=f"{field['label']} must use YYYY-MM-DD.", blocks_generation=True))
        for code in template.get("requirements", []):
            if code not in verified_requirements:
                findings.append(ValidationFinding(
                    code="REQUIREMENT_MAPPING_UNVERIFIED", field_path=f"requirements.{code}", severity=Severity.WARNING,
                    message=f"The internal mapping for {code} has not been verified against licensed source material.",
                    question="Confirm this mapping with the controlled requirements library before release.",
                    requirement_id=code, blocks_generation=False,
                ))
            choice = applicability.get(code, {})
            status = choice.get("status", "pending") if isinstance(choice, dict) else "pending"
            rationale = (choice.get("rationale", "") if isinstance(choice, dict) else "").strip()
            if status not in {"applicable", "not_applicable"}:
                findings.append(ValidationFinding(
                    code="APPLICABILITY_UNRESOLVED", field_path=f"applicability.{code}", severity=Severity.BLOCKER,
                    message=f"Applicability decision is required for {code}.",
                    question=f"Is {code.replace('-', ' ').lower()} applicable to this document? Record the decision and rationale.",
                    requirement_id=code, blocks_generation=True,
                ))
            elif status == "not_applicable" and not rationale:
                findings.append(ValidationFinding(
                    code="APPLICABILITY_RATIONALE_REQUIRED", field_path=f"applicability.{code}.rationale", severity=Severity.BLOCKER,
                    message=f"A rationale is required when {code} is marked not applicable.",
                    question=f"Explain why {code} is not applicable.", requirement_id=code, blocks_generation=True,
                ))
        return findings


def generation_gate(findings: list[dict] | list[ValidationFinding]) -> bool:
    for finding in findings:
        if isinstance(finding, dict):
            if finding.get("blocks_generation", False) and not finding.get("resolved", False):
                return False
        elif finding.blocks_generation and not finding.resolved:
            return False
    return True
