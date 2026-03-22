"""
ORBIT Value Objects

Architectural Intent:
- Immutable, identity-less domain concepts specific to the ORBIT bounded context
- Enforce invariants at construction time
- Frozen dataclasses and enums only
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AutonomyLevel(str, Enum):
    """Controls how much human oversight the agent requires.

    SUPERVISED: Human must approve every action before execution.
    GUIDED: Human approves the plan; individual actions execute automatically.
    AUTONOMOUS: Agent operates freely within configured guardrails.
    """

    SUPERVISED = "supervised"
    GUIDED = "guided"
    AUTONOMOUS = "autonomous"

    @property
    def requires_plan_approval(self) -> bool:
        return self in (AutonomyLevel.SUPERVISED, AutonomyLevel.GUIDED)

    @property
    def requires_action_approval(self) -> bool:
        return self == AutonomyLevel.SUPERVISED


class SessionState(str, Enum):
    """Lifecycle state of an agent session."""

    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    FAILED = "failed"
    PAUSED = "paused"


class StepStatus(str, Enum):
    """Execution status of a single plan step."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionStatus(str, Enum):
    """Execution status of a single agent action (tool call)."""

    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class InsightSeverity(str, Enum):
    """Severity of an agent-generated insight."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def numeric(self) -> int:
        return {"info": 1, "warning": 2, "critical": 3}[self.value]


class CyclePhase(str, Enum):
    """Phase within a single observe-plan-act-synthesize cycle."""

    OBSERVE = "observe"
    PLAN = "plan"
    ACT = "act"
    SYNTHESIZE = "synthesize"


class ModuleTarget(str, Enum):
    """LUMINA modules that ORBIT can orchestrate."""

    PULSE = "pulse"
    GRAPH = "graph"
    BEAM = "beam"
    SIGNAL = "signal"
    INTELLIGENCE = "intelligence"
    AGENCY = "agency"


@dataclass(frozen=True)
class ToolDefinition:
    """Schema for a tool available to the agent from a LUMINA module."""

    module: ModuleTarget
    name: str
    description: str
    input_schema: tuple[tuple[str, str, str, bool], ...]  # (name, type, desc, required)

    @property
    def qualified_name(self) -> str:
        """Return module-prefixed tool name for disambiguation."""
        return f"{self.module.value}__{self.name}"


@dataclass(frozen=True)
class AgentContext:
    """Contextual information provided to the agent engine for planning.

    Captures the brand state, prior insights, and any user-supplied focus areas
    so the agent can make informed decisions about what to do next.
    """

    brand_id: str
    brand_name: str = ""
    current_avs: float | None = None
    previous_avs: float | None = None
    known_issues: tuple[str, ...] = ()
    focus_areas: tuple[str, ...] = ()
    max_actions_per_cycle: int = 10

    def __post_init__(self) -> None:
        if not self.brand_id or not self.brand_id.strip():
            raise ValueError("AgentContext.brand_id cannot be empty")
        if self.max_actions_per_cycle < 1:
            raise ValueError(
                f"max_actions_per_cycle must be >= 1, got {self.max_actions_per_cycle}"
            )
        if self.current_avs is not None and not (0.0 <= self.current_avs <= 100.0):
            raise ValueError(
                f"current_avs must be between 0 and 100, got {self.current_avs}"
            )


@dataclass(frozen=True)
class Guardrails:
    """Safety constraints that limit agent autonomy.

    Guardrails are enforced by the domain service before any action is executed.
    They prevent the agent from taking actions that could be harmful, excessive,
    or outside the scope of the session.
    """

    max_cycles: int = 5
    max_actions_per_cycle: int = 10
    max_total_actions: int = 30
    allowed_modules: tuple[ModuleTarget, ...] = (
        ModuleTarget.PULSE,
        ModuleTarget.GRAPH,
        ModuleTarget.BEAM,
        ModuleTarget.SIGNAL,
        ModuleTarget.INTELLIGENCE,
        ModuleTarget.AGENCY,
    )
    blocked_tools: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.max_cycles < 1:
            raise ValueError(f"max_cycles must be >= 1, got {self.max_cycles}")
        if self.max_actions_per_cycle < 1:
            raise ValueError(
                f"max_actions_per_cycle must be >= 1, got {self.max_actions_per_cycle}"
            )
        if self.max_total_actions < 1:
            raise ValueError(
                f"max_total_actions must be >= 1, got {self.max_total_actions}"
            )
