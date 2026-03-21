"""
PULSE Module REST API Routes

Architectural Intent:
- Thin HTTP adapter translating REST calls to application-layer use cases
- All business logic resides in the PULSE bounded context
- Routes depend on the DI container for use case instances
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from fastapi import APIRouter, Request

from lumina.presentation.api.schemas import (
    CitationTrendPoint,
    CitationTrendsResponse,
    CreatePromptBatteryRequest,
    MonitoringRunResponse,
    PromptBatteryResponse,
    ShareOfVoiceEntry,
    ShareOfVoiceResponse,
    TriggerMonitoringRunRequest,
)

router = APIRouter(prefix="/api/v1/pulse", tags=["pulse"])


@router.post("/monitoring-runs", response_model=MonitoringRunResponse, status_code=201)
async def trigger_monitoring_run(
    body: TriggerMonitoringRunRequest,
    request: Request,
) -> MonitoringRunResponse:
    """Trigger a new PULSE monitoring run across configured AI engines."""
    container = request.app.state.container
    # Delegate to PULSE application layer when available
    run_id = str(uuid4())
    now = datetime.now(UTC)
    return MonitoringRunResponse(
        run_id=run_id,
        brand_id=body.brand_id,
        status="pending",
        engines=body.engines,
        created_at=now,
    )


@router.get("/monitoring-runs/{run_id}", response_model=MonitoringRunResponse)
async def get_monitoring_run(
    run_id: str,
    request: Request,
) -> MonitoringRunResponse:
    """Get the status and results of a monitoring run."""
    container = request.app.state.container
    from lumina.shared.domain.errors import EntityNotFoundError

    # Stub: delegate to PULSE query when wired
    raise EntityNotFoundError(f"Monitoring run {run_id} not found")


@router.post("/batteries", response_model=PromptBatteryResponse, status_code=201)
async def create_prompt_battery(
    body: CreatePromptBatteryRequest,
    request: Request,
) -> PromptBatteryResponse:
    """Create a new prompt battery for monitoring runs."""
    container = request.app.state.container
    battery_id = str(uuid4())
    now = datetime.now(UTC)
    return PromptBatteryResponse(
        battery_id=battery_id,
        brand_id=body.brand_id,
        name=body.name,
        prompts=body.prompts,
        category=body.category,
        created_at=now,
    )


@router.get("/brands/{brand_id}/trends", response_model=CitationTrendsResponse)
async def get_citation_trends(
    brand_id: str,
    request: Request,
    period: str = "30d",
) -> CitationTrendsResponse:
    """Get citation trend data for a brand across AI engines."""
    container = request.app.state.container
    return CitationTrendsResponse(
        brand_id=brand_id,
        period=period,
        data_points=[],
        trend_direction="stable",
        change_rate=0.0,
    )


@router.get("/brands/{brand_id}/share-of-voice", response_model=ShareOfVoiceResponse)
async def get_share_of_voice(
    brand_id: str,
    request: Request,
    category: str = "general",
) -> ShareOfVoiceResponse:
    """Get share of voice analysis for a brand."""
    container = request.app.state.container
    return ShareOfVoiceResponse(
        brand_id=brand_id,
        category=category,
        entries=[],
        calculated_at=datetime.now(UTC),
    )
