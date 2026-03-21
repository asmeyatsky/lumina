"""
Claude AI Engine Adapter — Infrastructure adapter implementing AIEnginePort

Architectural Intent:
- Translates the domain AIEnginePort protocol to Anthropic SDK calls
- Handles authentication, error mapping, and latency measurement
- Uses semaphore-based rate limiting for batch queries
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import anthropic

from lumina.shared.domain.value_objects import AIEngine
from lumina.shared.ports.ai_engine import AIEnginePort, AIResponse


class ClaudeAdapter:
    """AIEnginePort adapter for Anthropic's Claude API.

    Uses the anthropic SDK with async client for non-blocking I/O.
    Measures latency with time.perf_counter for high-resolution timing.
    """

    def __init__(
        self,
        api_key: str,
        model_id: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        max_concurrency: int = 5,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def engine(self) -> AIEngine:
        return AIEngine.CLAUDE

    async def query(self, prompt: str) -> AIResponse:
        """Send a prompt to Claude and return a structured AIResponse.

        Args:
            prompt: The prompt text to send.

        Returns:
            AIResponse with raw response text, latency, and metadata.

        Raises:
            anthropic.APIError: On API communication failure.
        """
        start = time.perf_counter()

        response = await self._client.messages.create(
            model=self._model_id,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        raw_text = ""
        for block in response.content:
            if block.type == "text":
                raw_text += block.text

        token_count = (response.usage.input_tokens + response.usage.output_tokens)

        return AIResponse(
            engine=AIEngine.CLAUDE,
            prompt=prompt,
            raw_response=raw_text,
            model_id=response.model,
            latency_ms=elapsed_ms,
            token_count=token_count,
            metadata={
                "stop_reason": response.stop_reason or "",
                "input_tokens": str(response.usage.input_tokens),
                "output_tokens": str(response.usage.output_tokens),
            },
        )

    async def query_batch(self, prompts: list[str]) -> list[AIResponse]:
        """Send multiple prompts concurrently with rate limiting.

        Uses a semaphore to bound concurrency and prevent API throttling.

        Args:
            prompts: List of prompt texts to send.

        Returns:
            List of AIResponse objects (one per prompt).
        """

        async def _rate_limited_query(prompt: str) -> AIResponse:
            async with self._semaphore:
                return await self.query(prompt)

        tasks = [
            asyncio.create_task(_rate_limited_query(p))
            for p in prompts
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses: list[AIResponse] = []
        for result in results:
            if isinstance(result, AIResponse):
                responses.append(result)
            elif isinstance(result, BaseException):
                raise result

        return responses

    async def health_check(self) -> bool:
        """Check if the Claude API is reachable.

        Sends a minimal prompt and returns True if a response is received.
        """
        try:
            await self._client.messages.create(
                model=self._model_id,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
