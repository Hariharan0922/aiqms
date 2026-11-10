from typing import Any, Optional
import httpx
from app.core.config import settings
from app.services.ingestion.chunking_engine import DocumentChunk


class LocalAIAdapter:
    """Interface for future local embedding and LLM integration (Ollama / nomic-embed-text / qwen3).
    Ingestion operates 100% deterministically offline and does not require an active LLM.
    """

    SUPPORTED_EMBEDDING_MODELS = ["nomic-embed-text", "all-minilm", "bge-m3"]
    SUPPORTED_REASONING_MODELS = ["qwen3:4b", "qwen3:8b", "llama3.2:3b"]

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.local_model_base_url or "http://localhost:11434"

    def format_chunk_for_embedding(self, chunk: DocumentChunk) -> dict[str, Any]:
        """Format a clean document chunk for the embedding model (e.g. nomic-embed-text).

        Prefixing with search document prefix as recommended for nomic-embed-text.
        """
        # Preserves source traceability in metadata without allowing modifications to chunk_text
        doc_prefix = f"search_document: [{chunk.document_number or 'DOC'}] " if chunk.document_number else "search_document: "
        formatted_input = f"{doc_prefix}{chunk.chunk_text}"

        return {
            "model": "nomic-embed-text",
            "prompt": formatted_input,
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "document_number": chunk.document_number,
            "revision": chunk.document_revision,
            "section_title": chunk.section_title,
            "section_number": chunk.section_number,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "sequence": chunk.chunk_sequence,
            "char_count": chunk.character_count,
        }

    def check_ollama_status(self) -> dict[str, Any]:
        """Check if local Ollama daemon is reachable without hanging or throwing exceptions."""
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    return {
                        "accessible": True,
                        "base_url": self.base_url,
                        "available_models": models,
                        "has_embedding_model": any(any(e in m for e in self.SUPPORTED_EMBEDDING_MODELS) for m in models),
                    }
        except Exception:
            pass

        return {
            "accessible": False,
            "base_url": self.base_url,
            "available_models": [],
            "has_embedding_model": False,
            "mode": "deterministic_offline_rules",
        }

    def get_readiness_report(self) -> dict[str, Any]:
        """Return readiness configuration for Milestone 3+ AI integration."""
        ollama_status = self.check_ollama_status()
        return {
            "engine_mode": "rules_first_deterministic",
            "llm_mutation_blocked": True,  # Content must never be modified by AI
            "target_embedding_model": "nomic-embed-text",
            "target_reasoning_models": ["qwen3:4b", "qwen3:8b"],
            "ollama_status": ollama_status,
            "chunk_compatibility": {
                "format": "structure_aware_markdown",
                "max_tokens_compatible": 2048,
                "provenance_retained": True,
            },
        }
