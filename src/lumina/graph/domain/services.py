"""
GRAPH Domain Services

Architectural Intent:
- Pure domain logic with no infrastructure dependencies
- Stateless services that operate on domain entities and value objects
- Each service encapsulates a single cohesive domain responsibility
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import BrandId, Score, AIEngine

from lumina.graph.domain.entities import (
    EntityProfile,
    EntityDimension,
    KnowledgeGap,
    CompetitorEntityComparison,
)
from lumina.graph.domain.value_objects import (
    DimensionType,
    GapSeverity,
    EntityHealth,
    JsonLdDocument,
)


# ---------------------------------------------------------------------------
# Weights used by scoring — critical dimensions count more
# ---------------------------------------------------------------------------
_DIMENSION_WEIGHTS: dict[DimensionType, float] = {
    DimensionType.IDENTITY: 1.5,
    DimensionType.PRODUCTS_SERVICES: 1.3,
    DimensionType.PEOPLE: 1.0,
    DimensionType.TOPIC_AUTHORITY: 1.2,
    DimensionType.ACHIEVEMENTS: 0.8,
    DimensionType.RELATIONSHIPS: 0.9,
    DimensionType.COMPETITIVE_POSITION: 1.0,
    DimensionType.TEMPORAL_DATA: 0.7,
}


class GapAnalysisService:
    """Compares an entity profile against AI-engine knowledge to find gaps."""

    def analyze_gaps(
        self,
        profile: EntityProfile,
        ai_knowledge: dict[str, dict],
    ) -> list[KnowledgeGap]:
        """Identify knowledge gaps.

        ``ai_knowledge`` maps DimensionType *values* (strings) to dicts of
        key/value pairs that the AI engines know about the brand.  If a
        dimension type is entirely missing from ``ai_knowledge`` or has an
        empty dict, it is treated as a critical gap.  If present but the
        profile dimension is incomplete, it is a proportional gap.

        Parameters
        ----------
        profile:
            The brand's current entity profile.
        ai_knowledge:
            ``{ "identity": {"name": "Acme", ...}, ... }`` — what AI engines
            know.  Typically sourced from the PULSE bounded context.
        """
        gaps: list[KnowledgeGap] = []
        dim_by_type: dict[DimensionType, EntityDimension] = {}
        for dim in profile.dimensions:
            dim_by_type[dim.dimension_type] = dim

        for dim_type in DimensionType:
            profile_dim = dim_by_type.get(dim_type)
            ai_data = ai_knowledge.get(dim_type.value, {})

            if profile_dim is None:
                # Dimension completely absent from the profile
                severity = (
                    GapSeverity.CRITICAL
                    if dim_type in (DimensionType.IDENTITY, DimensionType.PRODUCTS_SERVICES)
                    else GapSeverity.HIGH
                )
                gaps.append(
                    KnowledgeGap(
                        id=str(uuid4()),
                        brand_id=profile.brand_id,
                        dimension_type=dim_type,
                        description=f"Missing {dim_type.value} dimension entirely",
                        severity=severity,
                        identified_from=None,
                        recommended_action=f"Create {dim_type.value} dimension with foundational data",
                    )
                )
                continue

            # Check for keys the AI knows about but the profile lacks
            profile_data = profile_dim.data_as_dict
            if ai_data:
                missing_keys = set(ai_data.keys()) - set(profile_data.keys())
                if missing_keys:
                    severity = self._severity_for_missing_keys(
                        dim_type, len(missing_keys), len(ai_data)
                    )
                    gaps.append(
                        KnowledgeGap(
                            id=str(uuid4()),
                            brand_id=profile.brand_id,
                            dimension_type=dim_type,
                            description=(
                                f"AI engines reference {len(missing_keys)} "
                                f"attributes not in profile: {', '.join(sorted(missing_keys))}"
                            ),
                            severity=severity,
                            identified_from=None,
                            recommended_action=(
                                f"Add missing attributes to {dim_type.value} dimension"
                            ),
                        )
                    )

                # Check for mismatched values
                for key in set(ai_data.keys()) & set(profile_data.keys()):
                    if ai_data[key] != profile_data[key]:
                        gaps.append(
                            KnowledgeGap(
                                id=str(uuid4()),
                                brand_id=profile.brand_id,
                                dimension_type=dim_type,
                                description=(
                                    f"AI knowledge mismatch for '{key}': "
                                    f"profile='{profile_data[key]}' vs ai='{ai_data[key]}'"
                                ),
                                severity=GapSeverity.MEDIUM,
                                identified_from=None,
                                recommended_action=(
                                    f"Verify and correct '{key}' in {dim_type.value} dimension"
                                ),
                            )
                        )

            # Low completeness is itself a gap
            if profile_dim.completeness_score.value < 50.0:
                gaps.append(
                    KnowledgeGap(
                        id=str(uuid4()),
                        brand_id=profile.brand_id,
                        dimension_type=dim_type,
                        description=(
                            f"{dim_type.value} completeness is only "
                            f"{profile_dim.completeness_score.value}%"
                        ),
                        severity=GapSeverity.HIGH,
                        identified_from=None,
                        recommended_action=(
                            f"Enrich {dim_type.value} data to improve completeness"
                        ),
                    )
                )

        return gaps

    @staticmethod
    def _severity_for_missing_keys(
        dim_type: DimensionType,
        missing_count: int,
        total_count: int,
    ) -> GapSeverity:
        ratio = missing_count / total_count if total_count else 1.0
        if dim_type in (DimensionType.IDENTITY, DimensionType.PRODUCTS_SERVICES):
            return GapSeverity.CRITICAL if ratio > 0.5 else GapSeverity.HIGH
        if ratio > 0.5:
            return GapSeverity.HIGH
        if ratio > 0.25:
            return GapSeverity.MEDIUM
        return GapSeverity.LOW


class EntityScoringService:
    """Calculates dimension and overall health scores."""

    def calculate_dimension_score(self, dimension: EntityDimension) -> Score:
        """Score a single dimension based on data richness and source count.

        Formula:
        - base = number of data entries, capped at 10 -> 0-50 points
        - source_bonus = number of sources, capped at 5 -> 0-25 points
        - recency_bonus = up to 25 points if last_verified within 30 days
        """
        data_count = len(dimension.data)
        base = min(data_count, 10) * 5.0  # max 50

        source_count = len(dimension.sources)
        source_bonus = min(source_count, 5) * 5.0  # max 25

        now = datetime.now(UTC)
        days_old = (now - dimension.last_verified_at).days
        if days_old <= 7:
            recency_bonus = 25.0
        elif days_old <= 30:
            recency_bonus = 15.0
        elif days_old <= 90:
            recency_bonus = 5.0
        else:
            recency_bonus = 0.0

        raw = base + source_bonus + recency_bonus
        return Score(min(round(raw, 2), 100.0))

    def calculate_overall_health(self, profile: EntityProfile) -> EntityHealth:
        """Compute weighted health across all dimension types."""
        dim_by_type: dict[DimensionType, Score] = {}
        for dim in profile.dimensions:
            score = self.calculate_dimension_score(dim)
            existing = dim_by_type.get(dim.dimension_type)
            if existing is None or score.value > existing.value:
                dim_by_type[dim.dimension_type] = score

        weighted_sum = 0.0
        weight_total = 0.0
        for dim_type in DimensionType:
            weight = _DIMENSION_WEIGHTS[dim_type]
            score = dim_by_type.get(dim_type, Score(0.0))
            weighted_sum += score.value * weight
            weight_total += weight

        overall = round(weighted_sum / weight_total, 2) if weight_total else 0.0
        overall = min(overall, 100.0)

        dimension_scores_tuple = tuple(
            (dt, dim_by_type.get(dt, Score(0.0))) for dt in DimensionType
        )

        return EntityHealth(
            overall_score=Score(overall),
            dimension_scores=dimension_scores_tuple,
            gaps_count=sum(1 for dt in DimensionType if dt not in dim_by_type),
            last_audit_at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Mapping from DimensionType to schema.org types and property mappings
# ---------------------------------------------------------------------------
_SCHEMA_ORG_MAPPING: dict[DimensionType, tuple[str, dict[str, str]]] = {
    DimensionType.IDENTITY: (
        "Organization",
        {"name": "name", "description": "description", "url": "url", "logo": "logo"},
    ),
    DimensionType.PRODUCTS_SERVICES: (
        "Product",
        {"name": "name", "description": "description", "category": "category", "brand": "brand"},
    ),
    DimensionType.PEOPLE: (
        "Person",
        {"name": "name", "jobTitle": "jobTitle", "email": "email", "url": "url"},
    ),
    DimensionType.TOPIC_AUTHORITY: (
        "Article",
        {"name": "headline", "about": "about", "author": "author"},
    ),
    DimensionType.ACHIEVEMENTS: (
        "CreativeWork",
        {"name": "name", "award": "award", "description": "description"},
    ),
    DimensionType.RELATIONSHIPS: (
        "Organization",
        {"name": "name", "member": "member", "partner": "partner"},
    ),
    DimensionType.COMPETITIVE_POSITION: (
        "Organization",
        {"name": "name", "market": "market", "position": "description"},
    ),
    DimensionType.TEMPORAL_DATA: (
        "Event",
        {"name": "name", "startDate": "startDate", "description": "description"},
    ),
}


class JsonLdGenerationService:
    """Converts entity dimensions into schema.org JSON-LD documents."""

    def generate_json_ld(self, profile: EntityProfile) -> list[JsonLdDocument]:
        """Produce one JSON-LD document per dimension present on the profile."""
        documents: list[JsonLdDocument] = []

        for dim in profile.dimensions:
            mapping = _SCHEMA_ORG_MAPPING.get(dim.dimension_type)
            if mapping is None:
                continue

            schema_type, property_map = mapping
            data = dim.data_as_dict

            props: list[tuple[str, str]] = []
            for data_key, schema_prop in property_map.items():
                value = data.get(data_key)
                if value is not None:
                    props.append((schema_prop, value))

            # Always include a name fallback from profile if not present
            prop_keys = {p[0] for p in props}
            if "name" not in prop_keys:
                props.insert(0, ("name", profile.name))

            documents.append(
                JsonLdDocument(
                    context="https://schema.org",
                    type=schema_type,
                    properties=tuple(props),
                )
            )

        return documents


class CompetitorBenchmarkService:
    """Compares a brand's entity profile against competitor profiles."""

    def __init__(self, scoring_service: EntityScoringService | None = None) -> None:
        self._scoring = scoring_service or EntityScoringService()

    def compare_entities(
        self,
        brand_profile: EntityProfile,
        competitor_profiles: list[EntityProfile],
    ) -> list[CompetitorEntityComparison]:
        """Produce a comparison for each competitor."""
        brand_scores = self._scores_by_type(brand_profile)
        comparisons: list[CompetitorEntityComparison] = []

        for comp_profile in competitor_profiles:
            comp_scores = self._scores_by_type(comp_profile)
            dim_entries: list[tuple[DimensionType, Score, Score]] = []

            for dim_type in DimensionType:
                brand_s = brand_scores.get(dim_type, Score(0.0))
                comp_s = comp_scores.get(dim_type, Score(0.0))
                dim_entries.append((dim_type, brand_s, comp_s))

            comparisons.append(
                CompetitorEntityComparison(
                    brand_id=brand_profile.brand_id,
                    competitor_id=comp_profile.brand_id,
                    dimension_scores=tuple(dim_entries),
                )
            )

        return comparisons

    def _scores_by_type(self, profile: EntityProfile) -> dict[DimensionType, Score]:
        result: dict[DimensionType, Score] = {}
        for dim in profile.dimensions:
            score = self._scoring.calculate_dimension_score(dim)
            existing = result.get(dim.dimension_type)
            if existing is None or score.value > existing.value:
                result[dim.dimension_type] = score
        return result
