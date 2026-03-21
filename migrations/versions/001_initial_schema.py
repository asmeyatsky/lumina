"""Initial schema — all LUMINA tables

Revision ID: 001_initial
Revises:
Create Date: 2026-03-21
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enum types
# ---------------------------------------------------------------------------

run_status = sa.Enum(
    "pending", "running", "completed", "failed",
    name="run_status",
)
ai_engine = sa.Enum(
    "claude", "gpt-4o", "gemini", "perplexity",
    name="ai_engine",
)
sentiment = sa.Enum(
    "positive", "neutral", "negative",
    name="sentiment",
)
citation_position = sa.Enum(
    "FIRST", "SECOND", "THIRD", "MENTIONED", "NOT_CITED",
    name="citation_position",
)
dimension_type = sa.Enum(
    "identity", "products_services", "people", "topic_authority",
    "achievements", "relationships", "competitive_position", "temporal_data",
    name="dimension_type",
)
gap_severity = sa.Enum(
    "critical", "high", "medium", "low",
    name="gap_severity",
)
content_type = sa.Enum(
    "web_page", "pdf", "docx", "html", "blog_post", "landing_page",
    name="content_type",
)
geo_factor = sa.Enum(
    "entity_density", "answer_shape", "fact_citability",
    "rag_survivability", "semantic_authority", "freshness_signals",
    name="geo_factor",
)
surface_category = sa.Enum(
    "structured_data", "authority_publications", "qa_platforms",
    "developer_communities", "academic_research", "business_directories",
    "news_syndication",
    name="surface_category",
)
presence_status = sa.Enum(
    "present", "partial", "absent", "unknown",
    name="presence_status",
)
action_type = sa.Enum(
    "submit_structured_data", "publish_content", "update_wikidata",
    "syndicate_article", "engage_community", "submit_pr_brief",
    name="action_type",
)
action_status = sa.Enum(
    "planned", "in_progress", "completed", "failed", "skipped",
    name="action_status",
)
effort_level = sa.Enum(
    "low", "medium", "high",
    name="effort_level",
)


def upgrade() -> None:
    # Create enum types first
    run_status.create(op.get_bind(), checkfirst=True)
    ai_engine.create(op.get_bind(), checkfirst=True)
    sentiment.create(op.get_bind(), checkfirst=True)
    citation_position.create(op.get_bind(), checkfirst=True)
    dimension_type.create(op.get_bind(), checkfirst=True)
    gap_severity.create(op.get_bind(), checkfirst=True)
    content_type.create(op.get_bind(), checkfirst=True)
    geo_factor.create(op.get_bind(), checkfirst=True)
    surface_category.create(op.get_bind(), checkfirst=True)
    presence_status.create(op.get_bind(), checkfirst=True)
    action_type.create(op.get_bind(), checkfirst=True)
    action_status.create(op.get_bind(), checkfirst=True)
    effort_level.create(op.get_bind(), checkfirst=True)

    # ========================================================================
    # PULSE tables
    # ========================================================================

    op.create_table(
        "pulse_prompt_batteries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vertical", sa.String(128), nullable=False),
        sa.Column("schedule_cron", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pulse_batteries_tenant_id", "pulse_prompt_batteries", ["tenant_id"])
    op.create_index("ix_pulse_batteries_brand_id", "pulse_prompt_batteries", ["brand_id"])

    op.create_table(
        "pulse_prompt_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("battery_id", sa.String(36), sa.ForeignKey("pulse_prompt_batteries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("intent_tags", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pulse_templates_tenant_id", "pulse_prompt_templates", ["tenant_id"])
    op.create_index("ix_pulse_templates_battery_id", "pulse_prompt_templates", ["battery_id"])

    op.create_table(
        "pulse_monitoring_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("battery_id", sa.String(36), nullable=False),
        sa.Column("status", run_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pulse_runs_tenant_id", "pulse_monitoring_runs", ["tenant_id"])
    op.create_index("ix_pulse_runs_brand_id", "pulse_monitoring_runs", ["brand_id"])
    op.create_index("ix_pulse_runs_status", "pulse_monitoring_runs", ["status"])
    op.create_index("ix_pulse_runs_started_at", "pulse_monitoring_runs", ["started_at"])

    op.create_table(
        "pulse_citation_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("pulse_monitoring_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engine", ai_engine, nullable=False),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("raw_response", sa.Text, nullable=False),
        sa.Column("sentiment", sentiment, nullable=False),
        sa.Column("accuracy_score", sa.Float, nullable=False),
        sa.Column("response_latency_ms", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pulse_results_tenant_id", "pulse_citation_results", ["tenant_id"])
    op.create_index("ix_pulse_results_run_id", "pulse_citation_results", ["run_id"])

    op.create_table(
        "pulse_citations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("citation_result_id", sa.String(36), sa.ForeignKey("pulse_citation_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_name", sa.String(255), nullable=False),
        sa.Column("context", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("position", citation_position, nullable=False),
        sa.Column("is_recommendation", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pulse_citations_tenant_id", "pulse_citations", ["tenant_id"])
    op.create_index("ix_pulse_citations_result_id", "pulse_citations", ["citation_result_id"])

    # ========================================================================
    # GRAPH tables
    # ========================================================================

    op.create_table(
        "graph_entity_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("health_score", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_graph_profiles_tenant_id", "graph_entity_profiles", ["tenant_id"])
    op.create_index("ix_graph_profiles_brand_id", "graph_entity_profiles", ["brand_id"])

    op.create_table(
        "graph_entity_dimensions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("graph_entity_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension_type", dimension_type, nullable=False),
        sa.Column("data", JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("completeness_score", sa.Float, nullable=False),
        sa.Column("sources", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_graph_dimensions_tenant_id", "graph_entity_dimensions", ["tenant_id"])
    op.create_index("ix_graph_dimensions_profile_id", "graph_entity_dimensions", ["profile_id"])

    op.create_table(
        "graph_knowledge_gaps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("dimension_type", dimension_type, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("severity", gap_severity, nullable=False),
        sa.Column("identified_from", ai_engine, nullable=True),
        sa.Column("recommended_action", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_graph_gaps_tenant_id", "graph_knowledge_gaps", ["tenant_id"])
    op.create_index("ix_graph_gaps_brand_id", "graph_knowledge_gaps", ["brand_id"])
    op.create_index("ix_graph_gaps_severity", "graph_knowledge_gaps", ["severity"])

    # ========================================================================
    # BEAM tables
    # ========================================================================

    op.create_table(
        "beam_content_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("raw_content", sa.Text, nullable=False),
        sa.Column("content_type", content_type, nullable=False),
        sa.Column("last_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("geo_overall", sa.Float, nullable=True),
        sa.Column("geo_entity_density", sa.Float, nullable=True),
        sa.Column("geo_answer_shape", sa.Float, nullable=True),
        sa.Column("geo_fact_citability", sa.Float, nullable=True),
        sa.Column("geo_rag_survivability", sa.Float, nullable=True),
        sa.Column("geo_semantic_authority", sa.Float, nullable=True),
        sa.Column("geo_freshness_signals", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_beam_assets_tenant_id", "beam_content_assets", ["tenant_id"])
    op.create_index("ix_beam_assets_brand_id", "beam_content_assets", ["brand_id"])

    op.create_table(
        "beam_geo_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("beam_content_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall", sa.Float, nullable=False),
        sa.Column("entity_density", sa.Float, nullable=False),
        sa.Column("answer_shape", sa.Float, nullable=False),
        sa.Column("fact_citability", sa.Float, nullable=False),
        sa.Column("rag_survivability", sa.Float, nullable=False),
        sa.Column("semantic_authority", sa.Float, nullable=False),
        sa.Column("freshness_signals", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_beam_scores_tenant_id", "beam_geo_scores", ["tenant_id"])
    op.create_index("ix_beam_scores_asset_id", "beam_geo_scores", ["asset_id"])
    op.create_index("ix_beam_scores_created_at", "beam_geo_scores", ["created_at"])

    op.create_table(
        "beam_rewrite_suggestions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("beam_content_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_text", sa.Text, nullable=False),
        sa.Column("suggested_text", sa.Text, nullable=False),
        sa.Column("factor", geo_factor, nullable=False),
        sa.Column("expected_impact", sa.Float, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_beam_suggestions_tenant_id", "beam_rewrite_suggestions", ["tenant_id"])
    op.create_index("ix_beam_suggestions_asset_id", "beam_rewrite_suggestions", ["asset_id"])

    op.create_table(
        "beam_rag_simulation_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("beam_content_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("survived_facts", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("lost_facts", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("survivability_score", sa.Float, nullable=False),
        sa.Column("chunks", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_beam_rag_results_tenant_id", "beam_rag_simulation_results", ["tenant_id"])
    op.create_index("ix_beam_rag_results_asset_id", "beam_rag_simulation_results", ["asset_id"])

    # ========================================================================
    # SIGNAL tables
    # ========================================================================

    op.create_table(
        "signal_distribution_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("coverage_score", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_signal_plans_tenant_id", "signal_distribution_plans", ["tenant_id"])
    op.create_index("ix_signal_plans_brand_id", "signal_distribution_plans", ["brand_id"])

    op.create_table(
        "signal_citation_surfaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", surface_category, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("estimated_llm_weight", sa.Float, nullable=False),
        sa.Column("brand_presence", presence_status, nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_signal_surfaces_tenant_id", "signal_citation_surfaces", ["tenant_id"])
    op.create_index("ix_signal_surfaces_brand_id", "signal_citation_surfaces", ["brand_id"])
    op.create_index("ix_signal_surfaces_category", "signal_citation_surfaces", ["category"])

    op.create_table(
        "signal_distribution_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("signal_distribution_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("surface_id", sa.String(36), nullable=False),
        sa.Column("action_type", action_type, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", action_status, nullable=False, server_default=sa.text("'planned'")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_signal_actions_tenant_id", "signal_distribution_actions", ["tenant_id"])
    op.create_index("ix_signal_actions_plan_id", "signal_distribution_actions", ["plan_id"])
    op.create_index("ix_signal_actions_status", "signal_distribution_actions", ["status"])

    op.create_table(
        "signal_pr_briefs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("headline", sa.String(512), nullable=False),
        sa.Column("narrative_angle", sa.Text, nullable=False),
        sa.Column("target_publications", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("key_messages", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("entity_anchors", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_signal_pr_briefs_tenant_id", "signal_pr_briefs", ["tenant_id"])
    op.create_index("ix_signal_pr_briefs_brand_id", "signal_pr_briefs", ["brand_id"])

    # ========================================================================
    # INTELLIGENCE tables
    # ========================================================================

    op.create_table(
        "intelligence_ai_visibility_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("overall", sa.Float, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_intelligence_avs_tenant_id", "intelligence_ai_visibility_scores", ["tenant_id"])
    op.create_index("ix_intelligence_avs_brand_id", "intelligence_ai_visibility_scores", ["brand_id"])
    op.create_index("ix_intelligence_avs_calculated_at", "intelligence_ai_visibility_scores", ["calculated_at"])

    op.create_table(
        "intelligence_score_components",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("avs_id", sa.String(36), sa.ForeignKey("intelligence_ai_visibility_scores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_name", sa.String(32), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("weight", sa.Float, nullable=False),
        sa.Column("raw_metrics", JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_intelligence_components_tenant_id", "intelligence_score_components", ["tenant_id"])
    op.create_index("ix_intelligence_components_avs_id", "intelligence_score_components", ["avs_id"])

    op.create_table(
        "intelligence_recommendations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("source_module", sa.String(32), nullable=False),
        sa.Column("action_description", sa.Text, nullable=False),
        sa.Column("expected_avs_impact", sa.Float, nullable=False),
        sa.Column("effort_level", effort_level, nullable=False),
        sa.Column("priority_rank", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("linked_entity_id", sa.String(36), nullable=False, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_intelligence_recs_tenant_id", "intelligence_recommendations", ["tenant_id"])
    op.create_index("ix_intelligence_recs_brand_id", "intelligence_recommendations", ["brand_id"])
    op.create_index("ix_intelligence_recs_priority", "intelligence_recommendations", ["priority_rank"])

    op.create_table(
        "intelligence_root_cause_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), nullable=False),
        sa.Column("trigger", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("causes", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("recommended_actions", JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_intelligence_rca_tenant_id", "intelligence_root_cause_analyses", ["tenant_id"])
    op.create_index("ix_intelligence_rca_brand_id", "intelligence_root_cause_analyses", ["brand_id"])
    op.create_index("ix_intelligence_rca_analyzed_at", "intelligence_root_cause_analyses", ["analyzed_at"])


def downgrade() -> None:
    # INTELLIGENCE
    op.drop_table("intelligence_root_cause_analyses")
    op.drop_table("intelligence_recommendations")
    op.drop_table("intelligence_score_components")
    op.drop_table("intelligence_ai_visibility_scores")

    # SIGNAL
    op.drop_table("signal_pr_briefs")
    op.drop_table("signal_distribution_actions")
    op.drop_table("signal_citation_surfaces")
    op.drop_table("signal_distribution_plans")

    # BEAM
    op.drop_table("beam_rag_simulation_results")
    op.drop_table("beam_rewrite_suggestions")
    op.drop_table("beam_geo_scores")
    op.drop_table("beam_content_assets")

    # GRAPH
    op.drop_table("graph_knowledge_gaps")
    op.drop_table("graph_entity_dimensions")
    op.drop_table("graph_entity_profiles")

    # PULSE
    op.drop_table("pulse_citations")
    op.drop_table("pulse_citation_results")
    op.drop_table("pulse_monitoring_runs")
    op.drop_table("pulse_prompt_templates")
    op.drop_table("pulse_prompt_batteries")

    # Drop enum types
    effort_level.drop(op.get_bind(), checkfirst=True)
    action_status.drop(op.get_bind(), checkfirst=True)
    action_type.drop(op.get_bind(), checkfirst=True)
    presence_status.drop(op.get_bind(), checkfirst=True)
    surface_category.drop(op.get_bind(), checkfirst=True)
    geo_factor.drop(op.get_bind(), checkfirst=True)
    content_type.drop(op.get_bind(), checkfirst=True)
    gap_severity.drop(op.get_bind(), checkfirst=True)
    dimension_type.drop(op.get_bind(), checkfirst=True)
    citation_position.drop(op.get_bind(), checkfirst=True)
    sentiment.drop(op.get_bind(), checkfirst=True)
    ai_engine.drop(op.get_bind(), checkfirst=True)
    run_status.drop(op.get_bind(), checkfirst=True)
