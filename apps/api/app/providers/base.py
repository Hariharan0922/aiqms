from dataclasses import dataclass
from typing import Any, Protocol

@dataclass
class GenerationRequest:
    system_instructions: str
    prompt: str
    output_schema: dict[str, Any]
    max_output_tokens: int = 8000

@dataclass
class GenerationResponse:
    provider: str
    model_id: str
    content: dict[str, Any]
    request_id: str | None = None
    usage: dict[str, Any] | None = None

class ModelProvider(Protocol):
    async def generate(self, request: GenerationRequest) -> GenerationResponse: ...
