"""
SIGNAL Module REST API Routes

Architectural Intent:
- Thin HTTP adapter for SIGNAL (distribution) bounded context
- Distribution plans, action execution, coverage, PR briefs, and surface mapping
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from fastapi import APIRouter, Request

from lumina.presentation.api.schemas import (
    CoverageSurface,
    CreateDistributionPlanRequest,
    DistributionCoverageResponse,
    DistributionPlanResponse,
    ExecuteActionRequest,
    ExecuteActionResponse,
    GeneratePRBriefRequest,
    MapSurfacesRequest,
    MapSurfacesResponse,
    PRBriefResponse,
)

router = APIRouter(prefix="/api/v1/signal", tags=["signal"])


@router.post("/plans", response_model=DistributionPlanResponse, status_code=201)
async def create_distribution_plan(
    body: CreateDistributionPlanRequest,
    request: Request,
) -> DistributionPlanResponse:
    """Create a new distribution plan for a brand."""
    container = request.app.state.container
    plan_id = str(uuid4())
    now = datetime.now(UTC)
    return DistributionPlanResponse(
        plan_id=plan_id,
        brand_id=body.brand_id,
        strategy=body.strategy,
        status="draft",
        actions=[],
        created_at=now,
        updated_at=now,
    )


@router.get("/plans/{plan_id}", response_model=DistributionPlanResponse)
async def get_plan(
    plan_id: str,
    request: Request,
) -> DistributionPlanResponse:
    """Get the status and actions of a distribution plan."""
    container = request.app.state.container
    from lumina.shared.domain.errors import EntityNotFoundError

    raise EntityNotFoundError(f"Distribution plan {plan_id} not found")


@router.post(
    "/plans/{plan_id}/actions/{action_id}/execute",
    response_model=ExecuteActionResponse,
    status_code=201,
)
async def execute_action(
    plan_id: str,
    action_id: str,
    body: ExecuteActionRequest,
    request: Request,
) -> ExecuteActionResponse:
    """Execute a specific action within a distribution plan."""
    container = request.app.state.container
    return ExecuteActionResponse(
        action_id=action_id,
        plan_id=plan_id,
        status="executed",
        result={"message": "Action execution initiated"},
        executed_at=datetime.now(UTC),
    )


@router.get("/brands/{brand_id}/coverage", response_model=DistributionCoverageResponse)
async def get_distribution_coverage(
    brand_id: str,
    request: Request,
) -> DistributionCoverageResponse:
    """Get distribution coverage metrics for a brand."""
    container = request.app.state.container
    return DistributionCoverageResponse(
        brand_id=brand_id,
        overall_coverage=0.0,
        surfaces=[],
        calculated_at=datetime.now(UTC),
    )


@router.post(
    "/brands/{brand_id}/pr-briefs",
    response_model=PRBriefResponse,
    status_code=201,
)
async def generate_pr_brief(
    brand_id: str,
    body: GeneratePRBriefRequest,
    request: Request,
) -> PRBriefResponse:
    """Generate a PR brief optimised for AI engine visibility."""
    container = request.app.state.container
    brief_id = str(uuid4())
    return PRBriefResponse(
        brief_id=brief_id,
        brand_id=brand_id,
        topic=body.topic,
        headline=f"PR Brief: {body.topic}",
        body="",
        target_publications=body.target_publications,
        generated_at=datetime.now(UTC),
    )


@router.post(
    "/brands/{brand_id}/map-surfaces",
    response_model=MapSurfacesResponse,
    status_code=201,
)
async def map_surfaces(
    brand_id: str,
    body: MapSurfacesRequest,
    request: Request,
) -> MapSurfacesResponse:
    """Map AI-crawled surfaces relevant to a brand."""
    container = request.app.state.container
    return MapSurfacesResponse(
        brand_id=brand_id,
        surfaces=[],
        total_surfaces=0,
        mapped_at=datetime.now(UTC),
    )
