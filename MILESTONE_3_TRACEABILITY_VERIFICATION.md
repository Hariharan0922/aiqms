# AIQMS — Milestones 3.5 & 3.6 Verification Report
## ISO 13485 Clause-to-QMS Traceability & Deterministic Rules Engine

**Status:** Verified & Fully Passing (11/11 tests, 100% pass rate)  
**Date:** 2026-10-30  
**Test Suite:** `apps/api/tests/test_milestone_3_5_3_6_traceability.py`  
**Standard Evaluated:** ISO 13485:2016 (all 88 canonical clauses)  
**Rules Engine:** `DeterministicTraceabilityRulesEngine` (`apps/api/app/services/compliance/rules_engine.py`)  
**Traceability Service:** `TraceabilityService` (`apps/api/app/services/compliance/traceability_service.py`)  

---

## 1. Executive Summary

Milestones 3.5 and 3.6 deliver an enterprise-grade, deterministic ISO 13485 clause-to-QMS-document traceability system. The engine retrieves candidate evidence chunks across ingested quality documents, captures exact source provenance (document ID, document number, controlled revision, section number/title, chunk ID, and page numbers), assigns mapping confidence, identifies unmapped clauses, and subjects every candidate to a deterministic rules-based validation engine before human review.

### Critical Safety Principles Enforced
1. **Similarity Is Not Compliance:** Vector cosine similarity indicates semantic relevance between query and evidence, **not** regulatory conformity. High similarity scores never directly equate to ISO compliance.
2. **No Automatic Approvals:** Candidate mappings transition at most to `Evidence identified` or `Pending review`. Status `Verified by reviewer` strictly requires an authorized human reviewer decision.
3. **Deterministic & Independently Testable:** The rules engine runs 100% deterministically without relying on non-deterministic external LLMs or heuristic guesses.
4. **Duty Separation:** Authors are strictly prohibited from verifying their own compliance mappings. Independent review is enforced.
5. **Clause 1.2 Scope Exclusion Gate:** Exclusions are restricted to Clauses 6, 7, and 8. Marking general QMS requirements (Clauses 4 or 5) as "Not Applicable" is blocked according to ISO 13485:2016 Clause 1.2.

---

## 2. Canonical Traceability Statuses

The system implements the 6 mandatory traceability statuses:

| Status Code | Display Label | Description & Transition Rule |
|---|---|---|
| `not_mapped` | **Not mapped** | No candidate evidence found exceeding similarity threshold. Identifies gaps. |
| `evidence_identified` | **Evidence identified** | Candidate evidence identified and passed initial structural rule checks. Awaiting author submission. |
| `pending_review` | **Pending review** | Submitted for independent human review. Author cannot alter without resubmitting. |
| `verified_by_reviewer` | **Verified by reviewer** | Formally accepted and verified by an authorized reviewer or administrator. |
| `insufficient_evidence` | **Insufficient evidence** | Evidence fails rule checks (missing references, invalid revision, lack of procedural control, conflicting statements, or reviewer requested changes). |
| `not_applicable` | **Not applicable – justification required** | Permissible clause marked N/A with validated, substantive justification. |

---

## 3. Deterministic Rules Engine Architecture

The rules engine executes 8 independent, deterministic validation checks:

