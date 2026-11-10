import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.schemas.generated_document import GeneratedDocument, GeneratedSection
from app.providers.base import GenerationRequest, GenerationResponse
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OpenRouterProvider:
    """OpenRouter provider adapter supporting thousands of LLMs through a unified OpenAI-compatible gateway."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.openrouter_api_key
        self.base_url = (base_url or settings.openrouter_base_url).rstrip("/")
        self.model = model or settings.openrouter_model

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    @staticmethod
    def extract_json(raw_text: str) -> dict:
        """Extract and parse structured JSON from model responses, handling codeblocks, reasoning tags, and prose."""
        text = raw_text.strip()
        # Remove reasoning tags if any remain in text
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except Exception:
            pass

        # Strip markdown code fences
        text_clean = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text_clean = re.sub(r"\s*```$", "", text_clean, flags=re.MULTILINE).strip()
        try:
            return json.loads(text_clean)
        except Exception:
            pass

        # Look for JSON object bounds
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass

        raise ValueError(f"Could not parse valid JSON from response: {text[:200]}")

    def test_connectivity(self) -> Dict[str, Any]:
        """Test live connectivity and verify key validity against OpenRouter API."""
        if not self.is_configured:
            return {
                "success": False,
                "configured": False,
                "base_url": self.base_url,
                "model": self.model,
                "response_time_ms": None,
                "error": "OPENROUTER_API_KEY is not configured.",
                "last_tested": utcnow().isoformat(),
            }

        t0 = time.time()
        url = f"{self.base_url}/auth/key"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "AiDocMaker",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, headers=headers)
                latency = round((time.time() - t0) * 1000, 2)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return {
                        "success": True,
                        "configured": True,
                        "base_url": self.base_url,
                        "model": self.model,
                        "response_time_ms": latency,
                        "is_free_tier": data.get("is_free_tier", True),
                        "free_daily_requests_remaining": data.get("free_model_daily_requests", {}).get("remaining"),
                        "last_tested": utcnow().isoformat(),
                    }
                else:
                    return {
                        "success": False,
                        "configured": True,
                        "base_url": self.base_url,
                        "model": self.model,
                        "response_time_ms": latency,
                        "error": f"OpenRouter returned HTTP {resp.status_code}: {resp.text[:200]}",
                        "last_tested": utcnow().isoformat(),
                    }
        except Exception as exc:
            return {
                "success": False,
                "configured": True,
                "base_url": self.base_url,
                "model": self.model,
                "response_time_ms": round((time.time() - t0) * 1000, 2),
                "error": str(exc),
                "last_tested": utcnow().isoformat(),
            }

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not self.is_configured:
            raise ValueError(
                "OPENROUTER_API_KEY is not configured. Configure OPENROUTER_API_KEY in the API environment."
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "AiDocMaker",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        max_toks = max(request.max_output_tokens, 4096)
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_instructions},
                {
                    "role": "user",
                    "content": f"{request.prompt}\n\nCRITICAL: Return strictly valid JSON adhering to this schema:\n{json.dumps(request.output_schema)}",
                },
            ],
            "max_tokens": min(max_toks, 8192),
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=getattr(settings, "openrouter_timeout", 120)) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                raise ValueError(f"OpenRouter API error (HTTP {resp.status_code}): {resp.text}")
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenRouter API returned an empty choices array.")
        choice = choices[0]
        message = choice.get("message", {})
        raw_text = message.get("content")
        if not raw_text:
            raw_text = message.get("reasoning") or message.get("reasoning_content") or ""
        if not raw_text:
            raise ValueError(f"OpenRouter API returned empty message content. Finish reason: {choice.get('finish_reason')}")

        if choice.get("finish_reason") == "length" and not raw_text.rstrip().endswith("}"):
            raise ValueError("OpenRouter generation was truncated by upstream provider token limit.")

        parsed_content = self.extract_json(raw_text)

        return GenerationResponse(
            provider="openrouter",
            model_id=self.model,
            content=parsed_content,
            request_id=data.get("id"),
            usage=data.get("usage"),
        )

    def regenerate_section(
        self,
        section_id: str,
        section_title: str,
        template: dict,
        answers: dict,
        current_content: dict,
        user_guidance: Optional[str] = None,
    ) -> GeneratedSection:
        """Regenerate a single document section with OpenRouter."""
        if not self.is_configured:
            raise ValueError("OPENROUTER_API_KEY is not configured.")

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

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "AiDocMaker",
            "Content-Type": "application/json",
            "Accept": "application/json",
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
            "max_tokens": 2000,
            "temperature": 0.2,
        }

        with httpx.Client(timeout=getattr(settings, "openrouter_timeout", 120)) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise ValueError(f"OpenRouter API error (HTTP {resp.status_code}): {resp.text}")
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenRouter API returned empty choices for section regeneration.")

        msg = choices[0].get("message", {})
        raw_text = msg.get("content") or msg.get("reasoning") or msg.get("reasoning_content", "")
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
