"""
SIGNAL Domain Events

Architectural Intent:
- Capture every meaningful state change in the Distribution & Amplification context
- Events are immutable records published after aggregate persistence
- Other bounded contexts (PULSE, GRAPH) subscribe to these events to react
  to distribution progress and coverage changes
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class DistributionPlanCreated(DomainEvent):
    """Raised when a new distribution plan is created for a brand."""

    brand_id: str = ""
    total_actions: int = 0
    target_surface_count: int = 0


@dataclass(frozen=True)
class SignalDistributed(DomainEvent):
    """Raised when a distribution action is successfully executed on a surface."""

    brand_id: str = ""
    surface_id: str = ""
    action_type: str = ""
    result_url: str = ""


@dataclass(frozen=True)
class CoverageUpdated(DomainEvent):
    """Raised when a brand's overall distribution coverage changes."""

    brand_id: str = ""
    old_coverage: float = 0.0
    new_coverage: float = 0.0


@dataclass(frozen=True)
class PRBriefGenerated(DomainEvent):
    """Raised when a PR brief is generated for a brand."""

    brand_id: str = ""
    headline: str = ""
    target_publication_count: int = 0


@dataclass(frozen=True)
class SurfaceGapIdentified(DomainEvent):
    """Raised when analysis identifies a surface where the brand is absent."""

    brand_id: str = ""
    surface_name: str = ""
    category: str = ""
    estimated_impact: float = 0.0
