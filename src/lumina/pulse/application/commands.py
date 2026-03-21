"""
PULSE Application Commands — Write-side use cases

Architectural Intent:
- Each command class encapsulates a single write-side use case
- Commands orchestrate domain logic and infrastructure via injected ports
- Commands are responsible for publishing domain events after persistence
- No domain logic lives here — only coordination
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import AIEngine, BrandId, Score
from lumina.shared.ports.ai_engine import AIEnginePort
from lumina.shared.ports.event_bus import EventBusPort

from lumina.pulse.domain.entities import (
    CitationResult,
    MonitoringRun,
    PromptBattery,
    PromptTemplate,
)
from lumina.pulse.domain.events import CitationDetected
from lumina.pulse.domain.ports import AlertPort, PulseRepositoryPort
from lumina.pulse.domain.services import (
    CitationExtractionService,
    SentimentAnalysisService,
)
from lumina.pulse.domain.value_objects import RunStatus, Sentiment
from lumina.pulse.application.orchestration import MultiEngineQueryOrchestrator


@dataclass(frozen=True)
class AlertThreshold:
    """Configuration for alert thresholds."""

    brand_id: str
    citation_drop_enabled: bool = True
    hallucination_detection_enabled: bool = True
    competitor_surge_threshold: float = 20.0


class RunMonitoringCommand:
    """Execute a full monitoring run for a brand.

    Orchestrates the end-to-end flow:
    1. Load the prompt battery
    2. Fan out queries to all AI engines in parallel
    3. Extract citations from each response
    4. Analyze sentiment
    5. Save the completed run
    6. Publish domain events
    """

    def __init__(
        self,
        repository: PulseRepositoryPort,
        event_bus: EventBusPort,
        engines: list[AIEnginePort],
        brand_name: str,
        competitors: tuple[str, ...] = (),
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._engines = engines
        self._brand_name = brand_name
        self._competitors = competitors
        self._extraction_service = CitationExtractionService()
        self._sentiment_service = SentimentAnalysisService()

    async def execute(self, battery_id: str) -> MonitoringRun:
        """Run monitoring for the given prompt battery.

        Args:
            battery_id: ID of the prompt battery to execute.

        Returns:
            The completed (or failed) MonitoringRun.

        Raises:
            EntityNotFoundError: If the battery does not exist.
        """
        from lumina.shared.domain.errors import EntityNotFoundError

        # 1. Load battery
        battery = await self._repository.get_battery(battery_id)
        if battery is None:
            raise EntityNotFoundError(f"PromptBattery {battery_id} not found")

        # 2. Create and persist a pending run
        run = MonitoringRun(
            id=str(uuid4()),
            brand_id=battery.brand_id,
            battery_id=battery.id,
            started_at=datetime.now(UTC),
            status=RunStatus.PENDING,
        )
        run = run.start()
        await self._repository.save_run(run)

        try:
            # 3. Fan out queries to all engines in parallel
            orchestrator = MultiEngineQueryOrchestrator(
                engines=self._engines,
                max_concurrency=10,
            )
            ai_responses = await orchestrator.execute(battery)

            # 4. Process each response: extract citations, analyze sentiment
            citation_results: list[CitationResult] = []
            citation_events: list[CitationDetected] = []

            for ai_response in ai_responses:
                # Extract citations
                citations = self._extraction_service.extract_citations(
                    raw_response=ai_response.raw_response,
                    brand_name=self._brand_name,
                    competitors=self._competitors,
                )

                # Determine overall sentiment from cited mentions
                cited = [
                    c for c in citations
                    if c.position.value < 5  # exclude NOT_CITED
                ]
                if cited:
                    sentiments = [
                        self._sentiment_service.analyze_sentiment(c.context)
                        for c in cited
                    ]
                    positive = sum(1 for s in sentiments if s == Sentiment.POSITIVE)
                    negative = sum(1 for s in sentiments if s == Sentiment.NEGATIVE)
                    if positive > negative:
                        overall_sentiment = Sentiment.POSITIVE
                    elif negative > positive:
                        overall_sentiment = Sentiment.NEGATIVE
                    else:
                        overall_sentiment = Sentiment.NEUTRAL
                else:
                    overall_sentiment = Sentiment.NEUTRAL

                # Build CitationResult
                result = CitationResult(
                    id=str(uuid4()),
                    run_id=run.id,
                    engine=ai_response.engine,
                    prompt_text=ai_response.prompt,
                    raw_response=ai_response.raw_response,
                    citations=citations,
                    sentiment=overall_sentiment,
                    accuracy_score=Score(value=50.0),  # baseline score
                    response_latency_ms=ai_response.latency_ms,
                )
                citation_results.append(result)

                # Collect citation-detected events for each actual citation
                for citation in cited:
                    if citation.brand_name.lower() == self._brand_name.lower():
                        citation_events.append(
                            CitationDetected(
                                aggregate_id=run.id,
                                brand_id=battery.brand_id.value,
                                engine=ai_response.engine.value,
                                prompt_text=ai_response.prompt,
                                position=citation.position.name,
                                sentiment=overall_sentiment.value,
                            )
                        )

            # 5. Complete the run
            run = run.complete(tuple(citation_results))

            # 6. Persist and publish events
            clean_run, run_events = run.collect_events()
            await self._repository.save_run(clean_run)

            all_events = list(run_events) + citation_events
            if all_events:
                await self._event_bus.publish(all_events)

            return clean_run

        except Exception as exc:
            # On any failure, mark the run as failed
            failed_run = run.fail(str(exc))
            clean_failed, fail_events = failed_run.collect_events()
            await self._repository.save_run(clean_failed)
            if fail_events:
                await self._event_bus.publish(list(fail_events))
            return clean_failed


class CreatePromptBatteryCommand:
    """Create a new prompt battery for a brand.

    Validates input, constructs the aggregate, and persists it.
    """

    def __init__(self, repository: PulseRepositoryPort) -> None:
        self._repository = repository

    async def execute(
        self,
        brand_id: str,
        name: str,
        prompts: list[dict[str, str | tuple[str, ...]]],
        vertical: str,
        schedule_cron: str,
    ) -> PromptBattery:
        """Create and persist a new PromptBattery.

        Args:
            brand_id: The brand this battery belongs to.
            name: Human-readable name for the battery.
            prompts: List of dicts with keys: text, category, intent_tags.
            vertical: Industry vertical (e.g., "fintech", "healthcare").
            schedule_cron: Cron expression for scheduled execution.

        Returns:
            The newly created PromptBattery.
        """
        prompt_templates = tuple(
            PromptTemplate(
                id=str(uuid4()),
                text=str(p["text"]),
                category=str(p["category"]),
                intent_tags=tuple(p.get("intent_tags", ())),
            )
            for p in prompts
        )

        battery = PromptBattery(
            id=str(uuid4()),
            brand_id=BrandId(value=brand_id),
            name=name,
            prompts=prompt_templates,
            vertical=vertical,
            schedule_cron=schedule_cron,
            is_active=True,
        )

        await self._repository.save_battery(battery)
        return battery


class ConfigureAlertCommand:
    """Set up alert thresholds for a brand.

    Stores the alert configuration so the monitoring pipeline can
    trigger alerts when thresholds are crossed.
    """

    def __init__(self, repository: PulseRepositoryPort) -> None:
        self._repository = repository

    async def execute(
        self,
        brand_id: str,
        citation_drop_enabled: bool = True,
        hallucination_detection_enabled: bool = True,
        competitor_surge_threshold: float = 20.0,
    ) -> AlertThreshold:
        """Configure alert thresholds for a brand.

        Args:
            brand_id: The brand to configure alerts for.
            citation_drop_enabled: Whether to alert on citation drops.
            hallucination_detection_enabled: Whether to alert on hallucinations.
            competitor_surge_threshold: Percentage increase that triggers surge alert.

        Returns:
            The configured AlertThreshold.
        """
        threshold = AlertThreshold(
            brand_id=brand_id,
            citation_drop_enabled=citation_drop_enabled,
            hallucination_detection_enabled=hallucination_detection_enabled,
            competitor_surge_threshold=competitor_surge_threshold,
        )
        return threshold
