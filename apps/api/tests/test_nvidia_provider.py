import asyncio
import pytest
from unittest.mock import patch
from app.providers.nvidia_provider import NvidiaProvider
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


def test_nvidia_provider_registered():
    registry = ProviderRegistry()
    assert "nvidia" in registry._providers
    nvidia = registry.get("nvidia")
    assert isinstance(nvidia, NvidiaProvider)

    available = registry.available()
    nvidia_meta = next((p for p in available if p["id"] == "nvidia"), None)
    assert nvidia_meta is not None
    assert nvidia_meta["name"] == "NVIDIA NIM"
    assert "model" in nvidia_meta


def test_nvidia_provider_raises_when_unconfigured(sample_generation_request):
    async def _test():
        provider = NvidiaProvider()
        with patch.object(settings, "nvidia_api_key", ""):
            with pytest.raises(ValueError, match="NVIDIA_API_KEY is not configured"):
                await provider.generate(sample_generation_request)

    asyncio.run(_test())


def test_nvidia_provider_mocked_success(sample_generation_request):
    async def _test():
        provider = NvidiaProvider()
        mock_payload = {
            "id": "chatcmpl-test-123",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '{"title": "Standard Operating Procedure", "sections": []}'
                    }
                }
            ],
            "usage": {"total_tokens": 150}
        }

        with patch.object(settings, "nvidia_api_key", "nvapi-test-key-mock"):
            with patch.object(provider, "_sync_call", return_value=mock_payload):
                resp = await provider.generate(sample_generation_request)

                assert resp.provider == "nvidia"
                assert resp.content == {"title": "Standard Operating Procedure", "sections": []}
                assert resp.request_id == "chatcmpl-test-123"
                assert resp.usage == {"total_tokens": 150}

    asyncio.run(_test())


def test_nvidia_provider_reasoning_fallback(sample_generation_request):
    """Test when content is empty and reasoning_content contains JSON."""
    async def _test():
        provider = NvidiaProvider()
        mock_payload = {
            "id": "chatcmpl-reasoning-456",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": 'Thinking...\n```json\n{"title": "Reasoned SOP", "sections": []}\n```'
                    }
                }
            ]
        }

        with patch.object(settings, "nvidia_api_key", "nvapi-test-key-mock"):
            with patch.object(provider, "_sync_call", return_value=mock_payload):
                resp = await provider.generate(sample_generation_request)

                assert resp.provider == "nvidia"
                assert resp.content == {"title": "Reasoned SOP", "sections": []}

    asyncio.run(_test())
