import hashlib, json
from app.schemas.generated_document import GeneratedDocument
from app.services.web_analysis_service import web_analysis_service, INDUSTRY_STANDARDS_BENCHMARKS

PROMPT_VERSION = "2.0.0"


def build_generation_request(document, version, template, requirements: dict, evidence_summaries: list | None = None) -> tuple[str, str, str]:
    requirement_context = []
    for code in template.get("requirements", []):
        req = requirements.get(code, {})
        decision = (version.applicability or {}).get(code, {})
        requirement_context.append({
            "internal_reference": code,
            "title": req.get("title", code),
            "source": req.get("source_name", "Unverified source"),
            "source_reference": req.get("source_reference", "Not mapped"),
            "verification_status": req.get("verification_status", "requires_verification"),
            "applicability": decision,
        })

    # Retrieve industry standard benchmarks and quantitative data
    doc_text = f"{document.title} {template.get('name', '')} {version.answers.get('purpose', '')} {version.answers.get('scope', '')}"
    domain_key = web_analysis_service._match_domain_key(doc_text, template.get("category"))
    benchmark = INDUSTRY_STANDARDS_BENCHMARKS.get(domain_key, INDUSTRY_STANDARDS_BENCHMARKS["cleanroom"])

    spec = {
        "document_number": document.document_number,
        "revision": version.revision,
        "title": document.title,
        "document_type": template["name"],
        "sections": template.get("sections", []),
        "answers": version.answers or {},
        "requirement_context": requirement_context,
        "evidence_summaries": evidence_summaries or [],
        "industrial_standards_benchmarks": {
            "primary_standard": benchmark["primary_standard"],
            "related_standards": benchmark["related_standards"],
            "quantitative_parameters": benchmark["parameters"],
            "acceptance_criteria": benchmark["acceptance_criteria"],
            "risk_controls": benchmark["risk_controls"],
            "records_retention": benchmark["records_retention"],
        },
        "output_schema": GeneratedDocument.model_json_schema(),
    }
    payload = json.dumps(spec, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    instructions = (
        "You are an ISO 13485:2016 Certified Lead Quality Auditor and Senior Medical Device QMS Documentation Specialist. "
        "Your task is to generate a concise, authoritative, fully qualified, audit-ready Quality Management System procedure. "
        "\nCRITICAL PLATFORM SPECIFICATION - EXACT SECTION WORD COUNT RANGES & MANDATORY CLAUSE MAPPINGS:\n"
        "Every single section MUST strictly cite its corresponding ISO 13485:2016 clause and adhere to its specific word count range:\n"
        "1. Purpose (section_id: 'purpose', Title: 'Purpose'): 20-40 words. Must cite ISO 13485:2016 §4.1, stating operational controls, regulatory compliance, and QMS quality policy commitment.\n"
        "2. Scope & Applicability (section_id: 'scope', Title: 'Scope & Applicability'): 20-30 words. Must cite ISO 13485:2016 §1.2, defining covered operations, device classes, and design control exclusions.\n"
        "3. Responsibilities (section_id: 'responsibilities', Title: 'Responsibilities'): 20-50 words. Must cite ISO 13485:2016 §5.5, detailing role authorities (Process Owner, QA Manager, Operators, Approver).\n"
        "4. Reference (section_id: 'reference', Title: 'Reference'): 30-60 words. Must cite ISO 13485:2016 §4.2.1 and provide standard traceability mappings for all sections.\n"
        "5. Procedure (section_id: 'procedure', Title: 'Procedure'): 30-70 words. Must cite ISO 13485:2016 §7.1 and §7.5, providing step-by-step instructions with calibrated tolerances, inspection AQL, and ISO 14971 risk controls.\n"
        "6. Records (section_id: 'records', Title: 'Records'): 25-45 words. Must cite ISO 13485:2016 §4.2.5, specifying eDMS storage, retention period (7 years or device lifetime + 2 years), and key forms.\n"
        "7. Revision history (section_id: 'revision_history', Title: 'Revision history'): 25-40 words. Must cite ISO 13485:2016 §4.2.4, documenting revision details, ECO reference, and formal sign-offs.\n\n"
        f"The output 'sections' array MUST have these section_id values: {template.get('sections', [])}. Do NOT use numbers as section_id.\n"
        f"'requirement_refs' for each section must contain ONLY the exact internal_reference code strings from requirement_context (e.g. {template.get('requirements', [])}).\n"
        "Return strictly valid JSON that matches the requested schema with no markdown fences or external prose."
    )
    prompt = (
        "Generate the concise, authoritative ISO 13485:2016 document from this JSON specification. "
        "Strictly cite the required clauses and adhere to the word count limits: "
        "Purpose (§4.1, 20-40 words), Scope (§1.2, 20-30 words), Responsibilities (§5.5, 20-50 words), "
        "Reference (§4.2.1, 30-60 words), Procedure (§7.1/§7.5, 30-70 words), Records (§4.2.5, 25-45 words), "
        "Revision history (§4.2.4, 25-40 words):\n" + payload
    )
    return instructions, prompt, digest
