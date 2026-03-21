"""
Perplexity Adapter — Infrastructure adapter implementing AIEnginePort

Architectural Intent:
- Translates the domain AIEnginePort protocol to Perplexity's OpenAI-compatible API
- Uses httpx for async HTTP calls (no Perplexity-specific SDK needed)
- Handles authentication, error mapping, and latency measurement
- Uses semaphore-based rate limiting for batch queries
"""

from __future__ import annotations

import asyncio
import time

import httpx

from lumina.shared.domain.value_objects import AIEngine
from lumina.shared.ports.ai_engine import AIEnginePort, AIResponse


_PERPLEXITY_BASE_URL = "https://api.perplexity.ai"


class PerplexityAdapter:
    """AIEnginePort adapter for Perplexity's API.

    Perplexity exposes an OpenAI-compatible chat completions endpoint.
    This adapter uses httpx directly rather than the openai SDK to
    keep infrastructure dependencies minimal and explicit.
    """

    def __init__(
        self,
        api_key: str,
        model_id: str = "sonar-pro",
        max_tokens: int = 4096,
        max_concurrency: int = 5,
        base_url: str = _PERPLEXITY_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

    @property
    def engine(self) -> AIEngine:
        return AIEngine.PERPLEXITY

    async def query(self, prompt: str) -> AIResponse:
        """Send a prompt to Perplexity and return a structured AIResponse.

        Uses the OpenAI-compatible /chat/completions endpoint.

        Args:
            prompt: The prompt text to send.

        Returns:
            AIResponse with raw response text, latency, and metadata.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            httpx.RequestError: On network failure.
        """
        start = time.perf_counter()

        payload = {
            "model": self._model_id,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        data = response.json()

        # Extract response text from OpenAI-compatible format
        choices = data.get("choices", [])
        raw_text = ""
        finish_reason = ""
        if choices:
            message = choices[0].get("message", {})
            raw_text = message.get("content", "")
            finish_reason = choices[0].get("finish_reason", "")

        # Extract token usage
        usage = data.get("usage", {})
        token_count = (
            usage.get("prompt_tokens", 0)
            + usage.get("completion_tokens", 0)
        )

        # Extract citations if Perplexity provides them
        citations = data.get("citations", [])

        return AIResponse(
            engine=AIEngine.PERPLEXITY,
            prompt=prompt,
            raw_response=raw_text,
            model_id=data.get("model", self._model_id),
            latency_ms=elapsed_ms,
            token_count=token_count,
            metadata={
                "finish_reason": finish_reason,
                "response_id": data.get("id", ""),
                "citations": ",".join(citations) if citations else "",
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
        """Check if the Perplexity API is reachable."""
        try:
            payload = {
                "model": self._model_id,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "ping"}],
            }
            response = await self._client.post("/chat/completions", json=payload)
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
