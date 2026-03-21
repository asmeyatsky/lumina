"""
SQLAlchemy ORM Models for LUMINA

Maps all domain entities across the five bounded contexts (PULSE, GRAPH, BEAM,
SIGNAL, INTELLIGENCE) to PostgreSQL tables.  Every table carries ``tenant_id``
for multi-tenant isolation and ``created_at`` / ``updated_at`` audit columns.
"""

from __future__ import annotations

import enum
from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# PostgreSQL enum types mirroring domain enums
# ---------------------------------------------------------------------------

class CitationPositionEnum(enum.Enum):
    FIRST = 1
    SECOND = 2
    THIRD = 3
    MENTIONED = 4
    NOT_CITED = 5


class SentimentEnum(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class RunStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DimensionTypeEnum(str, enum.Enum):
    IDENTITY = "identity"
    PRODUCTS_SERVICES = "products_services"
    PEOPLE = "people"
    TOPIC_AUTHORITY = "topic_authority"
    ACHIEVEMENTS = "achievements"
    RELATIONSHIPS = "relationships"
    COMPETITIVE_POSITION = "competitive_position"
    TEMPORAL_DATA = "temporal_data"


class GapSeverityEnum(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContentTypeEnum(str, enum.Enum):
    WEB_PAGE = "web_page"
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    BLOG_POST = "blog_post"
    LANDING_PAGE = "landing_page"


class GEOFactorEnum(str, enum.Enum):
    ENTITY_DENSITY = "entity_density"
    ANSWER_SHAPE = "answer_shape"
    FACT_CITABILITY = "fact_citability"
    RAG_SURVIVABILITY = "rag_survivability"
    SEMANTIC_AUTHORITY = "semantic_authority"
    FRESHNESS_SIGNALS = "freshness_signals"


class SurfaceCategoryEnum(str, enum.Enum):
    STRUCTURED_DATA = "structured_data"
    AUTHORITY_PUBLICATIONS = "authority_publications"
    QA_PLATFORMS = "qa_platforms"
    DEVELOPER_COMMUNITIES = "developer_communities"
    ACADEMIC_RESEARCH = "academic_research"
    BUSINESS_DIRECTORIES = "business_directories"
    NEWS_SYNDICATION = "news_syndication"


class PresenceStatusEnum(str, enum.Enum):
    PRESENT = "present"
    PARTIAL = "partial"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class ActionTypeEnum(str, enum.Enum):
    SUBMIT_STRUCTURED_DATA = "submit_structured_data"
    PUBLISH_CONTENT = "publish_content"
    UPDATE_WIKIDATA = "update_wikidata"
    SYNDICATE_ARTICLE = "syndicate_article"
    ENGAGE_COMMUNITY = "engage_community"
    SUBMIT_PR_BRIEF = "submit_pr_brief"


class ActionStatusEnum(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AIEngineEnum(str, enum.Enum):
    CLAUDE = "claude"
    GPT4O = "gpt-4o"
    GEMINI = "gemini"
    PERPLEXITY = "perplexity"


class EffortLevelEnum(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Declarative base for all LUMINA ORM models."""

    pass


class BaseModel(Base):
    """Abstract base providing id, tenant_id, created_at, updated_at."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


# ============================================================================
# PULSE models
# ============================================================================

class PromptBatteryModel(BaseModel):
    __tablename__ = "pulse_prompt_batteries"
    __table_args__ = (
        Index("ix_pulse_batteries_brand_id", "brand_id"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vertical: Mapped[str] = mapped_column(String(128), nullable=False)
    schedule_cron: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    prompts: Mapped[list[PromptTemplateModel]] = relationship(
        "PromptTemplateModel", back_populates="battery", cascade="all, delete-orphan",
        lazy="selectin",
    )


class PromptTemplateModel(BaseModel):
    __tablename__ = "pulse_prompt_templates"
    __table_args__ = (
        Index("ix_pulse_templates_battery_id", "battery_id"),
    )

    battery_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pulse_prompt_batteries.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    intent_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    battery: Mapped[PromptBatteryModel] = relationship(
        "PromptBatteryModel", back_populates="prompts"
    )


class MonitoringRunModel(BaseModel):
    __tablename__ = "pulse_monitoring_runs"
    __table_args__ = (
        Index("ix_pulse_runs_brand_id", "brand_id"),
        Index("ix_pulse_runs_status", "status"),
        Index("ix_pulse_runs_started_at", "started_at"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    battery_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[RunStatusEnum] = mapped_column(
        SAEnum(RunStatusEnum, name="run_status", create_constraint=True),
        default=RunStatusEnum.PENDING,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[list[CitationResultModel]] = relationship(
        "CitationResultModel", back_populates="run", cascade="all, delete-orphan",
        lazy="selectin",
    )


class CitationResultModel(BaseModel):
    __tablename__ = "pulse_citation_results"
    __table_args__ = (
        Index("ix_pulse_results_run_id", "run_id"),
    )

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pulse_monitoring_runs.id", ondelete="CASCADE"), nullable=False
    )
    engine: Mapped[AIEngineEnum] = mapped_column(
        SAEnum(AIEngineEnum, name="ai_engine", create_constraint=True), nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[SentimentEnum] = mapped_column(
        SAEnum(SentimentEnum, name="sentiment", create_constraint=True), nullable=False
    )
    accuracy_score: Mapped[float] = mapped_column(Float, nullable=False)
    response_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    citations: Mapped[list[CitationModel]] = relationship(
        "CitationModel", back_populates="citation_result", cascade="all, delete-orphan",
        lazy="selectin",
    )

    run: Mapped[MonitoringRunModel] = relationship(
        "MonitoringRunModel", back_populates="results"
    )


class CitationModel(BaseModel):
    __tablename__ = "pulse_citations"
    __table_args__ = (
        Index("ix_pulse_citations_result_id", "citation_result_id"),
    )

    citation_result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pulse_citation_results.id", ondelete="CASCADE"), nullable=False
    )
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[CitationPositionEnum] = mapped_column(
        SAEnum(CitationPositionEnum, name="citation_position", create_constraint=True),
        nullable=False,
    )
    is_recommendation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    citation_result: Mapped[CitationResultModel] = relationship(
        "CitationResultModel", back_populates="citations"
    )


# ============================================================================
# GRAPH models
# ============================================================================

class EntityProfileModel(BaseModel):
    __tablename__ = "graph_entity_profiles"
    __table_args__ = (
        Index("ix_graph_profiles_brand_id", "brand_id"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    health_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    dimensions: Mapped[list[EntityDimensionModel]] = relationship(
        "EntityDimensionModel", back_populates="profile", cascade="all, delete-orphan",
        lazy="selectin",
    )


class EntityDimensionModel(BaseModel):
    __tablename__ = "graph_entity_dimensions"
    __table_args__ = (
        Index("ix_graph_dimensions_profile_id", "profile_id"),
    )

    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("graph_entity_profiles.id", ondelete="CASCADE"), nullable=False
    )
    dimension_type: Mapped[DimensionTypeEnum] = mapped_column(
        SAEnum(DimensionTypeEnum, name="dimension_type", create_constraint=True), nullable=False
    )
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, nullable=False)
    sources: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    profile: Mapped[EntityProfileModel] = relationship(
        "EntityProfileModel", back_populates="dimensions"
    )


class KnowledgeGapModel(BaseModel):
    __tablename__ = "graph_knowledge_gaps"
    __table_args__ = (
        Index("ix_graph_gaps_brand_id", "brand_id"),
        Index("ix_graph_gaps_severity", "severity"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    dimension_type: Mapped[DimensionTypeEnum] = mapped_column(
        SAEnum(DimensionTypeEnum, name="dimension_type", create_constraint=True,
               create_type=False),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[GapSeverityEnum] = mapped_column(
        SAEnum(GapSeverityEnum, name="gap_severity", create_constraint=True), nullable=False
    )
    identified_from: Mapped[AIEngineEnum | None] = mapped_column(
        SAEnum(AIEngineEnum, name="ai_engine", create_constraint=True, create_type=False),
        nullable=True,
    )
    recommended_action: Mapped[str] = mapped_column(Text, default="", nullable=False)


# ============================================================================
# BEAM models
# ============================================================================

class ContentAssetModel(BaseModel):
    __tablename__ = "beam_content_assets"
    __table_args__ = (
        Index("ix_beam_assets_brand_id", "brand_id"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[ContentTypeEnum] = mapped_column(
        SAEnum(ContentTypeEnum, name="content_type", create_constraint=True), nullable=False
    )
    last_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Current GEO score stored inline for fast reads
    geo_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_entity_density: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_answer_shape: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_fact_citability: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_rag_survivability: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_semantic_authority: Mapped[float | None] = mapped_column(Float, nullable=True)
    geo_freshness_signals: Mapped[float | None] = mapped_column(Float, nullable=True)

    suggestions: Mapped[list[RewriteSuggestionModel]] = relationship(
        "RewriteSuggestionModel", back_populates="asset", cascade="all, delete-orphan",
        lazy="selectin",
    )


class GEOScoreModel(BaseModel):
    """Historical GEO score records for trend tracking."""

    __tablename__ = "beam_geo_scores"
    __table_args__ = (
        Index("ix_beam_scores_asset_id", "asset_id"),
        Index("ix_beam_scores_created_at", "created_at"),
    )

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("beam_content_assets.id", ondelete="CASCADE"), nullable=False
    )
    overall: Mapped[float] = mapped_column(Float, nullable=False)
    entity_density: Mapped[float] = mapped_column(Float, nullable=False)
    answer_shape: Mapped[float] = mapped_column(Float, nullable=False)
    fact_citability: Mapped[float] = mapped_column(Float, nullable=False)
    rag_survivability: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_authority: Mapped[float] = mapped_column(Float, nullable=False)
    freshness_signals: Mapped[float] = mapped_column(Float, nullable=False)


class RewriteSuggestionModel(BaseModel):
    __tablename__ = "beam_rewrite_suggestions"
    __table_args__ = (
        Index("ix_beam_suggestions_asset_id", "asset_id"),
    )

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("beam_content_assets.id", ondelete="CASCADE"), nullable=False
    )
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str] = mapped_column(Text, nullable=False)
    factor: Mapped[GEOFactorEnum] = mapped_column(
        SAEnum(GEOFactorEnum, name="geo_factor", create_constraint=True), nullable=False
    )
    expected_impact: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    asset: Mapped[ContentAssetModel] = relationship(
        "ContentAssetModel", back_populates="suggestions"
    )


class RAGSimulationResultModel(BaseModel):
    __tablename__ = "beam_rag_simulation_results"
    __table_args__ = (
        Index("ix_beam_rag_results_asset_id", "asset_id"),
    )

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("beam_content_assets.id", ondelete="CASCADE"), nullable=False
    )
    survived_facts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    lost_facts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    survivability_score: Mapped[float] = mapped_column(Float, nullable=False)
    chunks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


# ============================================================================
# SIGNAL models
# ============================================================================

class DistributionPlanModel(BaseModel):
    __tablename__ = "signal_distribution_plans"
    __table_args__ = (
        Index("ix_signal_plans_brand_id", "brand_id"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    coverage_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    actions: Mapped[list[DistributionActionModel]] = relationship(
        "DistributionActionModel", back_populates="plan", cascade="all, delete-orphan",
        lazy="selectin",
    )


class CitationSurfaceModel(BaseModel):
    __tablename__ = "signal_citation_surfaces"
    __table_args__ = (
        Index("ix_signal_surfaces_brand_id", "brand_id"),
        Index("ix_signal_surfaces_category", "category"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[SurfaceCategoryEnum] = mapped_column(
        SAEnum(SurfaceCategoryEnum, name="surface_category", create_constraint=True),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_llm_weight: Mapped[float] = mapped_column(Float, nullable=False)
    brand_presence: Mapped[PresenceStatusEnum] = mapped_column(
        SAEnum(PresenceStatusEnum, name="presence_status", create_constraint=True),
        nullable=False,
    )
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DistributionActionModel(BaseModel):
    __tablename__ = "signal_distribution_actions"
    __table_args__ = (
        Index("ix_signal_actions_plan_id", "plan_id"),
        Index("ix_signal_actions_status", "status"),
    )

    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("signal_distribution_plans.id", ondelete="CASCADE"), nullable=False
    )
    surface_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_type: Mapped[ActionTypeEnum] = mapped_column(
        SAEnum(ActionTypeEnum, name="action_type", create_constraint=True), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ActionStatusEnum] = mapped_column(
        SAEnum(ActionStatusEnum, name="action_status", create_constraint=True),
        default=ActionStatusEnum.PLANNED,
        nullable=False,
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[DistributionPlanModel] = relationship(
        "DistributionPlanModel", back_populates="actions"
    )


class PRBriefModel(BaseModel):
    __tablename__ = "signal_pr_briefs"
    __table_args__ = (
        Index("ix_signal_pr_briefs_brand_id", "brand_id"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    headline: Mapped[str] = mapped_column(String(512), nullable=False)
    narrative_angle: Mapped[str] = mapped_column(Text, nullable=False)
    target_publications: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    key_messages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    entity_anchors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


# ============================================================================
# INTELLIGENCE models
# ============================================================================

class AIVisibilityScoreModel(BaseModel):
    __tablename__ = "intelligence_ai_visibility_scores"
    __table_args__ = (
        Index("ix_intelligence_avs_brand_id", "brand_id"),
        Index("ix_intelligence_avs_calculated_at", "calculated_at"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    overall: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    components: Mapped[list[ScoreComponentModel]] = relationship(
        "ScoreComponentModel", back_populates="avs", cascade="all, delete-orphan",
        lazy="selectin",
    )


class ScoreComponentModel(BaseModel):
    __tablename__ = "intelligence_score_components"
    __table_args__ = (
        Index("ix_intelligence_components_avs_id", "avs_id"),
    )

    avs_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("intelligence_ai_visibility_scores.id", ondelete="CASCADE"),
        nullable=False,
    )
    module_name: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    raw_metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    avs: Mapped[AIVisibilityScoreModel] = relationship(
        "AIVisibilityScoreModel", back_populates="components"
    )


class RecommendationModel(BaseModel):
    __tablename__ = "intelligence_recommendations"
    __table_args__ = (
        Index("ix_intelligence_recs_brand_id", "brand_id"),
        Index("ix_intelligence_recs_priority", "priority_rank"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_module: Mapped[str] = mapped_column(String(32), nullable=False)
    action_description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_avs_impact: Mapped[float] = mapped_column(Float, nullable=False)
    effort_level: Mapped[EffortLevelEnum] = mapped_column(
        SAEnum(EffortLevelEnum, name="effort_level", create_constraint=True), nullable=False
    )
    priority_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    linked_entity_id: Mapped[str] = mapped_column(String(36), default="", nullable=False)


class RootCauseAnalysisModel(BaseModel):
    __tablename__ = "intelligence_root_cause_analyses"
    __table_args__ = (
        Index("ix_intelligence_rca_brand_id", "brand_id"),
        Index("ix_intelligence_rca_analyzed_at", "analyzed_at"),
    )

    brand_id: Mapped[str] = mapped_column(String(36), nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False, default="")
    causes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    recommended_actions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
