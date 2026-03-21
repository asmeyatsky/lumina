"""
Pydantic Request/Response Schemas for all LUMINA API endpoints.

Architectural Intent:
- Strict separation between API schemas and domain entities
- Pydantic v2 models with explicit validation
- Grouped by module for clarity
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# Common
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str
    error_type: str = "error"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"
    service: str = "lumina"


# =============================================================================
# PULSE Schemas
# =============================================================================


class TriggerMonitoringRunRequest(BaseModel):
    """Request to trigger a new PULSE monitoring run."""

    brand_id: str = Field(..., description="Brand to monitor")
    engines: list[str] = Field(
        default_factory=lambda: ["claude", "gpt-4o", "gemini", "perplexity"],
        description="AI engines to query",
    )
    prompt_battery_id: str | None = Field(None, description="Optional prompt battery ID")


class MonitoringRunResponse(BaseModel):
    """Response for a PULSE monitoring run."""

    run_id: str
    brand_id: str
    status: str
    engines: list[str]
    created_at: datetime
    completed_at: datetime | None = None
    results_count: int = 0


class CreatePromptBatteryRequest(BaseModel):
    """Request to create a new prompt battery."""

    brand_id: str
    name: str
    prompts: list[str]
    category: str = "general"


class PromptBatteryResponse(BaseModel):
    """Response for a prompt battery."""

    battery_id: str
    brand_id: str
    name: str
    prompts: list[str]
    category: str
    created_at: datetime


class CitationTrendPoint(BaseModel):
    """A single data point in a citation trend."""

    timestamp: datetime
    citation_rate: float
    engine: str


class CitationTrendsResponse(BaseModel):
    """Response for citation trends."""

    brand_id: str
    period: str
    data_points: list[CitationTrendPoint]
    trend_direction: str
    change_rate: float


class ShareOfVoiceEntry(BaseModel):
    """Share of voice for a single competitor."""

    entity: str
    share: float
    citation_count: int


class ShareOfVoiceResponse(BaseModel):
    """Response for share of voice analysis."""

    brand_id: str
    category: str
    entries: list[ShareOfVoiceEntry]
    calculated_at: datetime


# =============================================================================
# GRAPH Schemas
# =============================================================================


class CreateEntityProfileRequest(BaseModel):
    """Request to create a new entity profile."""

    brand_id: str
    entity_name: str
    entity_type: str = "organization"
    description: str = ""
    dimensions: list[DimensionInput] | None = None


class DimensionInput(BaseModel):
    """Input for a knowledge graph dimension."""

    name: str
    value: str
    source: str = ""
    confidence: float = 1.0


class DimensionResponse(BaseModel):
    """Response for a knowledge graph dimension."""

    dimension_id: str
    name: str
    value: str
    source: str
    confidence: float
    updated_at: datetime


class EntityProfileResponse(BaseModel):
    """Response for an entity profile."""

    brand_id: str
    entity_name: str
    entity_type: str
    description: str
    dimensions: list[DimensionResponse]
    completeness_score: float
    created_at: datetime
    updated_at: datetime


class UpdateDimensionRequest(BaseModel):
    """Request to update a specific dimension."""

    value: str
    source: str = ""
    confidence: float = 1.0


class RunGapAnalysisRequest(BaseModel):
    """Request to run a knowledge gap analysis."""

    target_engines: list[str] = Field(
        default_factory=lambda: ["claude", "gpt-4o", "gemini", "perplexity"]
    )
    depth: str = "standard"


class KnowledgeGapResponse(BaseModel):
    """Response for a single knowledge gap."""

    gap_id: str
    dimension: str
    severity: float
    description: str
    suggested_action: str
    engine: str


class GapAnalysisResponse(BaseModel):
    """Response for gap analysis results."""

    brand_id: str
    gaps: list[KnowledgeGapResponse]
    total_gaps: int
    analysis_completed_at: datetime


class GenerateJsonLdRequest(BaseModel):
    """Request to generate JSON-LD markup."""

    schema_type: str = "Organization"
    include_dimensions: list[str] | None = None


class JsonLdResponse(BaseModel):
    """Response containing generated JSON-LD."""

    brand_id: str
    schema_type: str
    json_ld: dict
    generated_at: datetime


# Allow forward reference resolution
CreateEntityProfileRequest.model_rebuild()


# =============================================================================
# BEAM Schemas
# =============================================================================


class ScoreContentRequest(BaseModel):
    """Request to score content by URL."""

    url: str
    brand_id: str
    content_type: str = "webpage"


class ContentScoreResponse(BaseModel):
    """Response for content scoring."""

    asset_id: str
    url: str
    brand_id: str
    overall_score: float
    dimensions: dict[str, float]
    ai_readability: float
    chunking_quality: float
    factual_density: float
    scored_at: datetime


class BulkAuditRequest(BaseModel):
    """Request to audit multiple URLs."""

    brand_id: str
    urls: list[str]
    content_type: str = "webpage"


class BulkAuditResponse(BaseModel):
    """Response for bulk audit."""

    audit_id: str
    brand_id: str
    total_urls: int
    status: str
    results: list[ContentScoreResponse]
    started_at: datetime
    completed_at: datetime | None = None


class RAGSimulationRequest(BaseModel):
    """Request to run a RAG retrieval simulation."""

    query: str
    target_engines: list[str] = Field(
        default_factory=lambda: ["claude", "gpt-4o"]
    )


class RAGSimulationResponse(BaseModel):
    """Response for RAG simulation."""

    asset_id: str
    query: str
    retrieval_probability: float
    chunk_rankings: list[dict[str, object]]
    simulation_completed_at: datetime


class RewriteSuggestion(BaseModel):
    """A single rewrite suggestion."""

    section: str
    original_text: str
    suggested_text: str
    improvement_reason: str
    expected_score_impact: float


class RewriteSuggestionsRequest(BaseModel):
    """Request to generate rewrite suggestions."""

    target_score: float = 80.0
    focus_areas: list[str] | None = None


class RewriteSuggestionsResponse(BaseModel):
    """Response for rewrite suggestions."""

    asset_id: str
    suggestions: list[RewriteSuggestion]
    current_score: float
    projected_score: float
    generated_at: datetime


class AuditSummaryResponse(BaseModel):
    """Response for brand-level audit summary."""

    brand_id: str
    total_assets: int
    average_score: float
    score_distribution: dict[str, int]
    top_issues: list[str]
    summary_generated_at: datetime


# =============================================================================
# SIGNAL Schemas
# =============================================================================


class CreateDistributionPlanRequest(BaseModel):
    """Request to create a distribution plan."""

    brand_id: str
    target_surfaces: list[str] = Field(default_factory=list)
    strategy: str = "balanced"
    priority: str = "medium"


class DistributionAction(BaseModel):
    """A single action in a distribution plan."""

    action_id: str
    surface: str
    action_type: str
    status: str
    description: str


class DistributionPlanResponse(BaseModel):
    """Response for a distribution plan."""

    plan_id: str
    brand_id: str
    strategy: str
    status: str
    actions: list[DistributionAction]
    created_at: datetime
    updated_at: datetime


class ExecuteActionRequest(BaseModel):
    """Request to execute a specific distribution action."""

    parameters: dict[str, str] = Field(default_factory=dict)


class ExecuteActionResponse(BaseModel):
    """Response for action execution."""

    action_id: str
    plan_id: str
    status: str
    result: dict[str, object]
    executed_at: datetime


class CoverageSurface(BaseModel):
    """Coverage data for a single surface."""

    surface: str
    coverage_percentage: float
    last_submission: datetime | None = None
    status: str


class DistributionCoverageResponse(BaseModel):
    """Response for distribution coverage."""

    brand_id: str
    overall_coverage: float
    surfaces: list[CoverageSurface]
    calculated_at: datetime


class GeneratePRBriefRequest(BaseModel):
    """Request to generate a PR brief."""

    topic: str
    target_publications: list[str] = Field(default_factory=list)
    tone: str = "professional"


class PRBriefResponse(BaseModel):
    """Response for a generated PR brief."""

    brief_id: str
    brand_id: str
    topic: str
    headline: str
    body: str
    target_publications: list[str]
    generated_at: datetime


class MapSurfacesRequest(BaseModel):
    """Request to map AI-crawled surfaces."""

    categories: list[str] = Field(default_factory=list)
    include_competitors: bool = False


class SurfaceMapping(BaseModel):
    """A mapped AI-crawled surface."""

    surface_id: str
    name: str
    url: str
    category: str
    crawl_frequency: str
    relevance_score: float


class MapSurfacesResponse(BaseModel):
    """Response for surface mapping."""

    brand_id: str
    surfaces: list[SurfaceMapping]
    total_surfaces: int
    mapped_at: datetime


# =============================================================================
# Intelligence Engine Schemas
# =============================================================================


class CalculateAVSRequest(BaseModel):
    """Request to calculate AI Visibility Score."""

    weights: dict[str, float] | None = Field(
        None,
        description="Optional custom weights. Keys: citation_frequency, entity_depth, content_geo, distribution_coverage",
    )


class ScoreComponentResponse(BaseModel):
    """A single component of the AVS."""

    module_name: str
    score: float
    weight: float
    weighted_score: float


class AVSResponse(BaseModel):
    """Response for AI Visibility Score."""

    id: str
    brand_id: str
    overall_score: float
    components: list[ScoreComponentResponse]
    delta: float
    previous_score: float | None = None
    calculated_at: datetime


class AVSTrendPoint(BaseModel):
    """A single point in the AVS trend."""

    timestamp: datetime
    score: float


class AVSTrendsResponse(BaseModel):
    """Response for AVS trends."""

    brand_id: str
    period: str
    trend_direction: str
    change_rate: float
    data_points: list[AVSTrendPoint]


class RecommendationResponse(BaseModel):
    """Response for a single recommendation."""

    id: str
    source_module: str
    action_description: str
    expected_avs_impact: float
    effort_level: str
    priority_rank: int
    linked_entity_id: str
    created_at: datetime


class RecommendationQueueResponse(BaseModel):
    """Response for the recommendation queue."""

    brand_id: str
    recommendations: list[RecommendationResponse]
    total_count: int


class RunRootCauseRequest(BaseModel):
    """Request to run root cause analysis."""

    current_scores: dict[str, float]
    previous_scores: dict[str, float]
    external_signals: list[str] = Field(default_factory=list)


class RootCauseResponse(BaseModel):
    """Response for a single root cause."""

    factor: str
    module: str
    evidence: str
    contribution_weight: float


class RootCauseAnalysisResponse(BaseModel):
    """Response for root cause analysis."""

    id: str
    brand_id: str
    trigger: str
    causes: list[RootCauseResponse]
    recommended_actions: list[str]
    analyzed_at: datetime
