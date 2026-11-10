"""Deterministic Rules-Based Evidence Validation Engine for ISO 13485 Traceability.

Independently testable, deterministic rule checks enforcing:
- Document reference completeness
- Valid revisions
- Evidence presence and sufficiency
- Mandatory documented procedure satisfaction
- Mandatory record maintenance satisfaction
- Conflicting evidence detection
- Not-applicable justification constraints (ISO 13485:2016 Clause 1.2)
- Reviewer role permissions and separation of author/reviewer duties
- Prevention of auto-approval based on similarity scores
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional


class TraceabilityStatus:
    NOT_MAPPED = "not_mapped"
    EVIDENCE_IDENTIFIED = "evidence_identified"
    PENDING_REVIEW = "pending_review"
    VERIFIED_BY_REVIEWER = "verified_by_reviewer"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"

    LABELS = {
        NOT_MAPPED: "Not mapped",
        EVIDENCE_IDENTIFIED: "Evidence identified",
        PENDING_REVIEW: "Pending review",
        VERIFIED_BY_REVIEWER: "Verified by reviewer",
        INSUFFICIENT_EVIDENCE: "Insufficient evidence",
        NOT_APPLICABLE: "Not applicable – justification required",
    }


@dataclass
class RuleFinding:
    code: str
    severity: str  # "critical", "major", "minor", "info"
    rule_name: str
    message: str
    field_path: str = ""


@dataclass
class ValidationResult:
    passed: bool
    status: str  # TraceabilityStatus
    findings: List[RuleFinding] = field(default_factory=list)

    @property
    def has_critical_findings(self) -> bool:
        return any(f.severity == "critical" for f in self.findings)

    @property
    def has_major_findings(self) -> bool:
        return any(f.severity == "major" for f in self.findings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status,
            "status_label": TraceabilityStatus.LABELS.get(self.status, self.status),
            "findings_count": len(self.findings),
            "findings": [
                {
                    "code": f.code,
                    "severity": f.severity,
                    "rule_name": f.rule_name,
                    "message": f.message,
                    "field_path": f.field_path,
                }
                for f in self.findings
            ],
        }


class DeterministicTraceabilityRulesEngine:
    """Enterprise deterministic rule evaluation engine for QMS traceability."""

    # Regex patterns indicating procedural controls (using word boundaries to prevent substring collisions)
    PROCEDURE_PATTERNS = [
        r"\bprocedures?\b",
        r"\bsops?\b",
        r"\bwork\s+instructions?\b",
        r"\bwi\b",
        r"\bprotocols?\b",
        r"\bshall\s+document\b",
        r"\bdocumented\s+in\b",
        r"\bdocumented\s+procedures?\b",
        r"\boperating\s+procedures?\b",
        r"\bprocess\s+controls?\b",
        r"\binstructions\s+for\b",
    ]

    # Regex patterns indicating records
    RECORD_PATTERNS = [
        r"\brecords?\b",
        r"\breports?\b",
        r"\bforms?\b",
        r"\blogs?\b",
        r"\bresults?\b",
        r"\bcertificates?\b",
        r"\bdata\s+sheets?\b",
        r"\binspection\s+sheets?\b",
        r"\bsign-?offs?\b",
        r"\bretained\b",
        r"\bmaintenance\s+logs?\b",
        r"\bvalidation\s+reports?\b",
        r"\bbatch\s+records?\b",
    ]

    # Contradiction keywords for conflicting evidence detection
    CONTRADICTION_PAIRS = [
        ("quarantine", "continue without quarantine"),
        ("reject", "accept without review"),
        ("segregate", "do not segregate"),
        ("mandatory", "optional"),
        ("re-test without investigation", "investigate nonconformity"),
    ]

    def validate_mapping(
        self,
        clause_number: str,
        clause_title: str,
        requires_procedure: bool,
        requires_record: bool,
        document_id: Optional[str] = None,
        document_number: Optional[str] = None,
        document_revision: Optional[str] = None,
        section_number: Optional[str] = None,
        section_title: Optional[str] = None,
        page_start: Optional[int] = None,
        evidence_excerpt: Optional[str] = None,
        current_status: str = TraceabilityStatus.NOT_MAPPED,
        na_justification: Optional[str] = None,
        reviewer_role: Optional[str] = None,
        reviewer_email: Optional[str] = None,
        author_email: Optional[str] = None,
        is_verified_requested: bool = False,
    ) -> ValidationResult:
        """Execute complete deterministic rules suite against a clause-to-document mapping candidate."""
        findings: List[RuleFinding] = []

        # ==========================================
        # RULE 1: Not Applicable Justification Check
        # ==========================================
        if current_status == TraceabilityStatus.NOT_APPLICABLE:
            # Check Scope exclusion restrictions (ISO 13485:2016 Clause 1.2)
            root_clause = clause_number.split(".")[0]
            if root_clause in ["4", "5"]:
                findings.append(
                    RuleFinding(
                        code="INVALID_NA_EXCLUSION",
                        severity="critical",
                        rule_name="ISO 13485:2016 Clause 1.2 Exclusion Restriction",
                        message=(
                            f"Clause {clause_number} ({clause_title}) belongs to general QMS (Clause 4/5). "
                            "ISO 13485:2016 Clause 1.2 strictly prohibits exclusions from Clauses 4 or 5."
                        ),
                        field_path="mapping_status",
                    )
                )

            # Check presence and substance of rationale
            if not na_justification or len(na_justification.strip()) < 15:
                findings.append(
                    RuleFinding(
                        code="MISSING_NA_JUSTIFICATION",
                        severity="critical",
                        rule_name="Substantive Justification Required",
                        message=(
                            f"Marking Clause {clause_number} as Not Applicable requires a documented rationale "
                            "explaining why the organization or medical device activities do not apply."
                        ),
                        field_path="na_justification",
                    )
                )

            passed = not any(f.severity == "critical" for f in findings)
            return ValidationResult(
                passed=passed,
                status=TraceabilityStatus.NOT_APPLICABLE if passed else TraceabilityStatus.INSUFFICIENT_EVIDENCE,
                findings=findings,
            )

        # ==========================================
        # RULE 2: Evidence Presence & Sufficiency
        # ==========================================
        clean_evidence = (evidence_excerpt or "").strip()
        if not clean_evidence:
            findings.append(
                RuleFinding(
                    code="MISSING_EVIDENCE",
                    severity="critical",
                    rule_name="Evidence Text Required",
                    message=f"No supporting evidence text has been mapped for Clause {clause_number}.",
                    field_path="evidence_excerpt",
                )
            )
            return ValidationResult(
                passed=False,
                status=TraceabilityStatus.NOT_MAPPED,
                findings=findings,
            )

        if len(clean_evidence) < 30:
            findings.append(
                RuleFinding(
                    code="INSUFFICIENT_EVIDENCE_LENGTH",
                    severity="major",
                    rule_name="Evidence Substantiveness",
                    message=(
                        f"Evidence excerpt for Clause {clause_number} is too short ({len(clean_evidence)} chars). "
                        "Substantive procedural or technical details are required."
                    ),
                    field_path="evidence_excerpt",
                )
            )

        # ==========================================
        # RULE 3: Exact Document Reference Integrity
        # ==========================================
        if not document_id:
            findings.append(
                RuleFinding(
                    code="MISSING_DOC_ID",
                    severity="critical",
                    rule_name="Document Identifier Required",
                    message=f"Source document ID is missing for Clause {clause_number} evidence.",
                    field_path="document_id",
                )
            )

        if not document_number or len(document_number.strip()) < 2:
            findings.append(
                RuleFinding(
                    code="MISSING_DOC_NUMBER",
                    severity="critical",
                    rule_name="Document Number Required",
                    message=f"Controlled document number is missing or empty for Clause {clause_number}.",
                    field_path="document_number",
                )
            )

        if not section_title and not section_number:
            findings.append(
                RuleFinding(
                    code="MISSING_SECTION_REF",
                    severity="major",
                    rule_name="Section Reference Required",
                    message=f"Section reference (number or title) is required for Clause {clause_number}.",
                    field_path="section_number",
                )
            )

        if page_start is None or page_start <= 0:
            findings.append(
                RuleFinding(
                    code="MISSING_PAGE_REF",
                    severity="minor",
                    rule_name="Page Reference Required",
                    message=f"Page reference missing or invalid for Clause {clause_number}.",
                    field_path="page_start",
                )
            )

        # ==========================================
        # RULE 4: Revision Validity Check
        # ==========================================
        if not document_revision or not str(document_revision).strip():
            findings.append(
                RuleFinding(
                    code="MISSING_REVISION",
                    severity="critical",
                    rule_name="Revision Identification",
                    message=f"Document revision must be specified for Clause {clause_number}.",
                    field_path="document_revision",
                )
            )
        else:
            rev_str = str(document_revision).strip().lower()
            if rev_str in ["draft", "temp", "wip", "none", "null"]:
                findings.append(
                    RuleFinding(
                        code="INVALID_REVISION_STATE",
                        severity="critical",
                        rule_name="Released Revision Required",
                        message=(
                            f"Document revision '{document_revision}' indicates unapproved draft state. "
                            "Traceability evidence must reference released, controlled revisions."
                        ),
                        field_path="document_revision",
                    )
                )

        # ==========================================
        # RULE 5: Documented Procedure Requirement
        # ==========================================
        lower_evidence = clean_evidence.lower()
        if requires_procedure:
            has_proc = any(re.search(pat, lower_evidence) for pat in self.PROCEDURE_PATTERNS)
            if not has_proc:
                findings.append(
                    RuleFinding(
                        code="MISSING_PROCEDURAL_CONTROL",
                        severity="major",
                        rule_name="Mandatory Documented Procedure",
                        message=(
                            f"Clause {clause_number} ({clause_title}) mandates a documented procedure. "
                            "The mapped evidence does not cite or reference an SOP, work instruction, or protocol."
                        ),
                        field_path="evidence_excerpt",
                    )
                )

        # ==========================================
        # RULE 6: Record Maintenance Requirement
        # ==========================================
        if requires_record:
            has_rec = any(re.search(pat, lower_evidence) for pat in self.RECORD_PATTERNS)
            if not has_rec:
                findings.append(
                    RuleFinding(
                        code="MISSING_RECORD_RETENTION",
                        severity="major",
                        rule_name="Mandatory Record Maintenance",
                        message=(
                            f"Clause {clause_number} ({clause_title}) mandates maintaining records of conformity. "
                            "The mapped evidence does not identify retained records, reports, forms, or logs."
                        ),
                        field_path="evidence_excerpt",
                    )
                )

        # ==========================================
        # RULE 7: Conflicting Evidence Detection
        # ==========================================
        for phrase_a, phrase_b in self.CONTRADICTION_PAIRS:
            if phrase_a in lower_evidence and phrase_b in lower_evidence:
                findings.append(
                    RuleFinding(
                        code="CONFLICTING_EVIDENCE",
                        severity="critical",
                        rule_name="Evidence Consistency Check",
                        message=(
                            f"Conflicting statements detected in evidence: '{phrase_a}' vs '{phrase_b}'."
                        ),
                        field_path="evidence_excerpt",
                    )
                )

        # ==========================================
        # RULE 8: Reviewer Permission & Duty Separation
        # ==========================================
        if is_verified_requested or current_status == TraceabilityStatus.VERIFIED_BY_REVIEWER:
            if not reviewer_role or reviewer_role.lower() not in ["reviewer", "admin", "approver"]:
                findings.append(
                    RuleFinding(
                        code="UNAUTHORIZED_REVIEWER_ROLE",
                        severity="critical",
                        rule_name="Reviewer Authorization Required",
                        message=(
                            f"User with role '{reviewer_role}' is not authorized to mark Clause {clause_number} "
                            "evidence as 'Verified by reviewer'. Reviewer or Administrator role required."
                        ),
                        field_path="reviewer_role",
                    )
                )

            if author_email and reviewer_email and author_email.strip().lower() == reviewer_email.strip().lower():
                findings.append(
                    RuleFinding(
                        code="AUTHOR_CANNOT_VERIFY_OWN_WORK",
                        severity="critical",
                        rule_name="Independent Review Gate",
                        message=(
                            f"Author '{author_email}' cannot verify their own compliance mappings. "
                            "Independent human review is mandatory under QMS regulations."
                        ),
                        field_path="reviewer_email",
                    )
                )

            # Cannot verify if critical or major findings exist
            if any(f.severity in ["critical", "major"] for f in findings):
                findings.append(
                    RuleFinding(
                        code="BLOCKING_FINDINGS_PREVENT_VERIFICATION",
                        severity="critical",
                        rule_name="Clean Validation Gate",
                        message=(
                            f"Verification blocked: Clause {clause_number} has unresolved critical or major findings."
                        ),
                        field_path="mapping_status",
                    )
                )

        # Determine target status
        criticals = [f for f in findings if f.severity == "critical"]
        majors = [f for f in findings if f.severity == "major"]

        if criticals:
            final_status = TraceabilityStatus.INSUFFICIENT_EVIDENCE
            passed = False
        elif majors:
            final_status = TraceabilityStatus.INSUFFICIENT_EVIDENCE
            passed = False
        else:
            if is_verified_requested and reviewer_role in ["reviewer", "admin", "approver"]:
                final_status = TraceabilityStatus.VERIFIED_BY_REVIEWER
                passed = True
            elif current_status == TraceabilityStatus.PENDING_REVIEW:
                final_status = TraceabilityStatus.PENDING_REVIEW
                passed = True
            else:
                final_status = TraceabilityStatus.EVIDENCE_IDENTIFIED
                passed = True

        return ValidationResult(
            passed=passed,
            status=final_status,
            findings=findings,
        )
