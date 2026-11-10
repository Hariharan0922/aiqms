import json
import logging
import re
from typing import Any, Optional
import httpx
from app.core.config import settings
from app.services.compliance.prompt_templates import (
    ISO_AUDITOR_SYSTEM_PROMPT,
    build_compliance_prompt,
)

logger = logging.getLogger(__name__)


class OllamaReasoningClient:
    """Client for local LLM reasoning (qwen3:4b) with strict JSON output enforcement."""

    DEFAULT_MODEL = "qwen3:4b"

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 12.0,
    ):
        self.base_url = (base_url or settings.local_model_base_url or "http://localhost:11434").rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.timeout_seconds = timeout_seconds

    def evaluate_evidence(
        self,
        clause_number: str,
        clause_title: str,
        clause_text: str,
        summary_requirements: str,
        document_number: str,
        section_title: str,
        evidence_text: str,
    ) -> dict[str, Any]:
        """Invoke local qwen3:4b to evaluate QMS evidence against an ISO requirement."""
        prompt = build_compliance_prompt(
            clause_number=clause_number,
            clause_title=clause_title,
            clause_text=clause_text,
            summary_requirements=summary_requirements,
            document_number=document_number,
            section_title=section_title,
            evidence_text=evidence_text,
        )

        try:
            raw_response = self._call_ollama_generate(prompt=prompt)
            parsed = self._parse_json_response(raw_response)
            if parsed:
                return parsed
        except Exception as exc:
            logger.warning("Ollama reasoning call failed (%s). Using deterministic rules fallback.", exc)

        # Fallback to rules-based evaluation if LLM is offline or output is invalid
        return self._heuristic_fallback(
            clause_number=clause_number,
            clause_title=clause_title,
            evidence_text=evidence_text,
        )

    def _call_ollama_generate(self, prompt: str) -> str:
        """Call Ollama /api/generate without artificial token caps so thinking models finish cleanly."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
            raise RuntimeError(f"Ollama returned status {resp.status_code}: {resp.text}")

    @staticmethod
    def _parse_json_response(raw_text: str) -> Optional[dict[str, Any]]:
        """Parse structured JSON from model output with cleanup."""
        if not raw_text:
            return None

        # Clean potential markdown fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE).strip()

        # Find outer JSON braces
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        candidate = match.group(0) if match else cleaned

        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                # Standardize verdict
                raw_v = str(data.get("verdict", "")).lower().strip()
                if "non" in raw_v or "not satisfy" in raw_v or "gap" in raw_v:
                    data["verdict"] = "gap_detected"
                elif "partial" in raw_v:
                    data["verdict"] = "partially_compliant"
                elif "not_addressed" in raw_v or "not addressed" in raw_v or "unaddressed" in raw_v:
                    data["verdict"] = "not_addressed"
                elif "compliant" in raw_v or "satisfy" in raw_v or "pass" in raw_v:
                    data["verdict"] = "compliant"
                else:
                    data["verdict"] = "partially_compliant"

                # Validate severity
                valid_severities = {"critical", "major", "minor", "info"}
                sev = str(data.get("severity", "")).lower().strip()
                if sev not in valid_severities:
                    data["severity"] = "major" if data["verdict"] != "compliant" else "info"

                return data
        except Exception:
            pass
        return None

    @staticmethod
    def _heuristic_fallback(
        clause_number: str,
        clause_title: str,
        evidence_text: str,
    ) -> dict[str, Any]:
        """Deterministic rules-based compliance fallback with medical QMS domain ontology."""
        text_lower = evidence_text.lower()

        DOMAIN_SYNONYMS = {
            "4.2.3": ["medical device file", "device master file", "dmf", "specification", "intended use"],
            "4.2.4": ["document", "revision", "sop", "approval", "obsolete", "review", "procedure"],
            "4.2.5": ["record", "register", "dhr", "retention", "form", "log", "archive"],
            "6.4.1": ["environment", "cleanroom", "temperature", "humidity", "work station", "facility"],
            "6.4.2": ["contamination", "particulate", "gowning", "cleaning", "sanitization", "bioburden", "sterility"],
            "7.1": ["planning", "realization", "risk", "objective", "iso 14971"],
            "7.3.5": ["verification", "testing", "test", "inspection", "acceptance", "sample size"],
            "7.3.6": ["validation", "clinical", "user needs", "intended use", "performance test"],
            "7.5.1": ["production", "assembly", "manufacture", "soldering", "work instruction", "batch", "torque", "wiring"],
            "7.5.6": ["validation", "qualification", "iq", "oq", "pq", "process validation", "revalidation"],
            "7.5.8": ["identification", "status", "label", "labeling", "tag"],
            "7.5.9": ["traceability", "lot", "serial", "consignee", "batch number", "dhr"],
            "8.2.4": ["internal audit", "audit", "auditor", "audit schedule"],
            "8.3.1": ["nonconforming", "ncr", "segregation", "disposition", "scrap", "rework", "rejection"],
            "8.5.2": ["corrective action", "capa", "root cause", "recurrence", "effectiveness"],
        }

        matched_synonyms = []
        clause_synonyms = DOMAIN_SYNONYMS.get(clause_number, [])
        for syn in clause_synonyms:
            if syn in text_lower:
                matched_synonyms.append(syn)

        title_words = {w for w in re.findall(r"\w+", clause_title.lower()) if w not in {"of", "and", "the", "for", "in", "to", "a"}}
        text_words = set(re.findall(r"\w+", text_lower))
        title_overlap = len(title_words & text_words)

        has_clause_ref = clause_number in evidence_text

        # 1. Strong match: multiple domain synonyms or direct clause citation
        if len(matched_synonyms) >= 2 or (has_clause_ref and len(matched_synonyms) >= 1):
            return {
                "verdict": "partially_compliant",
                "confidence_score": 0.80,
                "cited_excerpt": evidence_text[:200].strip(),
                "reasoning": f"Evidence section contains active controls matching ISO 13485 Clause {clause_number} ({clause_title}), citing: {', '.join(matched_synonyms)}.",
                "gap_description": "Specific regulatory parameters (e.g. defined limits, formal acceptance sign-off) require verification.",
                "recommended_action": f"Confirm procedure explicitly documents all mandatory records for {clause_title}.",
                "severity": "minor",
            }
        # 2. Moderate match: 1 domain synonym or title keyword overlap
        elif len(matched_synonyms) == 1 or title_overlap >= 2:
            matched_term = matched_synonyms[0] if matched_synonyms else "relevant section context"
            return {
                "verdict": "gap_detected",
                "confidence_score": 0.65,
                "cited_excerpt": evidence_text[:160].strip(),
                "reasoning": f"Evidence references {matched_term} related to Clause {clause_number} ({clause_title}), but omits comprehensive procedural requirements.",
                "gap_description": f"Partial procedural controls found for {clause_title}, but full ISO 13485 requirements are incomplete.",
                "recommended_action": f"Expand section to include complete ISO 13485 clause {clause_number} criteria.",
                "severity": "major",
            }

        # 3. No match
        return {
            "verdict": "not_addressed",
            "confidence_score": 0.60,
            "cited_excerpt": None,
            "reasoning": f"No direct evidence identified for Clause {clause_number} ({clause_title}) in this section.",
            "gap_description": f"Requirement {clause_number} ({clause_title}) appears unaddressed in this document.",
            "recommended_action": f"Incorporate documented controls for {clause_title} into the SOP.",
            "severity": "major",
        }
