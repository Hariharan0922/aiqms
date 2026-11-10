"""Prompt templates for zero-hallucination ISO 13485 compliance reasoning."""

from typing import Optional

ISO_AUDITOR_SYSTEM_PROMPT = """You are a certified ISO 13485:2016 Lead Quality Auditor for medical devices.
Your task is to objectively evaluate whether the provided evidence excerpt from a Quality Management System (QMS) document satisfies a specific ISO 13485:2016 clause requirement.

STRICT AUDIT RULES:
1. Ground your judgment STRICTLY in the provided evidence excerpt and metadata. Do NOT fabricate, assume, extrapolate, or invent procedures that are not explicitly stated.
2. If evidence is empty, missing, or purely trivial, return verdict "insufficient_evidence".
3. If the excerpt clearly and adequately fulfills the clause requirements, return verdict "compliant".
4. If the excerpt addresses some aspects of the clause but omits mandatory elements (such as procedure controls, record retention, approval sign-off, or defined limits), return verdict "partially_compliant" and list the missing elements in "missing_evidence".
5. If the excerpt contains contradictory instructions (e.g. conflicting actions on failure or contradictory revision claims), return verdict "gap_detected" and list the conflict in "inconsistencies".
6. If the excerpt is unrelated to the requirement, return verdict "not_addressed".
7. PROVENANCE INTEGRITY: In "cited_document_number", "cited_revision", "cited_section", and "cited_pages", cite ONLY the exact values provided in the metadata. Do NOT invent other document numbers or clause numbers.
8. In "cited_evidence_excerpt", quote the exact verbatim phrase or sentence from the evidence text that supports your finding.
9. You must respond ONLY with a single valid JSON object matching the requested schema. No surrounding text, no conversational filler, no markdown formatting outside the JSON block.
"""


def build_evidence_analysis_prompt(
    clause_number: str,
    clause_title: str,
    clause_text: str,
    summary_requirements: str,
    document_number: Optional[str] = None,
    document_revision: Optional[str] = None,
    section_number: Optional[str] = None,
    section_title: Optional[str] = None,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
    evidence_text: Optional[str] = None,
) -> str:
    """Build standardized, grounded audit prompt for local LLMs (qwen3:4b / qwen3:8b)."""
    doc_num_str = document_number or "UNSPECIFIED"
    doc_rev_str = document_revision or "UNSPECIFIED"
    sec_str = f"{section_number or ''} {section_title or ''}".strip() or "UNSPECIFIED"
    pages_str = f"Page {page_start}-{page_end}" if page_start else "UNSPECIFIED"
    evidence_clean = (evidence_text or "").strip() or "[NO EVIDENCE PROVIDED - EMPTY EXCERPT]"

    return f"""ISO 13485:2016 AUDIT EVIDENCE EVALUATION TASK:

TARGET REQUIREMENT:
Standard: ISO 13485:2016
Clause: {clause_number} — {clause_title}
Normative Text:
{clause_text}

Key Summary Requirements:
{summary_requirements}

SUBMITTED QMS EVIDENCE:
Document Number: {doc_num_str}
Document Revision: {doc_rev_str}
Section: {sec_str}
Source Page(s): {pages_str}
Evidence Excerpt:
\"\"\"
{evidence_clean}
\"\"\"

INSTRUCTIONS:
Evaluate whether the submitted evidence satisfies Clause {clause_number}.
Check for missing procedural controls, missing records, contradictions, or unsupported claims.
Cite exact document metadata without inventing citations.
Respond with ONLY a JSON object formatted according to this exact structure:
{{
  "verdict": "compliant" | "partially_compliant" | "gap_detected" | "not_addressed" | "insufficient_evidence",
  "confidence": 0.85,
  "explanation": "Clear professional explanation of how the excerpt relates to the ISO requirement",
  "cited_evidence_excerpt": "Exact quotation from the evidence excerpt",
  "cited_document_number": "{doc_num_str}",
  "cited_revision": "{doc_rev_str}",
  "cited_section": "{sec_str}",
  "cited_pages": "{pages_str}",
  "missing_evidence": ["Specific missing element 1", "Specific missing element 2"],
  "inconsistencies": ["Specific inconsistency or contradiction 1"],
  "unsupported_conclusions_detected": false,
  "recommended_remediation": "Actionable step to close any identified gaps"
}}
"""

# Backwards-compatibility alias
build_compliance_prompt = build_evidence_analysis_prompt
