from app.providers.offline_provider import OfflineProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.google_provider import GoogleProvider
from app.providers.nvidia_provider import NvidiaProvider
from app.providers.openrouter_provider import OpenRouterProvider

class ProviderRegistry:
    def __init__(self):
        self._providers = {
            "nvidia": NvidiaProvider(),
            "openrouter": OpenRouterProvider(),
            "offline": OfflineProvider(),
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "google": GoogleProvider(),
        }

    def get(self, name: str):
        if not name or name == "default":
            name = "nvidia"
        if name == "local":
            raise ValueError(
                "Local LLM architecture has been decommissioned. Please use 'nvidia' (NVIDIA NIM Hosted API) or 'offline' template mode."
            )
        if name not in self._providers:
            raise ValueError(f"Unsupported provider '{name}'. Primary provider is 'nvidia' (NVIDIA NIM).")
        return self._providers[name]

    def available(self):
        from app.core.config import settings
        return [
            {"id":"nvidia", "name":"NVIDIA NIM", "configured":bool(settings.nvidia_api_key), "model":settings.nvidia_model, "is_primary":True},
            {"id":"openrouter", "name":"OpenRouter", "configured":bool(settings.openrouter_api_key), "model":settings.openrouter_model},
            {"id":"offline", "name":"Offline template draft", "configured":True, "note":"Deterministic template-based output without external API."},
            {"id":"openai", "name":"OpenAI", "configured":bool(settings.openai_api_key), "model":settings.openai_model},
            {"id":"anthropic", "name":"Anthropic Claude", "configured":bool(settings.anthropic_api_key), "model":settings.anthropic_model},
            {"id":"google", "name":"Google Gemini", "configured":bool(settings.google_api_key), "model":settings.google_model},
        ]
