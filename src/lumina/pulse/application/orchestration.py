"""
PULSE Multi-Engine Query Orchestration — DAG-based parallel execution

Architectural Intent:
- Fans out all prompts to all engines concurrently (prompt x engine matrix)
- Uses asyncio.gather with return_exceptions=True for fault tolerance
- Respects rate limits via semaphore-based concurrency control
- Individual engine failures do not fail the entire orchestration
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from lumina.shared.ports.ai_engine import AIEnginePort, AIResponse

from lumina.pulse.domain.entities import PromptBattery

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrchestrationResult:
    """Result of a multi-engine query orchestration.

    Separates successful responses from errors for downstream processing.
    """

    responses: tuple[AIResponse, ...]
    errors: tuple[EngineError, ...]


@dataclass(frozen=True)
class EngineError:
    """Captures a failed engine query for error reporting."""

    engine_name: str
    prompt_text: str
    error_message: str


class MultiEngineQueryOrchestrator:
    """Orchestrates concurrent prompt execution across multiple AI engines.

    Creates a matrix of (prompt x engine) tasks and executes them all
    concurrently, bounded by a semaphore to respect rate limits.

    Example:
        3 prompts x 4 engines = 12 concurrent tasks (bounded by semaphore)
    """

    def __init__(
        self,
        engines: list[AIEnginePort],
        max_concurrency: int = 10,
    ) -> None:
        self._engines = engines
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute(self, battery: PromptBattery) -> list[AIResponse]:
        """Execute all prompts in the battery against all engines.

        Creates len(prompts) * len(engines) tasks, executes them
        concurrently with semaphore-based rate limiting, and returns
        all successful responses. Failed queries are logged but do not
        prevent other results from being returned.

        Args:
            battery: The prompt battery to execute.

        Returns:
            List of successful AIResponse objects.
        """
        result = await self.execute_with_errors(battery)
        return list(result.responses)

    async def execute_with_errors(
        self, battery: PromptBattery
    ) -> OrchestrationResult:
        """Execute all prompts and return both successes and errors.

        Args:
            battery: The prompt battery to execute.

        Returns:
            OrchestrationResult with separated responses and errors.
        """
        # Build the task matrix: every prompt paired with every engine
        tasks: list[asyncio.Task[AIResponse | EngineError]] = []

        for prompt_template in battery.prompts:
            for engine in self._engines:
                task = asyncio.create_task(
                    self._query_with_semaphore(engine, prompt_template.text),
                    name=f"{engine.engine.value}:{prompt_template.id}",
                )
                tasks.append(task)

        if not tasks:
            return OrchestrationResult(responses=(), errors=())

        # Execute all tasks concurrently, collecting exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successes from failures
        responses: list[AIResponse] = []
        errors: list[EngineError] = []

        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                # Determine which engine/prompt this was
                prompt_idx = i // len(self._engines)
                engine_idx = i % len(self._engines)
                prompt_text = (
                    battery.prompts[prompt_idx].text
                    if prompt_idx < len(battery.prompts)
                    else "unknown"
                )
                engine_name = (
                    self._engines[engine_idx].engine.value
                    if engine_idx < len(self._engines)
                    else "unknown"
                )

                logger.warning(
                    "Engine query failed: engine=%s prompt=%s error=%s",
                    engine_name,
                    prompt_text[:80],
                    str(result),
                )
                errors.append(
                    EngineError(
                        engine_name=engine_name,
                        prompt_text=prompt_text,
                        error_message=str(result),
                    )
                )
            elif isinstance(result, EngineError):
                errors.append(result)
            elif isinstance(result, AIResponse):
                responses.append(result)

        logger.info(
            "Orchestration complete: %d responses, %d errors",
            len(responses),
            len(errors),
        )

        return OrchestrationResult(
            responses=tuple(responses),
            errors=tuple(errors),
        )

    async def _query_with_semaphore(
        self, engine: AIEnginePort, prompt: str
    ) -> AIResponse:
        """Execute a single engine query with semaphore-based rate limiting.

        Args:
            engine: The AI engine adapter to query.
            prompt: The prompt text to send.

        Returns:
            AIResponse from the engine.

        Raises:
            Any exception from the engine query is propagated.
        """
        async with self._semaphore:
            return await engine.query(prompt)
