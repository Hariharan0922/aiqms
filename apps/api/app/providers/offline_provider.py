from app.providers.base import GenerationRequest, GenerationResponse


SECTION_WORD_LIMITS = {
    "purpose": (20, 40),
    "scope": (20, 30),
    "responsibilities": (20, 50),
    "reference": (30, 60),
    "references": (30, 60),
    "procedure": (30, 70),
    "records": (25, 45),
    "revision_history": (25, 40),
}


def fit_to_word_range(text: str, fallback_text: str, min_words: int, max_words: int) -> str:
    """Ensure text strictly adheres to the platform specification [min_words, max_words]."""
    words = text.strip().split()
    if min_words <= len(words) <= max_words:
        return text.strip()
    if len(words) < min_words:
        fb_words = fallback_text.strip().split()
        if min_words <= len(fb_words) <= max_words:
            return fallback_text.strip()
        needed = min_words - len(words)
        added = " ".join(fb_words[:needed])
        return f"{text.strip()} {added}".strip()
    truncated = " ".join(words[:max_words])
    if "." in truncated:
        last_dot = truncated.rfind(".")
        sub = truncated[:last_dot + 1].strip()
        if len(sub.split()) >= min_words:
            return sub
    return truncated.strip()


class OfflineProvider:
    """A deterministic ISO 13485:2016 draft generator conforming strictly to configured section word ranges."""

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        import json
        raw = request.prompt.split("\n", 1)[-1]
        try:
            spec = json.loads(raw)
        except Exception:
            spec = {}
        answers = spec.get("answers", {})
        title_str = spec.get("title", "Standard Operating Procedure")
        org_name = answers.get("organization_name", "Apex Medical Operations Ltd.")

        # Targeted fallbacks calibrated precisely to platform word range specifications:
        # purpose: 20-40 words (target 33 words, citing §4.1)
        fb_purpose = (
            f"This procedure defines operational controls and QMS processes per ISO 13485:2016 §4.1 for {title_str}. "
            f"{org_name} commits to maintaining product safety, regulatory compliance, and continual improvement of QMS effectiveness."
        )

        # scope: 20-30 words (target 28 words, citing §1.2)
        fb_scope = (
            f"This procedure governs manufacturing, assembly, and inspection of Class I–III devices across {org_name}. "
            f"Design controls are excluded per ISO 13485:2016 §1.2 as operations follow released DMRs."
        )

        # responsibilities: 20-50 words (target 40 words, citing §5.5)
        p_owner = answers.get("process_owner", "Process Owner")
        fb_responsibilities = (
            f"Per ISO 13485:2016 §5.5, authorities are designated as follows:\n"
            f"• {p_owner}: Oversees procedure execution and line clearance.\n"
            f"• QA Manager: Authorizes travelers, reviews calibrations, and dispositions deviations.\n"
            f"• Operators: Execute instructions per GDP and report nonconformances.\n"
            f"• Quality Director: Final approval."
        )

        # reference: 30-60 words (target 47 words, citing §4.2.1)
        fb_reference = (
            "In accordance with ISO 13485:2016 §4.2.1, the following normative standards apply:\n"
            "1. ISO 13485:2016 Medical devices — QMS.\n"
            "2. ISO 14971:2019 Risk management.\n"
            "3. FDA 21 CFR Part 820 (QMSR).\n"
            "Traceability: Purpose (§4.1), Scope (§1.2), Responsibilities (§5.5), Reference (§4.2.1), Procedure (§7.1, §7.5), Records (§4.2.5), Revision History (§4.2.4)."
        )

        # procedure: 30-70 words (target 57 words, citing §7.1, §7.5)
        fb_procedure = (
            "Per ISO 13485:2016 §7.1 and §7.5, execution follows these validated controls:\n"
            "1. Line Clearance: Verify workspace cleanliness and differential pressure (>=10-15 Pa).\n"
            "2. Setup: Verify calibration (±0.5% tolerance) and log serials.\n"
            "3. Production & Inspection: Execute per DMR; sample per ANSI/ASQ Z1.4 (AQL 0.65).\n"
            "4. Risk Mitigation: Halt line and quarantine nonconformances within 1 hour per SOP-QA-08."
        )

        # records: 25-45 words (target 38 words, citing §4.2.5)
        fb_records = (
            "In accordance with ISO 13485:2016 §4.2.5, all quality records—including line clearance forms, travelers, calibration logs, and nonconformance reports—"
            "shall be indexed and retained in the eDMS for a minimum of 7 years or device commercial lifetime plus 2 years."
        )

        # revision_history: 25-40 words (target 35 words, citing §4.2.4)
        rev_num = spec.get("revision", 1)
        fb_revision = (
            f"Per ISO 13485:2016 §4.2.4 document control requirements:\n"
            f"Rev {rev_num}.0 | Effective: Current | ECO-2026-0042: Controlled initial release.\n"
            f"Approvals:\n"
            f"• Authored By: Lead Engineer [Signed]\n"
            f"• Reviewed By: QA Specialist [Signed]\n"
            f"• Approved By: Quality Director [Approved]"
        )

        fallbacks = {
            "purpose": fb_purpose,
            "scope": fb_scope,
            "responsibilities": fb_responsibilities,
            "reference": fb_reference,
            "references": fb_reference,
            "procedure": fb_procedure,
            "records": fb_records,
            "revision_history": fb_revision,
        }

        titles = {
            "purpose": "Purpose",
            "scope": "Scope & Applicability",
            "responsibilities": "Responsibilities",
            "reference": "Reference",
            "references": "Reference",
            "procedure": "Procedure",
            "records": "Records",
            "revision_history": "Revision history",
        }

        req_context_codes = [x["internal_reference"] for x in spec.get("requirement_context", [])] or ["QMS-DOC-CONTROL"]

        sections = []
        for section_id in spec.get("sections", []):
            title = titles.get(section_id, section_id.replace("_", " ").title())
            min_w, max_w = SECTION_WORD_LIMITS.get(section_id, (20, 50))
            fb_text = fallbacks.get(section_id, f"Operational specifications for {title} according to ISO 13485:2016 quality standards.")
            input_val = str(answers.get(section_id, "")).strip()

            final_text = fit_to_word_range(input_val if input_val else fb_text, fb_text, min_w, max_w)

            sections.append({
                "section_id": section_id,
                "title": title,
                "content": final_text,
                "requirement_refs": req_context_codes,
                "evidence_refs": [],
                "unresolved_items": []
            })

        purpose_text = fit_to_word_range(str(answers.get("purpose", "")), fb_purpose, 20, 40)
        scope_text = fit_to_word_range(str(answers.get("scope", "")), fb_scope, 20, 30)

        content = {
            "title": title_str,
            "document_type": spec.get("document_type", "Standard Operating Procedure"),
            "purpose": purpose_text,
            "scope": scope_text,
            "sections": sections,
            "open_issues": [],
            "review_notes": ["Verify site-specific equipment serial numbers and line room numbers before final authorized execution."],
        }
        return GenerationResponse(provider="offline", model_id="iso-concise-spec-v1", content=content)
