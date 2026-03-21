"""
BEAM Application Queries — Read-side use cases

Architectural Intent:
- Read-side use cases that do not mutate state
- Each query encapsulates a single read operation
- Depend on repository ports, never on infrastructure
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.value_objects import Score

from lumina.beam.domain.entities import ContentAsset, GEOScore, RewriteSuggestion
from lumina.beam.domain.ports import BeamRepositoryPort
from lumina.beam.domain.value_objects import ContentAuditSummary, GEOFactor


@dataclass(frozen=True)
class GetContentScoreQuery:
    """Returns the current GEO score for a content asset."""

    repository: BeamRepositoryPort

    async def execute(self, asset_id: str) -> GEOScore | None:
        """Retrieve the GEO score for a content asset.

        Args:
            asset_id: The content asset identifier.

        Returns:
            The GEOScore if the asset exists and has been scored, else None.
        """
        asset = await self.repository.get_asset(asset_id)
        if asset is None:
            return None
        return asset.geo_score


@dataclass(frozen=True)
class GetAuditSummaryQuery:
    """Returns an audit summary for a brand's content estate."""

    repository: BeamRepositoryPort

    async def execute(self, brand_id: str, threshold: float = 60.0) -> ContentAuditSummary:
        """Compute an audit summary across all content assets for a brand.

        Args:
            brand_id: The brand to summarise.
            threshold: Score threshold below which assets are flagged.

        Returns:
            A ContentAuditSummary with aggregate metrics.
        """
        assets = await self.repository.list_assets_for_brand(brand_id)

        scored_assets = [a for a in assets if a.geo_score is not None]
        total = len(scored_assets)

        if total == 0:
            return ContentAuditSummary(
                total_assets=0,
                avg_geo_score=Score(value=0.0),
                assets_below_threshold=0,
                top_improvement_opportunities=(),
            )

        scores = [a.geo_score.overall.value for a in scored_assets if a.geo_score]
        avg = sum(scores) / len(scores)
        below = sum(1 for s in scores if s < threshold)

        factor_weaknesses: dict[str, float] = {}
        for asset in scored_assets:
            geo = asset.geo_score
            if geo is None:
                continue
            factor_scores = {
                GEOFactor.ENTITY_DENSITY.value: geo.entity_density.value,
                GEOFactor.ANSWER_SHAPE.value: geo.answer_shape.value,
                GEOFactor.FACT_CITABILITY.value: geo.fact_citability.value,
                GEOFactor.RAG_SURVIVABILITY.value: geo.rag_survivability.value,
                GEOFactor.SEMANTIC_AUTHORITY.value: geo.semantic_authority.value,
                GEOFactor.FRESHNESS_SIGNALS.value: geo.freshness_signals.value,
            }
            for factor, score_val in factor_scores.items():
                factor_weaknesses[factor] = factor_weaknesses.get(factor, 0.0) + score_val

        factor_averages = {
            f: total_score / total for f, total_score in factor_weaknesses.items()
        }
        sorted_factors = sorted(factor_averages.items(), key=lambda x: x[1])
        opportunities = tuple(
            f"Improve {factor} (avg: {avg_val:.1f})"
            for factor, avg_val in sorted_factors[:3]
        )

        return ContentAuditSummary(
            total_assets=total,
            avg_geo_score=Score(value=round(avg, 2)),
            assets_below_threshold=below,
            top_improvement_opportunities=opportunities,
        )


@dataclass(frozen=True)
class GetScoreTrendsQuery:
    """Returns score trends over time for a content asset."""

    repository: BeamRepositoryPort

    async def execute(self, asset_id: str) -> list[GEOScore]:
        """Retrieve the score history for a content asset.

        Args:
            asset_id: The content asset identifier.

        Returns:
            A list of GEOScore instances ordered chronologically.
        """
        return await self.repository.get_score_history(asset_id)


@dataclass(frozen=True)
class GetRewriteSuggestionsQuery:
    """Returns rewrite suggestions for a content asset."""

    repository: BeamRepositoryPort

    async def execute(self, asset_id: str) -> tuple[RewriteSuggestion, ...]:
        """Retrieve rewrite suggestions for a content asset.

        Args:
            asset_id: The content asset identifier.

        Returns:
            A tuple of RewriteSuggestion instances, or empty tuple if none exist.
        """
        asset = await self.repository.get_asset(asset_id)
        if asset is None:
            return ()
        return asset.suggestions
