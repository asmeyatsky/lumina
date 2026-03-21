"""
Intelligence Engine REST API Routes

Architectural Intent:
- Thin HTTP adapter for the Intelligence Engine bounded context
- AVS calculation, trends, recommendations, and root cause analysis
- Routes delegate to application-layer commands and queries
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from lumina.shared.domain.value_objects import BrandId

from lumina.intelligence.domain.value_objects import AVSWeights

from lumina.presentation.api.schemas import (
    AVSResponse,
    AVSTrendPoint,
    AVSTrendsResponse,
    CalculateAVSRequest,
    RecommendationQueueResponse,
    RecommendationResponse,
    RootCauseAnalysisResponse,
    RootCauseResponse,
    RunRootCauseRequest,
    ScoreComponentResponse,
)

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


@router.post(
    "/brands/{brand_id}/avs",
    response_model=AVSResponse,
    status_code=201,
)
async def calculate_avs(
    brand_id: str,
    body: CalculateAVSRequest,
    request: Request,
) -> AVSResponse:
    """Calculate the AI Visibility Score for a brand."""
    container = request.app.state.container

    brand = BrandId(brand_id)

    calculate_cmd = container.calculate_avs_command()
    await calculate_cmd.execute(brand)

    avs_query = container.get_avs_query()
    avs = await avs_query.execute(brand)

    return AVSResponse(
        id=avs.id,
        brand_id=avs.brand_id,
        overall_score=avs.overall.value,
        components=[
            ScoreComponentResponse(
                module_name=c.module_name,
                score=c.score.value,
                weight=c.weight,
                weighted_score=c.weighted_score,
            )
            for c in avs.components
        ],
        delta=avs.calculate_delta(),
        previous_score=avs.previous_score.value if avs.previous_score else None,
        calculated_at=avs.calculated_at,
    )


@router.get("/brands/{brand_id}/avs", response_model=AVSResponse)
async def get_avs(
    brand_id: str,
    request: Request,
) -> AVSResponse:
    """Get the current AI Visibility Score for a brand."""
    container = request.app.state.container

    brand = BrandId(brand_id)
    avs_query = container.get_avs_query()
    avs = await avs_query.execute(brand)

    return AVSResponse(
        id=avs.id,
        brand_id=avs.brand_id,
        overall_score=avs.overall.value,
        components=[
            ScoreComponentResponse(
                module_name=c.module_name,
                score=c.score.value,
                weight=c.weight,
                weighted_score=c.weighted_score,
            )
            for c in avs.components
        ],
        delta=avs.calculate_delta(),
        previous_score=avs.previous_score.value if avs.previous_score else None,
        calculated_at=avs.calculated_at,
    )


@router.get("/brands/{brand_id}/avs/trends", response_model=AVSTrendsResponse)
async def get_avs_trends(
    brand_id: str,
    request: Request,
    period: str = "30d",
) -> AVSTrendsResponse:
    """Get AVS trend data over time for a brand."""
    container = request.app.state.container

    brand = BrandId(brand_id)
    trends_query = container.get_avs_trends_query()
    trend = await trends_query.execute(brand, period=period)

    return AVSTrendsResponse(
        brand_id=trend.brand_id,
        period=trend.period,
        trend_direction=trend.trend_direction,
        change_rate=trend.change_rate,
        data_points=[
            AVSTrendPoint(timestamp=ts, score=score)
            for ts, score in trend.scores
        ],
    )


@router.get(
    "/brands/{brand_id}/recommendations",
    response_model=RecommendationQueueResponse,
)
async def get_recommendations(
    brand_id: str,
    request: Request,
) -> RecommendationQueueResponse:
    """Get the prioritised recommendation queue for a brand."""
    container = request.app.state.container

    brand = BrandId(brand_id)
    rec_query = container.get_recommendation_queue_query()
    recs = await rec_query.execute(brand)

    return RecommendationQueueResponse(
        brand_id=brand_id,
        recommendations=[
            RecommendationResponse(
                id=r.id,
                source_module=r.source_module,
                action_description=r.action_description,
                expected_avs_impact=r.expected_avs_impact.value,
                effort_level=r.effort_level.value,
                priority_rank=r.priority_rank,
                linked_entity_id=r.linked_entity_id,
                created_at=r.created_at,
            )
            for r in recs
        ],
        total_count=len(recs),
    )


@router.post(
    "/brands/{brand_id}/root-cause",
    response_model=RootCauseAnalysisResponse,
    status_code=201,
)
async def run_root_cause_analysis(
    brand_id: str,
    body: RunRootCauseRequest,
    request: Request,
) -> RootCauseAnalysisResponse:
    """Run a root cause analysis on AVS changes for a brand."""
    container = request.app.state.container

    brand = BrandId(brand_id)
    rca_cmd = container.run_root_cause_analysis_command()
    rca = await rca_cmd.execute(
        brand_id=brand,
        current_scores=body.current_scores,
        previous_scores=body.previous_scores,
        external_signals=body.external_signals,
    )

    return RootCauseAnalysisResponse(
        id=rca.id,
        brand_id=rca.brand_id,
        trigger=rca.trigger,
        causes=[
            RootCauseResponse(
                factor=c.factor,
                module=c.module,
                evidence=c.evidence,
                contribution_weight=c.contribution_weight,
            )
            for c in rca.causes
        ],
        recommended_actions=list(rca.recommended_actions),
        analyzed_at=rca.analyzed_at,
    )
