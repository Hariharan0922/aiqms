import asyncio
import json
import logging
from app.providers.base import GenerationRequest, GenerationResponse
from app.services.nvidia_service import NvidiaService
from app.core.config import settings

logger = logging.getLogger(__name__)


class NvidiaProvider:
    """NVIDIA NIM provider adapter routing through enterprise NvidiaService."""

    def __init__(self, service: NvidiaService | None = None):
        self.service = service or NvidiaService()

    def _sync_call(self, url: str, headers: dict, body: dict) -> dict:
        return self.service._sync_http_post("chat/completions", body)

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not settings.nvidia_api_key:
            raise ValueError(
                "NVIDIA_API_KEY is not configured. Configure NVIDIA_API_KEY in the API environment."
            )

        url = f"{settings.nvidia_base_url.rstrip('/')}/chat/completions"
        body = {
            "model": settings.nvidia_model,
            "messages": [
                {"role": "system", "content": request.system_instructions},
                {
                    "role": "user",
                    "content": f"{request.prompt}\n\nReturn strictly valid JSON matching this schema:\n{json.dumps(request.output_schema)}",
                },
            ],
            "max_tokens": min(request.max_output_tokens, 4096),
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {settings.nvidia_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AiDocMaker-NvidiaClient/1.0",
            "Accept": "application/json",
        }

        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self._sync_call, url, headers, body)

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("NVIDIA NIM API returned an empty choices array.")
        message = choices[0].get("message", {})
        raw_text = message.get("content") or message.get("reasoning_content", "")
        if not raw_text:
            raise ValueError("NVIDIA NIM API returned empty message content.")

        parsed_content = NvidiaService.extract_json(raw_text)

        return GenerationResponse(
            provider="nvidia",
            model_id=settings.nvidia_model,
            content=parsed_content,
            request_id=data.get("id"),
            usage=data.get("usage"),
        )