| Rule Code | Rule Description | Enforcement Logic | Severity |
|---|---|---|---|
| `DOC_REF_VALID` | Document Reference Integrity | Validates presence of `document_id`, non-empty `document_number`, section reference, and positive `page_start`. | Critical |
| `REVISION_VALID` | Controlled Revision State | Rejects unapproved drafts (`draft`, `temp`, `wip`, empty) and requires released revision identifiers (e.g. `00`, `01`, `A`). | Critical |
| `EVIDENCE_SUFFICIENT`| Evidence Substantiveness | Enforces non-empty evidence excerpt and minimum substantive character length (>= 30 chars). | Critical / Major |
| `PROCEDURE_REQUIRED`| Mandatory Documented Procedure | If ISO clause mandates a documented procedure (`requires_documented_procedure=True`), evidence must cite or reference an SOP, work instruction, or protocol. | Major |
| `RECORD_REQUIRED` | Mandatory Record Retention | If ISO clause mandates records (`requires_record=True`), evidence must identify retained records, reports, forms, logs, or certificates. | Major |
| `CONFLICTING_EVIDENCE`| Contradiction Detection | Flags contradictory procedural statements (e.g. "quarantine" vs "continue without quarantine"). | Critical |
| `NA_JUSTIFICATION` | Clause 1.2 Exclusion Limits | Enforces ISO 13485 Clause 1.2: excludes exclusions from Clauses 4 & 5. Mandates substantive rationale (>= 15 chars) for Clauses 6–8. | Critical |
| `REVIEWER_AUTH` | Reviewer Role & Duty Separation | Verification requires role `reviewer`, `admin`, or `approver`. Author cannot verify own work. Blocks verification if critical/major findings exist. | Critical |

---

## 4. Empirical Test Suite Results

All 11 automated test cases passed in 13.80 seconds (`apps/api/tests/test_milestone_3_5_3_6_traceability.py`):

```
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestDeterministicTraceabilityRulesEngine::test_correct_source_mapping PASSED [  9%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestDeterministicTraceabilityRulesEngine::test_missing_document_references PASSED [ 18%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestDeterministicTraceabilityRulesEngine::test_invalid_revisions PASSED [ 27%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestDeterministicTraceabilityRulesEngine::test_missing_and_insufficient_evidence PASSED [ 36%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestDeterministicTraceabilityRulesEngine::test_missing_mandatory_procedure_control PASSED [ 45%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestDeterministicTraceabilityRulesEngine::test_conflicting_evidence_detection PASSED [ 54%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestDeterministicTraceabilityRulesEngine::test_not_applicable_justification_validity PASSED [ 63%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestDeterministicTraceabilityRulesEngine::test_reviewer_authorization_and_separation_of_duties PASSED [ 72%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestTraceabilityWorkflowAndAPI::test_traceability_candidate_generation_and_provenance PASSED [ 81%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestTraceabilityWorkflowAndAPI::test_human_review_workflow_transition PASSED [ 90%]
apps/api/tests/test_milestone_3_5_3_6_traceability.py::TestTraceabilityWorkflowAndAPI::test_traceability_api_endpoints PASSED [100%]

============================= 11 passed in 13.80s =============================
```

---

## 5. API Endpoints Implemented & Verified

- `POST /api/v1/compliance/traceability/{document_id}` — Evaluates document chunks against all 88 ISO clauses, generates candidate mappings with exact provenance and initial rule findings.
- `GET /api/v1/compliance/traceability/runs/{run_id}` — Returns run summary counts across all 6 canonical statuses.
- `GET /api/v1/compliance/traceability/runs/{run_id}/items` — Returns all 88 mapping items with filters by `status` and `clause`.
- `GET /api/v1/compliance/traceability/items/{item_id}` — Returns granular item detail including evidence excerpt, exact provenance, rule findings, and audit trail.
- `POST /api/v1/compliance/traceability/items/{item_id}/validate` — Re-runs deterministic rules engine on demand.
- `POST /api/v1/compliance/traceability/items/{item_id}/submit` — Submits candidate mapping for review (`pending_review`).
- `POST /api/v1/compliance/traceability/items/{item_id}/review` — Records human reviewer decision (`verified`, `changes_requested`, `rejected`) with authorization gates.
- `POST /api/v1/compliance/traceability/items/{item_id}/not-applicable` — Marks clause as N/A with documented justification.
- `POST /api/v1/compliance/traceability/items/{item_id}/link` — Manually links a specific chunk as supporting evidence.

---

## 6. Conclusion & Next Steps

Milestones 3.5 and 3.6 are complete and verified. The system now proceeds to **Milestone 3.7**: Local LLM Evidence Analysis utilizing Ollama with `qwen3:4b`, operating strictly on retrieved ISO requirements and QMS evidence, generating structured JSON explanations while keeping the deterministic rules engine completely independent.
