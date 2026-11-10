"""Content Enhancement Service for ISO 13485 Standard Documents.

Performs a 4-stage pipeline:
1. ISO 13485 ML Model Input Verification & Regulatory Comparison
2. Online Resources & Industrial Standards Research (DuckDuckGo + quantitative specs)
3. External Cloud API Structured Generation (NVIDIA NIM / OpenRouter)
4. Schema-Validated Quality Packaging & Verification Scorecard
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.templates.registry import get_template, REQUIREMENTS
from app.models.compliance import ISOClause
from app.providers.base import GenerationRequest
from app.providers.registry import ProviderRegistry
from app.services.compliance.iso_ml_model import ISO13485MLModel
from app.services.web_analysis_service import web_analysis_service

logger = logging.getLogger(__name__)


class ContentEnhancementService:
    """Enhances raw user topic summaries into ISO 13485 structured document content."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    async def enhance_topic_summary(
        self,
        template_id: str,
        summary: str,
        organization_name: Optional[str] = None,
        provider_name: str = "nvidia",
    ) -> Dict[str, Any]:
        """Transform a brief user summary into formal ISO 13485 QMS field answers and applicability."""
        template = get_template(template_id)
        if not template:
            raise ValueError(f"Template '{template_id}' is not recognized.")

        summary_clean = summary.strip()
        if len(summary_clean) < 2:
            raise ValueError("Topic summary or keyword must be at least 2 characters long.")

        # =========================================================================
        # STAGE 1: ISO 13485 ML Model Input Verification & Regulatory Comparison
        # =========================================================================
        ml_model = ISO13485MLModel(db=self.db)
        if not ml_model.is_loaded:
            ml_model.load()

        # Classify top governing ISO clauses
        ml_predictions = ml_model.predict_clause(summary_clean, top_k=5)
        # Perform gap analysis and compliance audit on user input
        ml_audit = ml_model.audit_text(summary_clean)

        # =========================================================================
        # STAGE 2: Online Resources & Industrial Standards Research
        # =========================================================================
        web_analysis = await web_analysis_service.analyze_topic(summary_clean, template.get("category"))

        # Fetch relevant ISO clauses with full context from DB using ML predictions
        iso_context, relevant_clauses_data = self._fetch_relevant_iso_clauses(template, summary_clean, ml_predictions)

        # =========================================================================
        # STAGE 3: Build Structured Instructions & Connect to External Cloud API
        # =========================================================================
        fields = template.get("fields", [])
        requirements = template.get("requirements", [])

        instructions = (
            "You are an ISO 13485:2016 Certified Lead Quality Auditor and Medical Device Quality Management System Specialist. "
            "Your task is to transform a user's brief keyword, short notes, or topic summary into a formal, concise, audit-ready QMS document specification. "
            "CRITICAL PLATFORM SPECIFICATION - EXACT SECTION WORD COUNT RANGES:\n"
            "Each narrative field MUST strictly adhere to its specific word budget:\n"
            "- 'purpose': 20-40 words (operational intent, ISO 13485/FDA compliance, QMS quality policy statement)\n"
            "- 'scope': 20-30 words (operational scope, device classifications, ISO 13485 §1.2 exclusions)\n"
            "- 'procedure' / 'procedure_steps': 30-70 words (line clearance, tolerances, inspection AQL, ISO 14971 risk containment)\n"
            "- 'records': 25-45 words (retention period of 7 years/device lifetime + 2 years, eDMS storage per Clause 4.2.5, key forms)\n"
            "Incorporate concrete industrial standards data values, numerical tolerances, and acceptance criteria. "
            "Return strictly valid JSON matching the requested structure with no markdown code fences or conversational prose."
        )

        field_descriptions = []
        for f in fields:
            req_str = " (REQUIRED)" if f.get("required") else " (OPTIONAL)"
            min_str = f" [minimum {f.get('min_length')} chars]" if f.get("min_length") else ""
            help_str = f": {f.get('help')}" if f.get("help") else ""
            field_descriptions.append(f"- \"{f['key']}\"{req_str}{min_str}{help_str}")

        req_descriptions = []
        for r_code in requirements:
            r_info = REQUIREMENTS.get(r_code, {})
            req_descriptions.append(f"- {r_code}: {r_info.get('title', r_code)} ({r_info.get('source_reference', '')})")

        gaps_bullet_list = "\n".join([f"  * {g}" for g in ml_audit.get("gaps", [])])
        recommendations_bullet_list = "\n".join([f"  * {r}" for r in ml_audit.get("recommendations", [])])

        prompt = (
            f"USER INPUT TOPIC / RAW SUMMARY:\n\"\"\"\n{summary_clean}\n\"\"\"\n\n"
            f"TARGET DOCUMENT TEMPLATE:\n"
            f"- Template ID: {template['id']}\n"
            f"- Template Name: {template['name']}\n"
            f"- Category: {template['category']}\n\n"
            f"ISO 13485:2016 ML MODEL VERIFICATION & GAP COMPARISON FINDINGS:\n"
            f"- Governing Standard: ISO 13485:2016 Clause {ml_audit['target_clause']} ({ml_audit['clause_title']})\n"
            f"- Initial Compliance Score: {ml_audit['compliance_score']}%\n"
            f"- Documented SOP Legally Mandated: {'YES' if ml_audit['requires_documented_procedure'] else 'NO'}\n"
            f"- Quality Records Retention Mandated: {'YES (Clause 4.2.5)' if ml_audit['requires_record'] else 'NO'}\n"
            f"- REGULATORY GAPS IN USER INPUT TO RESOLVE IN GENERATED TEXT:\n{gaps_bullet_list}\n"
            f"- MANDATORY REMEDIATION ACTIONS:\n{recommendations_bullet_list}\n\n"
            f"LIVE WEB & INDUSTRIAL STANDARDS ANALYSIS:\n{web_analysis['enrichment_prompt_text']}\n\n"
            f"RELEVANT ISO 13485:2016 STANDARD CONTEXT:\n{iso_context}\n\n"
            f"TEMPLATE REQUIRED FIELDS TO POPULATE (STRICT WORD LIMITS: purpose 20-40 words, scope 20-30 words, procedure 30-70 words, records 25-45 words):\n" + "\n".join(field_descriptions) + "\n\n"
            f"TEMPLATE REQUIREMENTS FOR APPLICABILITY DECISIONS:\n" + "\n".join(req_descriptions) + "\n\n"
            f"MANDATORY INSTRUCTIONS:\n"
            f"1. Generate a formal, professional Document Title aligned with ISO 13485 and medical device regulations.\n"
            f"2. Generate focused, high-precision answers strictly within the designated word limits: purpose (20-40 words), scope (20-30 words), procedure (30-70 words), records (25-45 words).\n"
            f"3. Include a concise QMS Policy commitment in the purpose field.\n"
            f"4. Address all regulatory gaps identified by the ISO 13485 ML Model.\n"
            f"5. Generate applicability decisions ('applicable' or 'not_applicable') with formal regulatory justification for each requirement.\n\n"
            f"Output strictly a JSON object with this exact schema:\n"
            f"{{\n"
            f"  \"title\": \"Enhanced Document Title\",\n"
            f"  \"answers\": {{\n"
            f"     \"{fields[0]['key']}\": \"...\",\n"
            f"     ...\n"
            f"  }},\n"
            f"  \"applicability\": {{\n"
            f"     \"{requirements[0] if requirements else 'QMS-SAMPLE'}\": {{\"status\": \"applicable\", \"rationale\": \"...\"}},\n"
            f"     ...\n"
            f"  }},\n"
            f"  \"enhancement_summary\": \"Brief 1-2 sentence overview of standards-based improvements made.\"\n"
            f"}}"
        )

        output_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "answers": {"type": "object"},
                "applicability": {"type": "object"},
                "enhancement_summary": {"type": "string"},
            },
            "required": ["title", "answers"],
        }

        # Call External Cloud API or Fallback
        res_data = None
        used_provider = provider_name
        model_id = None

        if provider_name != "offline":
            try:
                registry = ProviderRegistry()
                provider = registry.get(provider_name)
                req = GenerationRequest(
                    system_instructions=instructions,
                    prompt=prompt,
                    output_schema=output_schema,
                    max_output_tokens=3000,
                )
                gen_resp = await provider.generate(req)
                res_data = gen_resp.content
                used_provider = gen_resp.provider
                model_id = gen_resp.model_id
            except Exception as exc:
                logger.warning("External provider '%s' enhancement failed: %s. Falling back to deterministic ISO rules.", provider_name, exc)
                res_data = None

        if not res_data or not isinstance(res_data, dict):
            res_data = self._deterministic_fallback_enhancement(template, summary_clean, organization_name)
            used_provider = "offline"
            model_id = "deterministic-iso-rules"

        # =========================================================================
        # STAGE 4: Normalize, Structure & Package with ML Verification Scorecard
        # =========================================================================
        final_answers = self._normalize_answers(template, res_data.get("answers", {}), summary_clean, organization_name)
        final_applicability = self._normalize_applicability(template, res_data.get("applicability", {}))
        final_title = res_data.get("title") or f"{template['name']}: {summary_clean[:60].strip()}"

        return {
            "template_id": template["id"],
            "template_name": template["name"],
            "title": final_title,
            "answers": final_answers,
            "applicability": final_applicability,
            "relevant_iso_clauses": relevant_clauses_data,
            "provider": used_provider,
            "model_id": model_id,
            "enhancement_summary": res_data.get("enhancement_summary")
            or "Expanded summary into comprehensive ISO 13485:2016 compliant quality controls and retained records.",
            "original_summary": summary_clean,
            # ML Model Verification Metadata
            "ml_verification": {
                "target_clause": ml_audit["target_clause"],
                "clause_title": ml_audit["clause_title"],
                "verdict": ml_audit["verdict"],
                "verdict_label": ml_audit["verdict_label"],
                "initial_compliance_score": ml_audit["compliance_score"],
                "requires_documented_procedure": ml_audit["requires_documented_procedure"],
                "requires_record": ml_audit["requires_record"],
                "strengths": ml_audit["strengths"],
                "gaps": ml_audit["gaps"],
                "recommendations": ml_audit["recommendations"],
                "top_predictions": ml_predictions,
            },
            # Online Resources & Standards Research Metadata
            "online_resources": {
                "matched_domain": web_analysis.get("matched_domain"),
                "primary_standard": web_analysis.get("primary_standard"),
                "related_standards": web_analysis.get("related_standards", []),
                "quantitative_benchmarks": web_analysis.get("quantitative_benchmarks", []),
                "acceptance_criteria": web_analysis.get("acceptance_criteria"),
                "live_web_context": web_analysis.get("live_web_context", []),
            },
        }

    def _fetch_relevant_iso_clauses(self, template: dict, summary: str, ml_predictions: Optional[List[Dict[str, Any]]] = None):
        """Fetch matching ISO 13485 clauses using ML model predictions and database records."""
        fallback = [
            {
                "clause_number": "4.2.4",
                "title": "Control of documents",
                "category": "Quality management system",
                "summary": "Establish documented procedures to define the controls needed for QMS documents.",
                "requires_documented_procedure": True,
                "requires_record": True,
            },
            {
                "clause_number": "4.2.5",
                "title": "Control of records",
                "category": "Quality management system",
                "summary": "Maintain records to provide evidence of conformity to requirements and QMS operation.",
                "requires_documented_procedure": True,
                "requires_record": True,
            },
        ]
        if not self.db:
            return "- ISO 13485:2016 Clause 4.2.4 (Control of documents) & Clause 4.2.5 (Control of records)", fallback

        clauses = []
        # First use top predicted clauses from the ML Model
        if ml_predictions:
            for pred in ml_predictions[:3]:
                c_num = pred.get("clause_number")
                c_rec = self.db.query(ISOClause).filter_by(clause_number=c_num).first()
                if c_rec and c_rec not in clauses:
                    clauses.append(c_rec)

        tokens = [t.lower() for t in re.findall(r"\b[A-Za-z]{4,}\b", summary)]
        tokens.extend([t.lower() for t in re.findall(r"\b[A-Za-z]{4,}\b", template["name"])])

        for token in set(tokens[:8]):
            matches = (
                self.db.query(ISOClause)
                .filter(
                    (ISOClause.title.ilike(f"%{token}%"))
                    | (ISOClause.summary_requirements.ilike(f"%{token}%"))
                )
                .limit(2)
                .all()
            )
            for m in matches:
                if m not in clauses:
                    clauses.append(m)

        if not clauses:
            clauses = self.db.query(ISOClause).filter(ISOClause.level == 3).limit(4).all()

        lines = [
            f"- Clause {c.clause_number} {c.title}: {c.summary_requirements or (c.normative_text[:120] if c.normative_text else '')}"
            for c in clauses[:6]
        ]
        context_str = "\n".join(lines) if lines else "- ISO 13485:2016 General QMS Documentation and Process Controls"

        structured_clauses = [
            {
                "clause_number": c.clause_number,
                "title": c.title,
                "category": c.category,
                "summary": c.summary_requirements or (c.normative_text[:200] if c.normative_text else ""),
                "requires_documented_procedure": bool(getattr(c, "requires_documented_procedure", True)),
                "requires_record": bool(getattr(c, "requires_record", True)),
            }
            for c in clauses[:6]
        ]
        return context_str, structured_clauses or fallback

    def _deterministic_fallback_enhancement(
        self, template: dict, summary: str, organization_name: Optional[str]
    ) -> Dict[str, Any]:
        """Deterministic rules-based enhancement engine producing concise ISO 13485 compliant content adhering to exact word budgets."""
        org = organization_name or "Apex Medical Technologies Ltd."
        clean_sum = summary[:80].strip()
        answers = {}

        for f in template.get("fields", []):
            k = f["key"]
            if k == "organization_name":
                answers[k] = org
            elif "role" in k or "owner" in k:
                answers[k] = "Quality Assurance & Regulatory Compliance Lead. Responsible for process governance, verification, and change authorizations."
            elif k == "purpose":
                answers[k] = (
                    f"This procedure establishes operational controls per ISO 13485:2016 §4.1 for {clean_sum}. "
                    f"{org} is committed to product safety, regulatory compliance, and continuous improvement of QMS effectiveness."
                )
            elif k == "scope":
                answers[k] = (
                    f"This procedure applies to manufacturing and inspection of Class I–III devices at {org}, "
                    f"excluding design per ISO 13485:2016 §1.2 as operations follow released DMRs."
                )
            elif "step" in k or "process" in k or "method" in k or "procedure" in k:
                answers[k] = (
                    f"Per ISO 13485:2016 §7.1 and §7.5, execution follows these controls:\n"
                    f"1. Line Clearance: Verify area cleanliness.\n"
                    f"2. Execution: Perform steps per specifications: {summary[:70].strip()}.\n"
                    f"3. Inspection: Sample per ANSI/ASQ Z1.4 (AQL 0.65).\n"
                    f"4. Risk Control: Quarantine nonconforming product within 1 hour per SOP-QA-08."
                )
            elif "record" in k:
                answers[k] = (
                    f"In accordance with ISO 13485:2016 §4.2.5, all quality records—including line clearance forms, travelers, "
                    f"calibration logs, and nonconformance reports—shall be retained in the eDMS for a minimum of 7 years or device commercial lifetime plus 2 years."
                )
            elif "criteria" in k or "acceptability" in k:
                answers[k] = "100% adherence to engineering drawings, zero visible particulate contamination, and complete dual-operator traveler sign-off."
            elif "escalation" in k:
                answers[k] = "Notify Quality Assurance within 1 hour for nonconformances and escalate safety-critical issues to the Quality Board within 24 hours."
            else:
                answers[k] = f"Controlled operational specifications for {clean_sum} conforming to ISO 13485:2016 quality management standards."

        applicability = {}
        for r in template.get("requirements", []):
            applicability[r] = {
                "status": "applicable",
                "rationale": f"Mandatory compliance requirement under ISO 13485:2016 for medical device quality operations at {org}."
            }

        return {
            "title": f"{template['name']}: {clean_sum[:60]}",
            "answers": answers,
            "applicability": applicability,
            "enhancement_summary": f"Applied deterministic ISO 13485 rules to structure {template['name']} inputs.",
        }

    def _normalize_answers(self, template: dict, raw_answers: dict, summary: str, org_name: Optional[str]) -> dict:
        """Ensure all fields defined in the template exist, are non-empty strings, and meet validation minimums."""
        norm = {}
        fallback_data = self._deterministic_fallback_enhancement(template, summary, org_name)["answers"]

        for f in template.get("fields", []):
            key = f["key"]
            val = raw_answers.get(key)
            min_len = f.get("min_length", 5)

            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            elif val is not None:
                val = str(val).strip()

            if not val or len(val) < min_len:
                val = fallback_data.get(key, f"Standard operational compliance detail for {key} per ISO 13485.")

            norm[key] = val
        return norm

    def _normalize_applicability(self, template: dict, raw_app: dict) -> dict:
        """Ensure every required requirement has a valid applicability status and rationale."""
        norm = {}
        for r in template.get("requirements", []):
            item = raw_app.get(r, {})
            if isinstance(item, dict):
                st = item.get("status")
                rat = item.get("rationale")
            else:
                st = "applicable"
                rat = str(item)

            if st not in {"applicable", "not_applicable"}:
                st = "applicable"
            if not rat or len(str(rat).strip()) < 5:
                rat = f"Requirement {r} is applicable to this operational quality procedure under ISO 13485:2016."

            norm[r] = {"status": st, "rationale": str(rat).strip()}
        return norm
