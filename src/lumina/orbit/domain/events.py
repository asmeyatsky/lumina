"""
ORBIT Domain Events

Architectural Intent:
- Immutable event records capturing state transitions in the ORBIT bounded context
- Published after use-case completion for cross-context communication
- All extend the shared DomainEvent base class
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class SessionStarted(DomainEvent):
    """Emitted when a new autonomous agent session begins."""

    brand_id: str = ""
    goal: str = ""
    autonomy_level: str = ""


@dataclass(frozen=True)
class PlanCreated(DomainEvent):
    """Emitted when the agent generates an execution plan."""

    brand_id: str = ""
    step_count: int = 0
    rationale: str = ""


@dataclass(frozen=True)
class ActionExecuted(DomainEvent):
    """Emitted after the agent executes a tool call against a LUMINA module."""

    brand_id: str = ""
    module: str = ""
    tool_name: str = ""
    status: str = ""
    duration_ms: int = 0


@dataclass(frozen=True)
class CycleCompleted(DomainEvent):
    """Emitted when the agent completes a full observe-plan-act-synthesize cycle."""

    brand_id: str = ""
    cycle_number: int = 0
    actions_taken: int = 0
    insights_generated: int = 0


@dataclass(frozen=True)
class InsightGenerated(DomainEvent):
    """Emitted when the agent synthesizes a new insight from execution results."""

    brand_id: str = ""
    severity: str = ""
    finding: str = ""
    source_module: str = ""


@dataclass(frozen=True)
class GoalAchieved(DomainEvent):
    """Emitted when the agent determines the session goal has been met."""

    brand_id: str = ""
    goal: str = ""
    total_cycles: int = 0
    total_actions: int = 0


@dataclass(frozen=True)
class SessionFailed(DomainEvent):
    """Emitted when a session fails irrecoverably."""

    brand_id: str = ""
    reason: str = ""
    cycle_number: int = 0
