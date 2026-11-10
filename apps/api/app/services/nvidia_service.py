"""Dedicated NVIDIA NIM Hosted API Service for Intelligent Document Automation.

Provides resilient, low-latency communication with NVIDIA AI Foundation Models
(https://integrate.api.nvidia.com/v1) for document drafting, structured section
enhancement, single-section regeneration, and connection diagnostics.
"""

from datetime import datetime, timezone
import json
import logging
import re
import ssl
import time
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from app.core.config import settings
from app.schemas.generated_document import GeneratedDocument, GeneratedSection

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NvidiaServiceError(Exception):
    """Base exception for NVIDIA NIM service errors."""
    pass


class NvidiaAuthenticationError(NvidiaServiceError):
    """Raised when the API key is missing or invalid."""
    pass


class NvidiaTimeoutError(NvidiaServiceError):
    """Raised when an API call times out."""
    pass


class NvidiaRateLimitError(NvidiaServiceError):
    """Raised when provider rate limits are exceeded."""
    pass


class NvidiaService:
    """Enterprise client for NVIDIA NIM Hosted API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.nvidia_api_key
        self.base_url = (base_url or settings.nvidia_base_url or "https://integrate.api.nvidia.com/v1").rstrip("/")
        self.model = model or settings.nvidia_model or "poolside/laguna-xs-2.1"
        self.timeout = timeout or settings.nvidia_timeout or 120
        self.max_retries = max_retries if max_retries is not None else settings.nvidia_max_retries

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _sync_http_post(self, endpoint: str, payload: dict) -> dict:
        """Execute a secure synchronous HTTPS request to NVIDIA NIM with retries."""
        if not self.is_configured:
            raise NvidiaAuthenticationError(
                "NVIDIA_API_KEY is not configured in the application environment."
            )

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AiDocMaker-NvidiaClient/1.0",
            "Accept": "application/json",
        }

        ctx = ssl.create_default_context()
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, context=ctx, timeout=self.timeout) as resp:
                    resp_body = resp.read().decode("utf-8")
                    return json.loads(resp_body)
            except urllib.error.HTTPError as exc:
                err_detail = exc.read().decode("utf-8", errors="replace")
                if exc.code == 401:
                    raise NvidiaAuthenticationError(f"NVIDIA API Authentication Failed (401): {err_detail}") from exc
                elif exc.code == 429:
                    last_error = NvidiaRateLimitError(f"NVIDIA API Rate Limit Exceeded (429): {err_detail}")
                    if attempt < self.max_retries:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    raise last_error from exc
                elif exc.code in {502, 503, 504}:
                    last_error = NvidiaServiceError(f"NVIDIA API Gateway Error ({exc.code}): {err_detail}")
                    if attempt < self.max_retries:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise last_error from exc
                else:
                    raise NvidiaServiceError(f"NVIDIA API HTTP {exc.code}: {err_detail}") from exc
            except urllib.error.URLError as exc:
                if "timed out" in str(exc).lower():
                    last_error = NvidiaTimeoutError(f"NVIDIA API Request timed out after {self.timeout}s: {exc}")
                else:
                    last_error = NvidiaServiceError(f"NVIDIA API Network/TLS Error: {exc}")
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise last_error from exc
            except Exception as exc:
                last_error = NvidiaServiceError(f"NVIDIA API Connection Error: {exc}")
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise last_error from exc

        raise last_error or NvidiaServiceError("Unknown failure calling NVIDIA API.")

    def test_connectivity(self) -> Dict[str, Any]:
        """Test live connectivity to NVIDIA NIM, measures response latency and model readiness."""
        if not self.is_configured:
            return {
                "success": False,
                "configured": False,
                "base_url": self.base_url,
                "model": self.model,
                "response_time_ms": None,
                "error": "NVIDIA_API_KEY is not configured.",
                "last_tested": utcnow().isoformat(),
            }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": "Respond with the word 'OK' in a JSON object: {\"status\": \"OK\"}"}
            ],
            "max_tokens": 50,
            "temperature": 0.0,
        }

        t0 = time.time()
        try:
            resp = self._sync_http_post("chat/completions", payload)
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            choices = resp.get("choices", [])
            raw_text = choices[0]["message"]["content"] if choices else ""
            return {
                "success": True,
                "configured": True,
                "base_url": self.base_url,
                "model": self.model,
                "response_time_ms": elapsed_ms,
                "raw_response": raw_text.strip(),
                "request_id": resp.get("id"),
                "usage": resp.get("usage"),
                "last_tested": utcnow().isoformat(),
            }
        except Exception as exc:
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            return {
                "success": False,
                "configured": True,
                "base_url": self.base_url,
                "model": self.model,
                "response_time_ms": elapsed_ms,
                "error": str(exc),
                "last_tested": utcnow().isoformat(),
            }

    @staticmethod
    def extract_json(raw_text: str) -> dict:
        """Extract and parse structured JSON from model responses, handling codeblocks and prose."""
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE).strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        candidate = match.group(0) if match else text
        return json.loads(candidate)

    def generate_document_content(
        self,
        system_instructions: str,
        prompt: str,
        output_schema: dict,
        expected_sections: Optional[List[str]] = None,
    ) -> GeneratedDocument:
        """Generate complete structured document content using NVIDIA NIM."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instructions},
                {
                    "role": "user",
                    "content": f"{prompt}\n\nCRITICAL: Return strictly valid JSON adhering to this schema:\n{json.dumps(output_schema)}",
                },
            ],
            "max_tokens": 4096,
            "temperature": 0.2,
        }

        resp = self._sync_http_post("chat/completions", payload)
        choices = resp.get("choices", [])
        if not choices:
            raise NvidiaServiceError("NVIDIA API returned an empty choices array.")

        msg = choices[0].get("message", {})
        raw_text = msg.get("content") or msg.get("reasoning_content", "")
        if not raw_text:
            raise NvidiaServiceError("NVIDIA API returned empty message content.")

        parsed_data = self.extract_json(raw_text)

        # Normalize and align section IDs if the model numbered sections or used title aliases
        if expected_sections and "sections" in parsed_data and isinstance(parsed_data["sections"], list):
            sections = parsed_data["sections"]
            if len(sections) == len(expected_sections):
                for idx, sec in enumerate(sections):
                    if isinstance(sec, dict) and sec.get("section_id") not in set(expected_sections):
                        # Match title or fallback to template ordering
                        title = str(sec.get("title", "")).lower()
                        matched = next((s for s in expected_sections if s.lower() in title), None)
                        sec["section_id"] = matched or expected_sections[idx]

        return GeneratedDocument.model_validate(parsed_data)

    def regenerate_section(
        self,
        section_id: str,
        section_title: str,
        template: dict,
        answers: dict,
        current_content: dict,
        user_guidance: Optional[str] = None,
    ) -> GeneratedSection:
        """Regenerate a single document section with NVIDIA NIM without overwriting approved sections."""
        instructions = (
            "You are a Quality Management System technical author. Your task is to draft or improve "
            f"a single section: '{section_title}' (id: '{section_id}') for a '{template.get('name', 'Controlled Document')}'. "
            "Use only the provided factual answers and user instructions. "
            "Return valid JSON for a single section with keys: 'section_id', 'title', 'content', 'requirement_refs', 'unresolved_items'."
        )

        user_prompt = {
            "target_section_id": section_id,
            "target_section_title": section_title,
            "template_name": template.get("name"),
            "document_answers": answers,
            "existing_section_content": next(
                (s.get("content") for s in current_content.get("sections", []) if s.get("section_id") == section_id),
                "",
            ),
            "user_refinement_notes": user_guidance or "Enhance clarity, completeness, and audit-readiness.",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": f"Generate the section JSON for this specification:\n{json.dumps(user_prompt)}\n\n"
                               "Return JSON with: {\"section_id\": \"" + section_id + "\", \"title\": \"" + section_title + "\", \"content\": \"...\", \"requirement_refs\": [], \"unresolved_items\": []}",
                },
            ],
            "max_tokens": 1500,
            "temperature": 0.2,
        }

        resp = self._sync_http_post("chat/completions", payload)
        choices = resp.get("choices", [])
        if not choices:
            raise NvidiaServiceError("NVIDIA API returned empty choices for section regeneration.")

        msg = choices[0].get("message", {})
        raw_text = msg.get("content") or msg.get("reasoning_content", "")
        parsed = self.extract_json(raw_text)
        parsed["section_id"] = section_id
        parsed["title"] = parsed.get("title") or section_title
        allowed_reqs = set(template.get("requirements", []))
        if "requirement_refs" in parsed and isinstance(parsed["requirement_refs"], list):
            norm = []
            for r in parsed["requirement_refs"]:
                r_str = str(r).strip()
                if r_str in allowed_reqs:
                    norm.append(r_str)
                else:
                    m = next((code for code in allowed_reqs if code in r_str), None)
                    if m:
                        norm.append(m)
                    else:
                        first_token = r_str.split()[0].rstrip(":,;()[]") if r_str.split() else ""
                        matched_token = next((code for code in allowed_reqs if code.lower() == first_token.lower()), None)
                        if matched_token:
                            norm.append(matched_token)
            parsed["requirement_refs"] = list(dict.fromkeys(norm))

        return GeneratedSection.model_validate(parsed)
