"""
SIGNAL Domain Entities

Architectural Intent:
- All entities are frozen dataclasses (immutable aggregates)
- State transitions return new instances; originals are never mutated
- Domain events are collected on the aggregate root (DistributionPlan)
  and dispatched by the application layer after persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.events import DomainEvent
from lumina.shared.domain.value_objects import BrandId, Score, URL

from lumina.signal.domain.value_objects import (
    ActionStatus,
    ActionType,
    PresenceStatus,
    SurfaceCategory,
)
from lumina.signal.domain.events import (
    CoverageUpdated,
    DistributionPlanCreated,
    SignalDistributed,
)


@dataclass(frozen=True)
class CitationSurface:
    """A surface (website, platform, database) where LLMs draw training data."""

    id: str
    name: str
    category: SurfaceCategory
    url: URL
    estimated_llm_weight: Score
    brand_presence: PresenceStatus
    last_checked_at: datetime


@dataclass(frozen=True)
class DistributionAction:
    """A single action within a distribution plan targeting a surface."""

    id: str
    plan_id: str
    surface_id: str
    action_type: ActionType
    content: str
    status: ActionStatus
    scheduled_at: datetime
    completed_at: datetime | None = None
    result_url: str | None = None


@dataclass(frozen=True)
class DistributionPlan:
    """Aggregate root — a distribution plan for amplifying brand presence across surfaces."""

    id: str
    brand_id: BrandId
    target_surfaces: tuple[CitationSurface, ...] = ()
    actions: tuple[DistributionAction, ...] = ()
    coverage_score: Score = field(default_factory=lambda: Score(0.0))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    domain_events: tuple[DomainEvent, ...] = ()

    # ------------------------------------------------------------------
    # Aggregate behaviour — every mutation returns a new instance
    # ------------------------------------------------------------------

    def add_action(self, action: DistributionAction) -> DistributionPlan:
        """Return a new plan with the given action appended."""
        new_actions = self.actions + (action,)
        return DistributionPlan(
            id=self.id,
            brand_id=self.brand_id,
            target_surfaces=self.target_surfaces,
            actions=new_actions,
            coverage_score=self.coverage_score,
            created_at=self.created_at,
            domain_events=self.domain_events,
        )

    def mark_action_complete(
        self,
        action_id: str,
        result: str,
    ) -> DistributionPlan:
        """Return a new plan with the specified action marked completed and an event."""
        updated_actions: list[DistributionAction] = []
        events: list[DomainEvent] = list(self.domain_events)
        found = False

        for action in self.actions:
            if action.id == action_id:
                found = True
                completed_action = DistributionAction(
                    id=action.id,
                    plan_id=action.plan_id,
                    surface_id=action.surface_id,
                    action_type=action.action_type,
                    content=action.content,
                    status=ActionStatus.COMPLETED,
                    scheduled_at=action.scheduled_at,
                    completed_at=datetime.now(UTC),
                    result_url=result,
                )
                updated_actions.append(completed_action)
                events.append(
                    SignalDistributed(
                        aggregate_id=self.id,
                        brand_id=self.brand_id.value,
                        surface_id=action.surface_id,
                        action_type=action.action_type.value,
                        result_url=result,
                    )
                )
            else:
                updated_actions.append(action)

        if not found:
            raise ValueError(f"Action {action_id} not found on plan {self.id}")

        return DistributionPlan(
            id=self.id,
            brand_id=self.brand_id,
            target_surfaces=self.target_surfaces,
            actions=tuple(updated_actions),
            coverage_score=self.coverage_score,
            created_at=self.created_at,
            domain_events=tuple(events),
        )

    def calculate_coverage(self) -> DistributionPlan:
        """Return a new plan with coverage_score recalculated from completed actions.

        Coverage is measured as the percentage of target surfaces that have at least
        one completed action, mapped to a 0-100 score.  When coverage changes, a
        ``CoverageUpdated`` event is collected.
        """
        if not self.target_surfaces:
            new_score = Score(0.0)
        else:
            surfaces_with_completed = set()
            for action in self.actions:
                if action.status == ActionStatus.COMPLETED:
                    surfaces_with_completed.add(action.surface_id)

            covered_count = sum(
                1 for surface in self.target_surfaces
                if surface.id in surfaces_with_completed
            )
            raw = (covered_count / len(self.target_surfaces)) * 100.0
            new_score = Score(round(raw, 2))

        events = list(self.domain_events)
        if new_score.value != self.coverage_score.value:
            events.append(
                CoverageUpdated(
                    aggregate_id=self.id,
                    brand_id=self.brand_id.value,
                    old_coverage=self.coverage_score.value,
                    new_coverage=new_score.value,
                )
            )

        return DistributionPlan(
            id=self.id,
            brand_id=self.brand_id,
            target_surfaces=self.target_surfaces,
            actions=self.actions,
            coverage_score=new_score,
            created_at=self.created_at,
            domain_events=tuple(events),
        )

    def clear_events(self) -> DistributionPlan:
        """Return a copy with all collected domain events cleared."""
        return DistributionPlan(
            id=self.id,
            brand_id=self.brand_id,
            target_surfaces=self.target_surfaces,
            actions=self.actions,
            coverage_score=self.coverage_score,
            created_at=self.created_at,
            domain_events=(),
        )


@dataclass(frozen=True)
class PRBrief:
    """A press release brief constructed from entity data and narrative angles."""

    id: str
    brand_id: BrandId
    headline: str
    narrative_angle: str
    target_publications: tuple[str, ...]
    key_messages: tuple[str, ...]
    entity_anchors: tuple[str, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class CommunityPlaybook:
    """A playbook for community engagement on a specific platform."""

    id: str
    brand_id: BrandId
    platform: str
    recommended_topics: tuple[str, ...]
    engagement_strategy: str
    target_communities: tuple[str, ...]
