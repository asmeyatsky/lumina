"""
PULSE Domain Entities

Architectural Intent:
- All entities are frozen dataclasses (immutable domain models)
- State changes produce new instances (functional core)
- Domain events are collected on aggregate roots for dispatch after persistence
- MonitoringRun is the primary aggregate root
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, UTC
from typing import Optional
from uuid import uuid4

from lumina.shared.domain.events import DomainEvent
from lumina.shared.domain.value_objects import AIEngine, BrandId, Score, URL

from lumina.pulse.domain.value_objects import CitationPosition, RunStatus, Sentiment


@dataclass(frozen=True)
class Citation:
    """A single brand citation found within an AI engine response.

    Represents whether and how a brand was mentioned — its position,
    surrounding context, and whether the mention was a recommendation.
    """

    brand_name: str
    context: str
    position: CitationPosition
    is_recommendation: bool
    source_url: Optional[URL] = None

    def __post_init__(self) -> None:
        from lumina.pulse.domain.value_objects import CitationPosition as _CP

        if not self.brand_name or not self.brand_name.strip():
            raise ValueError("brand_name cannot be empty")
        if not self.context and self.position != _CP.NOT_CITED:
            raise ValueError("context cannot be empty")


@dataclass(frozen=True)
class PromptTemplate:
    """A reusable prompt template for querying AI engines.

    Each template targets a specific category and carries intent tags
    that describe the kind of information being sought.
    """

    id: str
    text: str
    category: str
    intent_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("PromptTemplate id cannot be empty")
        if not self.text or not self.text.strip():
            raise ValueError("PromptTemplate text cannot be empty")
        if not self.category or not self.category.strip():
            raise ValueError("PromptTemplate category cannot be empty")


@dataclass(frozen=True)
class CitationResult:
    """Result of querying a single AI engine with a single prompt.

    Captures the raw response, extracted citations, sentiment analysis,
    accuracy scoring, and response latency.
    """

    id: str
    run_id: str
    engine: AIEngine
    prompt_text: str
    raw_response: str
    citations: tuple[Citation, ...]
    sentiment: Sentiment
    accuracy_score: Score
    response_latency_ms: int

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("CitationResult id cannot be empty")
        if not self.run_id or not self.run_id.strip():
            raise ValueError("CitationResult run_id cannot be empty")
        if self.response_latency_ms < 0:
            raise ValueError("response_latency_ms must be non-negative")


@dataclass(frozen=True)
class PromptBattery:
    """A named collection of prompt templates for a brand.

    Batteries group related prompts that are executed together during
    monitoring runs. They can be scheduled via cron expression.
    """

    id: str
    brand_id: BrandId
    name: str
    prompts: tuple[PromptTemplate, ...]
    vertical: str
    schedule_cron: str
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("PromptBattery id cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("PromptBattery name cannot be empty")
        if not self.vertical or not self.vertical.strip():
            raise ValueError("PromptBattery vertical cannot be empty")


@dataclass(frozen=True)
class MonitoringRun:
    """Aggregate root for a single monitoring execution.

    Represents the lifecycle of running a prompt battery against AI engines,
    collecting citation results, and publishing domain events.
    Immutable — state transitions produce new instances.
    """

    id: str
    brand_id: BrandId
    battery_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: RunStatus = RunStatus.PENDING
    results: tuple[CitationResult, ...] = ()
    domain_events: tuple[DomainEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("MonitoringRun id cannot be empty")
        if not self.battery_id or not self.battery_id.strip():
            raise ValueError("MonitoringRun battery_id cannot be empty")

    def start(self) -> MonitoringRun:
        """Transition to RUNNING status. Returns a new instance."""
        return replace(
            self,
            status=RunStatus.RUNNING,
            domain_events=(),
        )

    def complete(self, results: tuple[CitationResult, ...]) -> MonitoringRun:
        """Transition to COMPLETED with citation results.

        Collects a MonitoringRunCompleted domain event on the new aggregate.
        Returns a new MonitoringRun instance — the original is unchanged.
        """
        from lumina.pulse.domain.events import MonitoringRunCompleted

        total_citations = sum(len(r.citations) for r in results)
        engines_queried = tuple({r.engine.value for r in results})

        event = MonitoringRunCompleted(
            aggregate_id=self.id,
            brand_id=self.brand_id.value,
            battery_id=self.battery_id,
            total_citations=total_citations,
            engines_queried=engines_queried,
        )

        return replace(
            self,
            completed_at=datetime.now(UTC),
            status=RunStatus.COMPLETED,
            results=results,
            domain_events=self.domain_events + (event,),
        )

    def fail(self, reason: str) -> MonitoringRun:
        """Transition to FAILED status with a failure reason event.

        Returns a new MonitoringRun instance — the original is unchanged.
        """
        from lumina.pulse.domain.events import MonitoringRunFailed

        event = MonitoringRunFailed(
            aggregate_id=self.id,
            brand_id=self.brand_id.value,
            battery_id=self.battery_id,
            reason=reason,
        )

        return replace(
            self,
            completed_at=datetime.now(UTC),
            status=RunStatus.FAILED,
            domain_events=self.domain_events + (event,),
        )

    def collect_events(self) -> tuple[MonitoringRun, tuple[DomainEvent, ...]]:
        """Return collected events and a clean aggregate with no pending events."""
        events = self.domain_events
        clean = replace(self, domain_events=())
        return clean, events
