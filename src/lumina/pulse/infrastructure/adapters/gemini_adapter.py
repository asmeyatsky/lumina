"""
Google Gemini Adapter — Infrastructure adapter implementing AIEnginePort

Architectural Intent:
- Translates the domain AIEnginePort protocol to Google GenAI SDK calls
- Handles authentication, error mapping, and latency measurement
- Uses semaphore-based rate limiting for batch queries
"""

from __future__ import annotations

import asyncio
import time

from google import genai
from google.genai import types

from lumina.shared.domain.value_objects import AIEngine
from lumina.shared.ports.ai_engine import AIEnginePort, AIResponse


class GeminiAdapter:
    """AIEnginePort adapter for Google's Gemini API.

    Uses the google-genai SDK with async client for non-blocking I/O.
    Measures latency with time.perf_counter for high-resolution timing.
    """

    def __init__(
        self,
        api_key: str,
        model_id: str = "gemini-2.0-flash",
        max_concurrency: int = 5,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model_id = model_id
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def engine(self) -> AIEngine:
        return AIEngine.GEMINI

    async def query(self, prompt: str) -> AIResponse:
        """Send a prompt to Gemini and return a structured AIResponse.

        Args:
            prompt: The prompt text to send.

        Returns:
            AIResponse with raw response text, latency, and metadata.

        Raises:
            google.genai errors on API communication failure.
        """
        start = time.perf_counter()

        response = await self._client.aio.models.generate_content(
            model=self._model_id,
            contents=prompt,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        raw_text = response.text or ""

        token_count = 0
        if response.usage_metadata:
            token_count = (
                (response.usage_metadata.prompt_token_count or 0)
                + (response.usage_metadata.candidates_token_count or 0)
            )

        return AIResponse(
            engine=AIEngine.GEMINI,
            prompt=prompt,
            raw_response=raw_text,
            model_id=self._model_id,
            latency_ms=elapsed_ms,
            token_count=token_count,
            metadata={},
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
        """Check if the Gemini API is reachable."""
        try:
            await self._client.aio.models.generate_content(
                model=self._model_id,
                contents="ping",
            )
            return True
        except Exception:
            return False
