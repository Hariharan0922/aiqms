import json
import httpx
from app.providers.base import GenerationRequest, GenerationResponse
from app.core.config import settings

class AnthropicProvider:
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured. Configure it in the API environment first.")
        body = {"model": settings.anthropic_model, "max_tokens": request.max_output_tokens,
                "system": request.system_instructions,
                "messages": [{"role": "user", "content": request.prompt + "\n\nReturn only JSON matching this schema:\n" + json.dumps(request.output_schema)}]}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=body)
            response.raise_for_status()
            data = response.json()
        text = "".join(item.get("text", "") for item in data.get("content", []) if item.get("type") == "text")
        return GenerationResponse(provider="anthropic", model_id=settings.anthropic_model, content=json.loads(text),
                                  request_id=data.get("id"), usage=data.get("usage"))
