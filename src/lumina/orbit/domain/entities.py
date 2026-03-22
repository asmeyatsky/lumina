"""
ORBIT Domain Entities

Architectural Intent:
- Frozen dataclasses enforce immutability (DDD aggregate invariant protection)
- Domain events are collected as tuples (immutable collections)
- All mutations produce new instances via dataclasses.replace()
- AgentSession is the aggregate root for the ORBIT bounded context
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.events import DomainEvent

from lumina.orbit.domain.value_objects import (
    ActionStatus,
    AgentContext,
    AutonomyLevel,
    CyclePhase,
    Guardrails,
    InsightSeverity,
    ModuleTarget,
    SessionState,
    StepStatus,
)
from lumina.orbit.domain.events import (
    ActionExecuted,
    CycleCompleted,
    GoalAchieved,
    InsightGenerated,
    PlanCreated,
    SessionFailed,
    SessionStarted,
)


# ---------------------------------------------------------------------------
# Supporting entities (not aggregate roots)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanStep:
    """A single step in the agent's execution plan.

    Each step maps to a tool call on a specific LUMINA module.
    Steps may declare dependencies on other steps to enforce ordering.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    module: ModuleTarget = ModuleTarget.INTELLIGENCE
    tool_name: str = ""
    description: str = ""
    arguments_json: str = "{}"
    depends_on: tuple[str, ...] = ()
    status: StepStatus = StepStatus.PENDING
    result_summary: str = ""

    def is_ready(self, completed_ids: frozenset[str]) -> bool:
        """Return True if all dependencies have completed."""
        return all(dep in completed_ids for dep in self.depends_on)

    def mark_completed(self, result_summary: str = "") -> PlanStep:
        return replace(self, status=StepStatus.COMPLETED, result_summary=result_summary)

    def mark_failed(self, reason: str = "") -> PlanStep:
        return replace(self, status=StepStatus.FAILED, result_summary=reason)


@dataclass(frozen=True)
class AgentPlan:
    """The agent's execution plan for achieving a goal.

    A DAG of PlanSteps with a rationale explaining the agent's reasoning.
    Plans can be revised mid-session if the agent determines a new approach.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    steps: tuple[PlanStep, ...] = ()
    rationale: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    revised_at: datetime | None = None

    @property
    def pending_steps(self) -> tuple[PlanStep, ...]:
        """Return steps that have not yet been executed."""
        return tuple(s for s in self.steps if s.status == StepStatus.PENDING)

    @property
    def completed_step_ids(self) -> frozenset[str]:
        """Return IDs of all completed steps."""
        return frozenset(s.id for s in self.steps if s.status == StepStatus.COMPLETED)

    @property
    def ready_steps(self) -> tuple[PlanStep, ...]:
        """Return steps whose dependencies are all met and are still pending."""
        completed = self.completed_step_ids
        return tuple(
            s for s in self.steps
            if s.status == StepStatus.PENDING and s.is_ready(completed)
        )

    @property
    def is_complete(self) -> bool:
        """True when no pending steps remain."""
        return len(self.pending_steps) == 0

    @property
    def progress_fraction(self) -> float:
        """Fraction of steps completed (0.0 to 1.0)."""
        if not self.steps:
            return 1.0
        done = sum(1 for s in self.steps if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED))
        return done / len(self.steps)

    def update_step(self, step_id: str, updated: PlanStep) -> AgentPlan:
        """Return a new plan with the specified step replaced."""
        new_steps = tuple(updated if s.id == step_id else s for s in self.steps)
        return replace(self, steps=new_steps)


@dataclass(frozen=True)
class AgentAction:
    """A single tool call executed by the agent.

    Records the module, tool, arguments, result, timing, and status
    of a concrete action the agent took.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    module: ModuleTarget = ModuleTarget.INTELLIGENCE
    tool_name: str = ""
    arguments_json: str = "{}"
    result_json: str = ""
    status: ActionStatus = ActionStatus.PENDING
    error_message: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: int = 0

    def mark_succeeded(
        self, result_json: str, completed_at: datetime, duration_ms: int
    ) -> AgentAction:
        return replace(
            self,
            status=ActionStatus.SUCCEEDED,
            result_json=result_json,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )

    def mark_failed(
        self, error_message: str, completed_at: datetime, duration_ms: int
    ) -> AgentAction:
        return replace(
            self,
            status=ActionStatus.FAILED,
            error_message=error_message,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )


