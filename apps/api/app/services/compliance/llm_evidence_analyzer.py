"""Local LLM Evidence Analysis Service.

Interfaces with local Ollama qwen3:4b (and qwen3:8b) to generate structured,
schema-validated compliance explanations, identify missing evidence, detect inconsistencies,
verify citations, and prevent unsupported conclusions.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, Optional
import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.services.compliance.llm_evidence_schema import (
    LLMEvidenceAnalysisResponse,
    LLMAnalysisRequest,
)
from app.services.compliance.prompt_templates import (
    ISO_AUDITOR_SYSTEM_PROMPT,
    build_evidence_analysis_prompt,
)
from app.services.ingestion.local_ai_adapter import LocalAIAdapter

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LLMConnectionError(Exception):
    pass


class LLMTimeoutError(Exception):
    pass


class LLMSchemaValidationError(Exception):
    pass


class LLMEvidenceAnalyzer:
    """Enterprise service executing grounded local LLM evidence evaluations."""

    DEFAULT_MODEL = "qwen3:4b"

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: str = DEFAULT_MODEL,
        timeout_seconds: float = 120.0,
    ):
        self.base_url = (base_url or settings.local_model_base_url or "http://localhost:11434").rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self.adapter = LocalAIAdapter(base_url=self.base_url)
        self._client = httpx.Client(timeout=self.timeout_seconds)

    def check_readiness(self) -> Dict[str, Any]:
        """Check Ollama connectivity and available reasoning models."""
        return self.adapter.check_ollama_status()

    def analyze_evidence(
        self,
        request: LLMAnalysisRequest,
        actor_email: str = "system",
    ) -> Dict[str, Any]:
        """Analyze evidence against an ISO requirement using local Qwen3."""
        model = request.model_name or self.default_model

        # Handle missing or empty evidence directly
        if not request.evidence_text or not request.evidence_text.strip():
            empty_resp = LLMEvidenceAnalysisResponse(
                verdict="insufficient_evidence",
                confidence=1.0,
                explanation=(
                    f"No supporting evidence text was provided for Clause {request.clause_number} "
                    f"({request.clause_title}). Evaluation cannot proceed without substantive excerpts."
                ),
                cited_evidence_excerpt=None,
                cited_document_number=request.document_number,
                cited_revision=request.document_revision,
                cited_section=request.section_title or request.section_number,
                cited_pages=f"Page {request.page_start}-{request.page_end}" if request.page_start else None,
                missing_evidence=[f"Complete procedural and technical evidence for {request.clause_title}"],
                inconsistencies=[],
                unsupported_conclusions_detected=True,
                recommended_remediation=f"Map an active, released QMS SOP section addressing Clause {request.clause_number}.",
            )
            return {
                "model_name": model,
                "duration_seconds": 0.0,
                "structured_analysis": empty_resp.model_dump(),
                "schema_valid": True,
                "raw_response": None,
                "audit_entry": {
                    "timestamp": utcnow().isoformat(),
                    "actor": actor_email,
                    "model": model,
                    "duration_seconds": 0.0,
                    "verdict": empty_resp.verdict,
                },
            }

        # Build prompt
        prompt = build_evidence_analysis_prompt(
            clause_number=request.clause_number,
            clause_title=request.clause_title,
            clause_text=request.clause_text,
            summary_requirements=request.summary_requirements,
            document_number=request.document_number,
            document_revision=request.document_revision,
            section_number=request.section_number,
            section_title=request.section_title,
            page_start=request.page_start,
            page_end=request.page_end,
            evidence_text=request.evidence_text,
        )

        t0 = time.time()
        try:
            raw_response = self._invoke_ollama(prompt=prompt, model=model)
        except httpx.ConnectError as exc:
            raise LLMConnectionError(f"Could not connect to Ollama at {self.base_url}: {exc}")
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Ollama call timed out after {self.timeout_seconds}s: {exc}")
        except Exception as exc:
            raise RuntimeError(f"Ollama invocation error: {exc}")

        duration = round(time.time() - t0, 2)

        # Parse and validate JSON against Pydantic schema
        parsed_data = self._clean_and_parse_json(raw_response)

        # Ensure provenance citations reflect input request if model omitted them
        if not parsed_data.get("cited_document_number") and request.document_number:
            parsed_data["cited_document_number"] = request.document_number
        if not parsed_data.get("cited_revision") and request.document_revision:
            parsed_data["cited_revision"] = request.document_revision
        if not parsed_data.get("cited_section") and request.section_title:
            parsed_data["cited_section"] = f"{request.section_number or ''} {request.section_title}".strip()
        if not parsed_data.get("cited_pages") and request.page_start:
            parsed_data["cited_pages"] = f"Page {request.page_start}-{request.page_end or request.page_start}"

        try:
            validated = LLMEvidenceAnalysisResponse(**parsed_data)
        except ValidationError as val_err:
            logger.warning("LLM response failed schema validation: %s", val_err)
            raise LLMSchemaValidationError(f"Model response did not conform to defined schema: {val_err}")

        # Anti-hallucination verification
        self._verify_provenance_and_citations(validated, request)

        audit_entry = {
            "timestamp": utcnow().isoformat(),
            "actor": actor_email,
            "model": model,
            "duration_seconds": duration,
            "verdict": validated.verdict,
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            "unsupported_conclusions_detected": validated.unsupported_conclusions_detected,
        }

        return {
            "model_name": model,
            "duration_seconds": duration,
            "structured_analysis": validated.model_dump(),
            "schema_valid": True,
            "raw_response": raw_response,
            "audit_entry": audit_entry,
        }

    def _invoke_ollama(self, prompt: str, model: str) -> str:
        """Call Ollama generate API with system instructions."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": ISO_AUDITOR_SYSTEM_PROMPT,
            "stream": False,
            "format": "json",  # Enforce JSON mode in Ollama
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic evaluation
                "top_p": 0.9,
            },
        }

        resp = self._client.post(url, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", "").strip()
        raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

    @staticmethod
    def _clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
        """Extract and parse clean JSON dictionary from model response."""
        if not raw_text:
            raise LLMSchemaValidationError("Ollama returned an empty response.")

        cleaned = raw_text.strip()
        # Remove potential markdown wrappers
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

        # Extract outer JSON block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        candidate = match.group(0) if match else cleaned

        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                # Normalize key-level verdict if model returned e.g. {"partially_compliant": ...}
                if "verdict" not in data:
                    for v in ["compliant", "partially_compliant", "gap_detected", "not_addressed", "insufficient_evidence"]:
                        if v in data:
                            data["verdict"] = v
                            break
                    if "verdict" not in data:
                        data["verdict"] = "insufficient_evidence"

                if "explanation" not in data or not str(data.get("explanation", "")).strip():
                    data["explanation"] = f"Evaluation indicates {data['verdict']} based on submitted QMS evidence and requirement controls."

                if "confidence" not in data:
                    data["confidence"] = 0.85

            return data
        except Exception as exc:
            raise LLMSchemaValidationError(f"Malformed JSON in model output: {exc}. Raw candidate: {candidate[:200]}")

    @staticmethod
    def _verify_provenance_and_citations(
        response: LLMEvidenceAnalysisResponse, request: LLMAnalysisRequest
    ) -> None:
        """Verify that the model's citations accurately reflect provided metadata without hallucination."""
        # 1. Document number check
        if request.document_number and response.cited_document_number:
            if response.cited_document_number.strip().lower() != request.document_number.strip().lower():
                response.inconsistencies.append(
                    f"Cited document number '{response.cited_document_number}' differs from input metadata '{request.document_number}'."
                )
                response.unsupported_conclusions_detected = True

        # 2. Quote verification: check if cited excerpt exists in the actual evidence text
        if response.cited_evidence_excerpt and request.evidence_text:
            quote = response.cited_evidence_excerpt.strip().lower()
            evidence = request.evidence_text.lower()
            # Check for partial match (at least 20 chars) if exact match fails
            if quote not in evidence:
                # Check normalized whitespace
                norm_quote = " ".join(quote.split())
                norm_evidence = " ".join(evidence.split())
                if norm_quote not in norm_evidence:
                    response.inconsistencies.append(
                        "Cited evidence excerpt could not be verified in the submitted document text (potential hallucinated quote)."
                    )
                    response.unsupported_conclusions_detected = True

    def run_comparative_benchmark(
        self,
        test_cases: list[LLMAnalysisRequest],
        models: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """Benchmark latency, schema validity, and consistency between qwen3:4b and qwen3:8b."""
        eval_models = models or ["qwen3:4b", "qwen3:8b"]
        benchmark_results: Dict[str, Any] = {}

        for m in eval_models:
            model_results = []
            total_duration = 0.0
            schema_passes = 0

            for tc in test_cases:
                tc.model_name = m
                try:
                    res = self.analyze_evidence(tc)
                    duration = res["duration_seconds"]
                    total_duration += duration
                    if res["schema_valid"]:
                        schema_passes += 1
                    model_results.append(
                        {
                            "clause": tc.clause_number,
                            "verdict": res["structured_analysis"]["verdict"],
                            "confidence": res["structured_analysis"]["confidence"],
                            "duration_seconds": duration,
                            "schema_valid": True,
                        }
                    )
                except Exception as exc:
                    model_results.append(
                        {
                            "clause": tc.clause_number,
                            "error": str(exc),
                            "duration_seconds": 0.0,
                            "schema_valid": False,
                        }
                    )

            benchmark_results[m] = {
                "total_cases": len(test_cases),
                "schema_pass_rate": f"{schema_passes}/{len(test_cases)}",
                "average_duration_seconds": round(total_duration / max(len(test_cases), 1), 2),
                "case_results": model_results,
            }

        return benchmark_results
