"""
OpenAI GPT-4o Adapter — Infrastructure adapter implementing AIEnginePort

Architectural Intent:
- Translates the domain AIEnginePort protocol to OpenAI SDK calls
- Handles authentication, error mapping, and latency measurement
- Uses semaphore-based rate limiting for batch queries
"""

from __future__ import annotations

import asyncio
import time

import openai

from lumina.shared.domain.value_objects import AIEngine
from lumina.shared.ports.ai_engine import AIEnginePort, AIResponse


class OpenAIAdapter:
    """AIEnginePort adapter for OpenAI's GPT-4o API.

    Uses the openai SDK with async client for non-blocking I/O.
    Measures latency with time.perf_counter for high-resolution timing.
    """

    def __init__(
        self,
        api_key: str,
        model_id: str = "gpt-4o",
        max_tokens: int = 4096,
        max_concurrency: int = 5,
    ) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def engine(self) -> AIEngine:
        return AIEngine.GPT4O

    async def query(self, prompt: str) -> AIResponse:
        """Send a prompt to GPT-4o and return a structured AIResponse.

        Args:
            prompt: The prompt text to send.

        Returns:
            AIResponse with raw response text, latency, and metadata.

        Raises:
            openai.APIError: On API communication failure.
        """
        start = time.perf_counter()

        response = await self._client.chat.completions.create(
            model=self._model_id,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        choice = response.choices[0] if response.choices else None
        raw_text = choice.message.content or "" if choice else ""

        token_count = 0
        if response.usage:
            token_count = (
                (response.usage.prompt_tokens or 0)
                + (response.usage.completion_tokens or 0)
            )

        return AIResponse(
            engine=AIEngine.GPT4O,
            prompt=prompt,
            raw_response=raw_text,
            model_id=response.model or self._model_id,
            latency_ms=elapsed_ms,
            token_count=token_count,
            metadata={
                "finish_reason": choice.finish_reason or "" if choice else "",
                "response_id": response.id or "",
            },
        )

    async def query_batch(self, prompts: list[str]) -> list[AIResponse]:
        """Send multiple prompts concurrently with rate limiting.

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
        """Check if the OpenAI API is reachable."""
        try:
            await self._client.chat.completions.create(
                model=self._model_id,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