@dataclass(frozen=True)
class AgentInsight:
    """A synthesized finding from the agent's analysis.

    Insights are generated during the synthesis phase of each cycle.
    They capture what the agent learned and what it recommends.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    severity: InsightSeverity = InsightSeverity.INFO
    confidence: float = 0.5
    finding: str = ""
    evidence: str = ""
    recommended_action: str = ""
    source_module: ModuleTarget = ModuleTarget.INTELLIGENCE
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be between 0 and 1, got {self.confidence}"
            )


@dataclass(frozen=True)
class ExecutionCycle:
    """A single observe-plan-act-synthesize iteration.

    The agent runs in cycles. Each cycle observes the current state,
    plans what to do, executes actions, and synthesizes findings.
    This is the atomic unit of autonomous work.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    cycle_number: int = 0
    phase: CyclePhase = CyclePhase.OBSERVE
    observations: tuple[str, ...] = ()
    actions: tuple[AgentAction, ...] = ()
    insights: tuple[AgentInsight, ...] = ()
    synthesis: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def succeeded_actions(self) -> tuple[AgentAction, ...]:
        return tuple(a for a in self.actions if a.status == ActionStatus.SUCCEEDED)

    @property
    def failed_actions(self) -> tuple[AgentAction, ...]:
        return tuple(a for a in self.actions if a.status == ActionStatus.FAILED)

    def add_action(self, action: AgentAction) -> ExecutionCycle:
        return replace(self, actions=self.actions + (action,))

    def add_insight(self, insight: AgentInsight) -> ExecutionCycle:
        return replace(self, insights=self.insights + (insight,))

    def complete(self, synthesis: str, insights: tuple[AgentInsight, ...]) -> ExecutionCycle:
        return replace(
            self,
            phase=CyclePhase.SYNTHESIZE,
            synthesis=synthesis,
            insights=insights,
            completed_at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentSession:
    """Aggregate root for the ORBIT bounded context.

    Represents a complete autonomous agent session. The agent receives a goal,
    plans how to achieve it using LUMINA's module tools, executes the plan
    in cycles, and synthesizes insights along the way.

    Invariants:
    - A session must have a non-empty goal.
    - Cycle count must not exceed guardrails.max_cycles.
    - Total actions must not exceed guardrails.max_total_actions.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    brand_id: str = ""
    goal: str = ""
    autonomy_level: AutonomyLevel = AutonomyLevel.GUIDED
    state: SessionState = SessionState.PLANNING
    context: AgentContext | None = None
    guardrails: Guardrails = field(default_factory=Guardrails)
    plan: AgentPlan | None = None
    cycles: tuple[ExecutionCycle, ...] = ()
    insights: tuple[AgentInsight, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    failure_reason: str = ""
    domain_events: tuple[DomainEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.goal or not self.goal.strip():
            raise ValueError("AgentSession.goal cannot be empty")

    # -- Derived properties --

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)

    @property
    def total_actions(self) -> int:
        return sum(c.action_count for c in self.cycles)

    @property
    def current_cycle(self) -> ExecutionCycle | None:
        if not self.cycles:
            return None
        last = self.cycles[-1]
        return last if last.completed_at is None else None

    @property
    def all_insights(self) -> tuple[AgentInsight, ...]:
        """All insights from all cycles plus session-level insights."""
        cycle_insights: list[AgentInsight] = []
        for cycle in self.cycles:
            cycle_insights.extend(cycle.insights)
        return tuple(cycle_insights) + self.insights

    @property
    def can_start_cycle(self) -> bool:
        """Check whether a new cycle is allowed under guardrails."""
        return (
            self.state in (SessionState.PLANNING, SessionState.EXECUTING)
            and self.cycle_count < self.guardrails.max_cycles
            and self.total_actions < self.guardrails.max_total_actions
        )

    @property
    def is_terminal(self) -> bool:
        return self.state in (SessionState.COMPLETE, SessionState.FAILED)

    # -- State transitions (produce new instances + domain events) --

    @staticmethod
    def start(
        brand_id: str,
        goal: str,
        autonomy_level: AutonomyLevel = AutonomyLevel.GUIDED,
        context: AgentContext | None = None,
        guardrails: Guardrails | None = None,
    ) -> AgentSession:
        """Factory: create and start a new session."""
        session_id = str(uuid4())
        effective_guardrails = guardrails or Guardrails()
        effective_context = context or AgentContext(brand_id=brand_id)

        event = SessionStarted(
            aggregate_id=session_id,
            brand_id=brand_id,
            goal=goal,
            autonomy_level=autonomy_level.value,
        )

        return AgentSession(
            id=session_id,
            brand_id=brand_id,
            goal=goal,
            autonomy_level=autonomy_level,
            state=SessionState.PLANNING,
            context=effective_context,
            guardrails=effective_guardrails,
            domain_events=(event,),
        )

    def set_plan(self, plan: AgentPlan) -> AgentSession:
        """Attach a plan to the session and transition state."""
        new_state = (
            SessionState.AWAITING_APPROVAL
            if self.autonomy_level.requires_plan_approval
            else SessionState.EXECUTING
        )

        event = PlanCreated(
            aggregate_id=self.id,
            brand_id=self.brand_id,
            step_count=len(plan.steps),
            rationale=plan.rationale,
        )

        return replace(
            self,
            plan=plan,
            state=new_state,
            domain_events=self.domain_events + (event,),
        )

    def approve_plan(self) -> AgentSession:
        """Human approves the plan; transition to executing."""
        if self.state != SessionState.AWAITING_APPROVAL:
            raise ValueError(
                f"Cannot approve plan in state {self.state.value}; "
                f"expected awaiting_approval"
            )
        return replace(self, state=SessionState.EXECUTING)

    def begin_cycle(self) -> AgentSession:
        """Start a new execution cycle."""
        if not self.can_start_cycle:
            raise ValueError(
                f"Cannot start new cycle: state={self.state.value}, "
                f"cycles={self.cycle_count}/{self.guardrails.max_cycles}, "
                f"actions={self.total_actions}/{self.guardrails.max_total_actions}"
            )
        cycle = ExecutionCycle(
            cycle_number=self.cycle_count + 1,
            phase=CyclePhase.OBSERVE,
        )
        return replace(
            self,
            state=SessionState.EXECUTING,
            cycles=self.cycles + (cycle,),
        )

    def record_action(self, action: AgentAction) -> AgentSession:
        """Record an executed action in the current cycle."""
        if not self.cycles:
            raise ValueError("No active cycle to record action in")

        current = self.cycles[-1]
        updated_cycle = current.add_action(action)

        event = ActionExecuted(
            aggregate_id=self.id,
            brand_id=self.brand_id,
            module=action.module.value,
            tool_name=action.tool_name,
            status=action.status.value,
            duration_ms=action.duration_ms,
        )

        return replace(
            self,
            cycles=self.cycles[:-1] + (updated_cycle,),
            domain_events=self.domain_events + (event,),
        )

    def complete_cycle(
        self, synthesis: str, insights: tuple[AgentInsight, ...]
    ) -> AgentSession:
        """Complete the current cycle with a synthesis and generated insights."""
        if not self.cycles:
            raise ValueError("No active cycle to complete")

        current = self.cycles[-1]
        completed_cycle = current.complete(synthesis, insights)

        events: list[DomainEvent] = []

        events.append(CycleCompleted(
            aggregate_id=self.id,
            brand_id=self.brand_id,
            cycle_number=completed_cycle.cycle_number,
            actions_taken=completed_cycle.action_count,
            insights_generated=len(insights),
        ))

        for insight in insights:
            events.append(InsightGenerated(
                aggregate_id=self.id,
                brand_id=self.brand_id,
                severity=insight.severity.value,
                finding=insight.finding,
                source_module=insight.source_module.value,
            ))

        return replace(
            self,
            cycles=self.cycles[:-1] + (completed_cycle,),
            insights=self.insights + insights,
            domain_events=self.domain_events + tuple(events),
        )

    def mark_complete(self) -> AgentSession:
        """Mark the session as successfully completed."""
        event = GoalAchieved(
            aggregate_id=self.id,
            brand_id=self.brand_id,
            goal=self.goal,
            total_cycles=self.cycle_count,
            total_actions=self.total_actions,
        )
        return replace(
            self,
            state=SessionState.COMPLETE,
            completed_at=datetime.now(UTC),
            domain_events=self.domain_events + (event,),
        )

    def mark_failed(self, reason: str) -> AgentSession:
        """Mark the session as failed."""
        event = SessionFailed(
            aggregate_id=self.id,
            brand_id=self.brand_id,
            reason=reason,
            cycle_number=self.cycle_count,
        )
        return replace(
            self,
            state=SessionState.FAILED,
            failure_reason=reason,
            completed_at=datetime.now(UTC),
            domain_events=self.domain_events + (event,),
        )

    def pause(self) -> AgentSession:
        """Pause the session for manual review."""
        return replace(self, state=SessionState.PAUSED)

    def resume(self) -> AgentSession:
        """Resume a paused session."""
        if self.state != SessionState.PAUSED:
            raise ValueError(f"Cannot resume from state {self.state.value}")
        return replace(self, state=SessionState.EXECUTING)
