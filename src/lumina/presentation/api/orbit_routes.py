"""
ORBIT REST API Routes

Architectural Intent:
- Thin HTTP adapter for the ORBIT bounded context
- Delegates to application commands and queries
- Pydantic schemas for request/response serialisation only
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from lumina.orbit.domain.value_objects import AutonomyLevel


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class StartSessionRequest(BaseModel):
    brand_id: str
    goal: str
    autonomy_level: str = "guided"
    brand_name: str = ""
    focus_areas: list[str] = Field(default_factory=list)
    max_cycles: int = 5


class PlanSummary(BaseModel):
    rationale: str
    step_count: int
    progress: float


class SessionResponse(BaseModel):
    session_id: str
    brand_id: str
    goal: str
    state: str
    autonomy_level: str
    cycle_count: int
    total_actions: int
    insight_count: int
    created_at: datetime
    completed_at: datetime | None = None
    failure_reason: str = ""
    plan: PlanSummary | None = None


class InsightResponse(BaseModel):
    severity: str
    confidence: float
    finding: str
    evidence: str
    recommended_action: str
    source_module: str


class SessionMetricsResponse(BaseModel):
    session_id: str
    brand_id: str
    state: str
    cycle_count: int
    total_actions: int
    modules_touched: list[str]
    insight_count: int
    critical_insights: int
    average_cycle_success_rate: float


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/orbit", tags=["orbit"])


def _session_to_response(session) -> SessionResponse:
    """Convert domain session to response schema."""
    plan = None
    if session.plan:
        plan = PlanSummary(
            rationale=session.plan.rationale,
            step_count=len(session.plan.steps),
            progress=round(session.plan.progress_fraction, 2),
        )
    return SessionResponse(
        session_id=session.id,
        brand_id=session.brand_id,
        goal=session.goal,
        state=session.state.value,
        autonomy_level=session.autonomy_level.value,
        cycle_count=session.cycle_count,
        total_actions=session.total_actions,
        insight_count=len(session.all_insights),
        created_at=session.created_at,
        completed_at=session.completed_at,
        failure_reason=session.failure_reason,
        plan=plan,
    )


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def start_session(body: StartSessionRequest, request: Request) -> SessionResponse:
    """Start a new autonomous ORBIT session."""
    container = request.app.state.container

    command = container.start_session_command()
    session = await command.execute(
        brand_id=body.brand_id,
        goal=body.goal,
        autonomy_level=AutonomyLevel(body.autonomy_level),
    )
    return _session_to_response(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request) -> SessionResponse:
    """Get session state."""
    container = request.app.state.container
    query = container.get_session_query()
    session = await query.execute(session_id)
    return _session_to_response(session)


@router.post("/sessions/{session_id}/cycle", response_model=SessionResponse)
async def run_cycle(session_id: str, request: Request) -> SessionResponse:
    """Execute one observe-plan-act-synthesize cycle."""
    container = request.app.state.container
    command = container.run_cycle_command()
    session = await command.execute(session_id)
    return _session_to_response(session)


@router.post("/sessions/{session_id}/run", response_model=SessionResponse)
async def run_full_session(session_id: str, request: Request) -> SessionResponse:
    """Run the full autonomous loop to completion."""
    container = request.app.state.container
    command = container.run_full_session_command()
    session = await command.execute(session_id)
    return _session_to_response(session)


@router.post("/sessions/{session_id}/approve", response_model=SessionResponse)
async def approve_plan(session_id: str, request: Request) -> SessionResponse:
    """Approve the agent's plan."""
    container = request.app.state.container
    command = container.approve_plan_command()
    session = await command.execute(session_id)
    return _session_to_response(session)


@router.post("/sessions/{session_id}/pause", response_model=SessionResponse)
async def pause_session(session_id: str, request: Request) -> SessionResponse:
    """Pause an active session."""
    container = request.app.state.container
    command = container.pause_session_command()
    session = await command.execute(session_id)
    return _session_to_response(session)


@router.post("/sessions/{session_id}/resume", response_model=SessionResponse)
async def resume_session(session_id: str, request: Request) -> SessionResponse:
    """Resume a paused session."""
    container = request.app.state.container
    command = container.resume_session_command()
    session = await command.execute(session_id)
    return _session_to_response(session)


@router.get(
    "/sessions/{session_id}/insights",
    response_model=list[InsightResponse],
)
async def get_insights(session_id: str, request: Request) -> list[InsightResponse]:
    """Get ranked insights from a session."""
    container = request.app.state.container
    query = container.get_insights_query()
    insights = await query.execute(session_id)
    return [
        InsightResponse(
            severity=i.severity.value,
            confidence=i.confidence,
            finding=i.finding,
            evidence=i.evidence,
            recommended_action=i.recommended_action,
            source_module=i.source_module.value,
        )
        for i in insights
    ]


@router.get(
    "/sessions/{session_id}/metrics",
    response_model=SessionMetricsResponse,
)
async def get_metrics(session_id: str, request: Request) -> SessionMetricsResponse:
    """Get aggregate metrics for a session."""
    container = request.app.state.container
    query = container.get_session_metrics_query()
    metrics = await query.execute(session_id)
    return SessionMetricsResponse(**metrics)


@router.get("/brands/{brand_id}/active", response_model=SessionResponse | None)
async def get_active_session(
    brand_id: str, request: Request
) -> SessionResponse | None:
    """Get the currently active session for a brand."""
    container = request.app.state.container
    query = container.get_active_session_query()
    session = await query.execute(brand_id)
    if session is None:
        return None
    return _session_to_response(session)


@router.get("/brands/{brand_id}/history", response_model=list[SessionResponse])
async def get_session_history(
    brand_id: str, request: Request, limit: int = 20
) -> list[SessionResponse]:
    """Get session history for a brand."""
    container = request.app.state.container
    query = container.get_session_history_query()
    sessions = await query.execute(brand_id, limit=limit)
    return [_session_to_response(s) for s in sessions]
