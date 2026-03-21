"""
AI Engine Port — Interface for querying AI answer engines

Architectural Intent:
- Abstracts all AI engine communication behind a single protocol
- Infrastructure adapters implement this for Claude, GPT-4o, Gemini, Perplexity
- Domain and application layers never import SDK-specific code
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from lumina.shared.domain.value_objects import AIEngine


@dataclass(frozen=True)
class AIResponse:
    """Structured response from an AI answer engine."""

    engine: AIEngine
    prompt: str
    raw_response: str
    model_id: str
    latency_ms: int
    token_count: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


class AIEnginePort(Protocol):
    """Port for querying AI answer engines."""

    @property
    def engine(self) -> AIEngine: ...

    async def query(self, prompt: str) -> AIResponse:
        """Send a prompt to the AI engine and return the structured response."""
        ...

    async def query_batch(self, prompts: list[str]) -> list[AIResponse]:
        """Send multiple prompts concurrently with rate limiting."""
        ...

    async def health_check(self) -> bool:
        """Check if the AI engine is reachable."""
        ...
