from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AiDocMaker - Intelligent Document Automation"
    environment: str = "development"
    database_url: str = "sqlite:///./aiqms.db"
    cors_origins: str = "http://localhost:5173"
    dev_auth_enabled: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-5.6"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    google_api_key: str = ""
    google_model: str = "gemini-2.5-pro"
    nvidia_api_key: str = ""
    nvidia_model: str = "poolside/laguna-xs-2.1"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_timeout: int = 120
    nvidia_max_retries: int = 2
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    openrouter_timeout: int = 120
    local_model_base_url: str = ""
    local_model_name: str = ""
    max_upload_mb: int = 20
    aiqms_storage_dir: str = "./data"

    model_config = SettingsConfigDict(env_file=(".env", "apps/api/.env"), env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
