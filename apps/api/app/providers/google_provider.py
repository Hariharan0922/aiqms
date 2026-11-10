import json
import httpx
from app.providers.base import GenerationRequest, GenerationResponse
from app.core.config import settings

class GoogleProvider:
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is not configured. Configure it in the API environment first.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.google_model}:generateContent"
        body = {"systemInstruction": {"parts": [{"text": request.system_instructions}]},
                "contents": [{"role": "user", "parts": [{"text": request.prompt + "\n\nReturn only JSON matching this schema:\n" + json.dumps(request.output_schema)}]}],
                "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": request.max_output_tokens}}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, params={"key": settings.google_api_key}, json=body)
            response.raise_for_status()
            data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        usage = data.get("usageMetadata")
        return GenerationResponse(provider="google", model_id=settings.google_model, content=json.loads(text), usage=usage)
