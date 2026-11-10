import asyncio
import pytest
from unittest.mock import patch, MagicMock
from app.providers.openrouter_provider import OpenRouterProvider
from app.providers.base import GenerationRequest
from app.providers.registry import ProviderRegistry
from app.core.config import settings


@pytest.fixture
def sample_generation_request():
    return GenerationRequest(
        system_instructions="You are an ISO 13485 QMS assistant.",
        prompt="Draft an SOP for Document Control.",
        output_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "sections": {"type": "array"}
            },
            "required": ["title", "sections"]
        },
        max_output_tokens=2000
    )


def test_openrouter_provider_registered():
    registry = ProviderRegistry()
    assert "openrouter" in registry._providers
    openrouter = registry.get("openrouter")
    assert isinstance(openrouter, OpenRouterProvider)

    available = registry.available()
    or_meta = next((p for p in available if p["id"] == "openrouter"), None)
    assert or_meta is not None
    assert or_meta["name"] == "OpenRouter"
    assert "model" in or_meta


def test_openrouter_provider_raises_when_unconfigured(sample_generation_request):
    async def _test():
        provider = OpenRouterProvider(api_key="")
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY is not configured"):
            await provider.generate(sample_generation_request)

    asyncio.run(_test())


def test_openrouter_extract_json():
    # Direct JSON
    assert OpenRouterProvider.extract_json('{"status": "ok"}') == {"status": "ok"}

    # Markdown fence
    assert OpenRouterProvider.extract_json('```json\n{"status": "ok"}\n```') == {"status": "ok"}

    # Reasoning / Think tags
    assert OpenRouterProvider.extract_json('<think>Reasoning...</think>{"status": "ok"}') == {"status": "ok"}


def test_openrouter_connectivity_check():
    provider = OpenRouterProvider(api_key="")
    unconfigured_res = provider.test_connectivity()
    assert unconfigured_res["configured"] is False
    assert unconfigured_res["success"] is False

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "is_free_tier": True,
            "free_model_daily_requests": {"remaining": 42}
        }
    }
    with patch("httpx.Client.get", return_value=mock_resp):
        p2 = OpenRouterProvider(api_key="sk-or-v1-mock-test")
        res = p2.test_connectivity()
        assert res["success"] is True
        assert res["configured"] is True
        assert res["free_daily_requests_remaining"] == 42
