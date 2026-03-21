"""
GRAPH Domain Service Tests

Covers:
- GapAnalysisService identifies missing dimensions and mismatches
- EntityScoringService calculates correct dimension and overall scores
- JsonLdGenerationService produces valid JSON-LD structure
- CompetitorBenchmarkService comparison logic
"""

from __future__ import annotations

from datetime import datetime, UTC, timedelta

from lumina.shared.domain.value_objects import BrandId, Score

from lumina.graph.domain.entities import EntityProfile, EntityDimension
from lumina.graph.domain.value_objects import DimensionType, GapSeverity, JsonLdDocument
from lumina.graph.domain.services import (
    GapAnalysisService,
    EntityScoringService,
    JsonLdGenerationService,
    CompetitorBenchmarkService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dim(
    dim_type: DimensionType,
    completeness: float = 80.0,
    data: dict[str, str] | None = None,
    sources: tuple[str, ...] = ("website",),
    dim_id: str | None = None,
    last_verified_at: datetime | None = None,
) -> EntityDimension:
    return EntityDimension(
        id=dim_id or f"d-{dim_type.value}",
        dimension_type=dim_type,
        data=tuple(sorted((data or {"name": "Acme"}).items())),
        completeness_score=Score(completeness),
        sources=sources,
        last_verified_at=last_verified_at or datetime.now(UTC),
    )


def _profile(
    dims: list[EntityDimension] | None = None,
    brand_id: str = "brand-1",
    name: str = "Acme Corp",
) -> EntityProfile:
    return EntityProfile(
        id="prof-1",
        brand_id=BrandId(brand_id),
        name=name,
        description="Test brand",
        dimensions=tuple(dims or []),
        health_score=Score(0.0),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# GapAnalysisService
# ---------------------------------------------------------------------------


class TestGapAnalysisService:
    def setup_method(self) -> None:
        self.service = GapAnalysisService()

    def test_identifies_missing_dimensions(self) -> None:
        # Profile has only IDENTITY, all others are missing
        profile = _profile(dims=[_dim(DimensionType.IDENTITY)])
        gaps = self.service.analyze_gaps(profile, {})

        gap_types = {g.dimension_type for g in gaps}
        # Should identify gaps for all dimension types except IDENTITY
        for dt in DimensionType:
            if dt != DimensionType.IDENTITY:
                assert dt in gap_types, f"Expected gap for {dt.value}"

    def test_critical_severity_for_missing_identity(self) -> None:
        profile = _profile(dims=[])
        gaps = self.service.analyze_gaps(profile, {})

        identity_gaps = [g for g in gaps if g.dimension_type == DimensionType.IDENTITY]
        assert len(identity_gaps) >= 1
        assert identity_gaps[0].severity == GapSeverity.CRITICAL

    def test_detects_missing_attributes_from_ai_knowledge(self) -> None:
        profile = _profile(dims=[_dim(DimensionType.IDENTITY, data={"name": "Acme"})])
        ai_knowledge = {
            "identity": {"name": "Acme", "founded": "1990", "ceo": "Jane Doe"},
        }
        gaps = self.service.analyze_gaps(profile, ai_knowledge)

        # Should detect that profile is missing "founded" and "ceo"
        attr_gaps = [
            g
            for g in gaps
            if g.dimension_type == DimensionType.IDENTITY and "attributes" in g.description
        ]
        assert len(attr_gaps) == 1
        assert "founded" in attr_gaps[0].description or "ceo" in attr_gaps[0].description

    def test_detects_value_mismatches(self) -> None:
        profile = _profile(
            dims=[_dim(DimensionType.IDENTITY, data={"name": "Acme Corp"})]
        )
        ai_knowledge = {"identity": {"name": "Acme Inc"}}
        gaps = self.service.analyze_gaps(profile, ai_knowledge)

        mismatch_gaps = [g for g in gaps if "mismatch" in g.description]
        assert len(mismatch_gaps) == 1

    def test_low_completeness_is_flagged(self) -> None:
        profile = _profile(dims=[_dim(DimensionType.IDENTITY, completeness=30.0)])
        gaps = self.service.analyze_gaps(profile, {})

        low_gaps = [
            g
            for g in gaps
            if g.dimension_type == DimensionType.IDENTITY and "completeness" in g.description
        ]
        assert len(low_gaps) == 1

    def test_no_gaps_for_complete_profile(self) -> None:
        """A profile with all dimensions present, high completeness, and matching AI data."""
        dims = [
            _dim(dt, completeness=90.0, data={"name": "Acme"})
            for dt in DimensionType
        ]
        ai_knowledge = {dt.value: {"name": "Acme"} for dt in DimensionType}
        profile = _profile(dims=dims)
        gaps = self.service.analyze_gaps(profile, ai_knowledge)

        # No missing-dimension or missing-attribute gaps; no mismatch gaps
        assert all(g.severity != GapSeverity.CRITICAL for g in gaps)


# ---------------------------------------------------------------------------
# EntityScoringService
# ---------------------------------------------------------------------------


class TestEntityScoringService:
    def setup_method(self) -> None:
        self.service = EntityScoringService()

    def test_dimension_score_with_rich_data(self) -> None:
        dim = _dim(
            DimensionType.IDENTITY,
            data={f"key{i}": f"val{i}" for i in range(10)},
            sources=("s1", "s2", "s3", "s4", "s5"),
        )
        score = self.service.calculate_dimension_score(dim)
        # 10 keys * 5 = 50, 5 sources * 5 = 25, recent = 25 => 100
        assert score.value == 100.0

    def test_dimension_score_with_minimal_data(self) -> None:
        dim = _dim(
            DimensionType.IDENTITY,
            data={"name": "X"},
            sources=(),
            last_verified_at=datetime.now(UTC) - timedelta(days=365),
        )
        score = self.service.calculate_dimension_score(dim)
        # 1 key * 5 = 5, 0 sources = 0, old = 0 => 5
        assert score.value == 5.0

    def test_dimension_score_recency_tiers(self) -> None:
        data = {f"k{i}": f"v{i}" for i in range(5)}
        sources = ("s1",)

        recent = _dim(
            DimensionType.IDENTITY,
            data=data,
            sources=sources,
            last_verified_at=datetime.now(UTC) - timedelta(days=3),
        )
        mid = _dim(
            DimensionType.IDENTITY,
            data=data,
            sources=sources,
            last_verified_at=datetime.now(UTC) - timedelta(days=20),
        )
        old = _dim(
            DimensionType.IDENTITY,
            data=data,
            sources=sources,
            last_verified_at=datetime.now(UTC) - timedelta(days=60),
        )

        s_recent = self.service.calculate_dimension_score(recent)
        s_mid = self.service.calculate_dimension_score(mid)
        s_old = self.service.calculate_dimension_score(old)

        assert s_recent.value > s_mid.value > s_old.value

    def test_overall_health_empty_profile(self) -> None:
        profile = _profile()
        health = self.service.calculate_overall_health(profile)
        assert health.overall_score.value == 0.0
        assert health.gaps_count == len(DimensionType)

    def test_overall_health_partial_profile(self) -> None:
        dims = [
            _dim(DimensionType.IDENTITY, data={f"k{i}": f"v{i}" for i in range(10)}),
            _dim(DimensionType.PEOPLE, data={f"k{i}": f"v{i}" for i in range(5)}),
        ]
        profile = _profile(dims=dims)
        health = self.service.calculate_overall_health(profile)

        assert health.overall_score.value > 0.0
        assert health.gaps_count == len(DimensionType) - 2

    def test_overall_health_full_profile(self) -> None:
        dims = [
            _dim(
                dt,
                data={f"k{i}": f"v{i}" for i in range(10)},
                sources=("s1", "s2", "s3", "s4", "s5"),
            )
            for dt in DimensionType
        ]
        profile = _profile(dims=dims)
        health = self.service.calculate_overall_health(profile)
        assert health.overall_score.value == 100.0
        assert health.gaps_count == 0


# ---------------------------------------------------------------------------
# JsonLdGenerationService
# ---------------------------------------------------------------------------


class TestJsonLdGenerationService:
    def setup_method(self) -> None:
        self.service = JsonLdGenerationService()

    def test_generates_document_per_dimension(self) -> None:
        dims = [_dim(dt) for dt in DimensionType]
        profile = _profile(dims=dims)
        docs = self.service.generate_json_ld(profile)
        assert len(docs) == len(DimensionType)

    def test_identity_produces_organization_type(self) -> None:
        dim = _dim(
            DimensionType.IDENTITY,
            data={"name": "Acme Corp", "description": "Best widgets"},
        )
        profile = _profile(dims=[dim])
        docs = self.service.generate_json_ld(profile)

        assert len(docs) == 1
        doc = docs[0]
        assert doc.type == "Organization"
        assert doc.context == "https://schema.org"

    def test_json_ld_to_dict(self) -> None:
        dim = _dim(
            DimensionType.IDENTITY,
            data={"name": "Acme", "url": "https://acme.com"},
        )
        profile = _profile(dims=[dim])
        docs = self.service.generate_json_ld(profile)
        d = docs[0].to_dict()

        assert d["@context"] == "https://schema.org"
        assert d["@type"] == "Organization"
        assert d["name"] == "Acme"
        assert d["url"] == "https://acme.com"

    def test_products_produces_product_type(self) -> None:
        dim = _dim(
            DimensionType.PRODUCTS_SERVICES,
            data={"name": "Widget Pro", "description": "A premium widget"},
        )
        profile = _profile(dims=[dim])
        docs = self.service.generate_json_ld(profile)
        assert docs[0].type == "Product"

    def test_name_fallback_from_profile(self) -> None:
        """When a dimension has no 'name' key, it should fallback to profile name."""
        dim = _dim(DimensionType.ACHIEVEMENTS, data={"award": "Best in class"})
        profile = _profile(dims=[dim], name="Acme Corp")
        docs = self.service.generate_json_ld(profile)
        d = docs[0].to_dict()
        assert d["name"] == "Acme Corp"

    def test_empty_profile_produces_no_documents(self) -> None:
        profile = _profile(dims=[])
        docs = self.service.generate_json_ld(profile)
        assert docs == []


# ---------------------------------------------------------------------------
# CompetitorBenchmarkService
# ---------------------------------------------------------------------------


class TestCompetitorBenchmarkService:
    def setup_method(self) -> None:
        self.service = CompetitorBenchmarkService()

    def test_compare_single_competitor(self) -> None:
        brand = _profile(
            dims=[_dim(DimensionType.IDENTITY, data={f"k{i}": f"v{i}" for i in range(10)})],
            brand_id="brand-1",
        )
        competitor = _profile(
            dims=[_dim(DimensionType.IDENTITY, data={"name": "Rival"})],
            brand_id="comp-1",
        )

        comparisons = self.service.compare_entities(brand, [competitor])
        assert len(comparisons) == 1
        comp = comparisons[0]
        assert comp.brand_id == BrandId("brand-1")
        assert comp.competitor_id == BrandId("comp-1")

        identity_comparison = comp.get_comparison(DimensionType.IDENTITY)
        assert identity_comparison is not None
        brand_score, comp_score = identity_comparison
        assert brand_score.value > comp_score.value

    def test_compare_multiple_competitors(self) -> None:
        brand = _profile(dims=[], brand_id="b1")
        comp1 = _profile(dims=[], brand_id="c1")
        comp2 = _profile(dims=[], brand_id="c2")

        comparisons = self.service.compare_entities(brand, [comp1, comp2])
        assert len(comparisons) == 2

    def test_missing_dimension_scores_zero(self) -> None:
        brand = _profile(
            dims=[_dim(DimensionType.IDENTITY)],
            brand_id="b1",
        )
        competitor = _profile(dims=[], brand_id="c1")

        comparisons = self.service.compare_entities(brand, [competitor])
        people_comp = comparisons[0].get_comparison(DimensionType.PEOPLE)
        assert people_comp is not None
        # Both should be zero for PEOPLE since neither has that dimension
        assert people_comp[0].value == 0.0
        assert people_comp[1].value == 0.0

    def test_all_dimension_types_covered(self) -> None:
        brand = _profile(dims=[], brand_id="b1")
        competitor = _profile(dims=[], brand_id="c1")

        comparisons = self.service.compare_entities(brand, [competitor])
        comp = comparisons[0]
        for dt in DimensionType:
            assert comp.get_comparison(dt) is not None
