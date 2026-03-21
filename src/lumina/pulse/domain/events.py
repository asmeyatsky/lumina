"""
PULSE Domain Events

Architectural Intent:
- All events are frozen dataclasses extending the shared DomainEvent
- Events represent facts that have occurred within the PULSE bounded context
- Other bounded contexts (SIGNAL, BEAM) can subscribe to these events
- Events carry enough data for consumers to react without querying back
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class MonitoringRunCompleted(DomainEvent):
    """Emitted when a monitoring run finishes successfully.

    Consumers can use this to trigger trend recalculation,
    dashboard refresh, or downstream analytics.
    """

    brand_id: str = ""
    battery_id: str = ""
    total_citations: int = 0
    engines_queried: tuple[str, ...] = ()


@dataclass(frozen=True)
class MonitoringRunFailed(DomainEvent):
    """Emitted when a monitoring run fails.

    Used for alerting and retry orchestration.
    """

    brand_id: str = ""
    battery_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class CitationDetected(DomainEvent):
    """Emitted when a brand citation is found in an AI engine response.

    Each detection carries the engine, prompt context, position, and sentiment
    so downstream consumers can update metrics without re-querying.
    """

    brand_id: str = ""
    engine: str = ""
    prompt_text: str = ""
    position: str = ""
    sentiment: str = ""


@dataclass(frozen=True)
class CitationDropped(DomainEvent):
    """Emitted when a brand that was previously cited is no longer cited.

    This is a high-signal event — it may indicate a ranking regression
    and should trigger alerts.
    """

    brand_id: str = ""
    engine: str = ""
    prompt_text: str = ""
    previous_position: str = ""


@dataclass(frozen=True)
class CompetitorCitationSurge(DomainEvent):
    """Emitted when a competitor's citation rate surges significantly.

    Helps brands respond quickly to competitive shifts in AI visibility.
    """

    brand_id: str = ""
    competitor_id: str = ""
    engine: str = ""
    surge_percentage: float = 0.0


@dataclass(frozen=True)
class HallucinationDetected(DomainEvent):
    """Emitted when an AI engine makes a factually incorrect claim about a brand.

    Critical for brand safety — hallucinated claims can damage reputation
    and require immediate attention.
    """

    brand_id: str = ""
    engine: str = ""
    claim: str = ""
    prompt_text: str = ""
