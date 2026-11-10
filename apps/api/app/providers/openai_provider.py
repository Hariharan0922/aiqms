import json
import httpx
from app.providers.base import GenerationRequest, GenerationResponse
from app.core.config import settings

class OpenAIProvider:
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured. Select Offline draft or configure a provider key in the API environment.")
        body = {
            "model": settings.openai_model,
            "instructions": request.system_instructions,
            "input": request.prompt + "\n\nOutput JSON schema:\n" + json.dumps(request.output_schema),
            "max_output_tokens": request.max_output_tokens,
            "text": {"format": {"type": "json_object"}},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}, json=body)
            response.raise_for_status()
            data = response.json()
        text = data.get("output_text")
        if not text:
            parts = []
            for item in data.get("output", []):
                for part in item.get("content", []):
                    if part.get("type") == "output_text": parts.append(part.get("text", ""))
            text = "".join(parts)
        return GenerationResponse(provider="openai", model_id=settings.openai_model, content=json.loads(text),
                                  request_id=data.get("id"), usage=data.get("usage"))
