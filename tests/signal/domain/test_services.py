"""
Tests for SIGNAL domain services.

Validates surface prioritization, coverage calculation,
PR brief generation, and surface mapping logic.
"""

from __future__ import annotations

from datetime import datetime, UTC

import pytest

from lumina.shared.domain.value_objects import BrandId, Percentage, Score, URL

from lumina.signal.domain.entities import (
    CitationSurface,
    DistributionAction,
    DistributionPlan,
)
from lumina.signal.domain.services import (
    CoverageCalculationService,
    PRBriefGenerationService,
    SurfaceMappingService,
    SurfacePrioritizationService,
)
from lumina.signal.domain.value_objects import (
    ActionStatus,
    ActionType,
    PresenceStatus,
    SurfaceCategory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_surface(
    *,
    id: str = "s-1",
    name: str = "Surface",
    category: SurfaceCategory = SurfaceCategory.AUTHORITY_PUBLICATIONS,
    weight: float = 50.0,
    presence: PresenceStatus = PresenceStatus.ABSENT,
) -> CitationSurface:
    return CitationSurface(
        id=id,
        name=name,
        category=category,
        url=URL("https://example.com"),
        estimated_llm_weight=Score(weight),
        brand_presence=presence,
        last_checked_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# SurfacePrioritizationService
# ---------------------------------------------------------------------------


class TestSurfacePrioritizationService:
    def test_ranks_absent_surfaces_higher_than_present(self) -> None:
        service = SurfacePrioritizationService()
        absent = _make_surface(id="absent", weight=50.0, presence=PresenceStatus.ABSENT)
        present = _make_surface(id="present", weight=50.0, presence=PresenceStatus.PRESENT)

        result = service.prioritize_surfaces([present, absent], brand_gaps=[])

        assert result[0].id == "absent"
        assert result[1].id == "present"

    def test_ranks_higher_weight_surfaces_first(self) -> None:
        service = SurfacePrioritizationService()
        low = _make_surface(id="low", weight=30.0, presence=PresenceStatus.ABSENT)
        high = _make_surface(id="high", weight=90.0, presence=PresenceStatus.ABSENT)

        result = service.prioritize_surfaces([low, high], brand_gaps=[])

        assert result[0].id == "high"

    def test_gap_boost_increases_priority(self) -> None:
        service = SurfacePrioritizationService()
        s1 = _make_surface(id="s-1", weight=60.0, presence=PresenceStatus.ABSENT)
        s2 = _make_surface(id="s-2", weight=60.0, presence=PresenceStatus.ABSENT)

        # s-2 is in brand_gaps, gets 1.5x boost
        result = service.prioritize_surfaces([s1, s2], brand_gaps=["s-2"])

        assert result[0].id == "s-2"

    def test_empty_surfaces_returns_empty(self) -> None:
        service = SurfacePrioritizationService()
        result = service.prioritize_surfaces([], brand_gaps=[])
        assert result == []

    def test_weight_times_gap_ordering(self) -> None:
        service = SurfacePrioritizationService()
        # high weight but present: 80 * 0.1 = 8
        high_present = _make_surface(id="hp", weight=80.0, presence=PresenceStatus.PRESENT)
        # low weight but absent: 20 * 1.0 = 20
        low_absent = _make_surface(id="la", weight=20.0, presence=PresenceStatus.ABSENT)

        result = service.prioritize_surfaces([high_present, low_absent], brand_gaps=[])

        assert result[0].id == "la"  # 20 > 8


# ---------------------------------------------------------------------------
# CoverageCalculationService
# ---------------------------------------------------------------------------


class TestCoverageCalculationService:
    def test_computes_zero_for_empty_plan(self) -> None:
        service = CoverageCalculationService()
        plan = DistributionPlan(
            id="p-1",
            brand_id=BrandId("brand-1"),
        )

        coverage = service.calculate_coverage(plan)

        assert coverage.total_surfaces == 0
        assert coverage.surfaces_with_presence == 0
        assert coverage.coverage_percentage.value == 0.0

    def test_computes_partial_coverage(self) -> None:
        service = CoverageCalculationService()
        s1 = _make_surface(id="s-1", presence=PresenceStatus.PRESENT,
                           category=SurfaceCategory.STRUCTURED_DATA)
        s2 = _make_surface(id="s-2", presence=PresenceStatus.ABSENT,
                           category=SurfaceCategory.QA_PLATFORMS)
        s3 = _make_surface(id="s-3", presence=PresenceStatus.PARTIAL,
                           category=SurfaceCategory.STRUCTURED_DATA)

        plan = DistributionPlan(
            id="p-1",
            brand_id=BrandId("brand-1"),
            target_surfaces=(s1, s2, s3),
        )

        coverage = service.calculate_coverage(plan)

        assert coverage.total_surfaces == 3
        assert coverage.surfaces_with_presence == 2  # PRESENT + PARTIAL
        assert coverage.coverage_percentage.value == pytest.approx(66.67)

    def test_computes_full_coverage(self) -> None:
        service = CoverageCalculationService()
        s1 = _make_surface(id="s-1", presence=PresenceStatus.PRESENT)
        s2 = _make_surface(id="s-2", presence=PresenceStatus.PRESENT)

        plan = DistributionPlan(
            id="p-1",
            brand_id=BrandId("brand-1"),
            target_surfaces=(s1, s2),
        )

        coverage = service.calculate_coverage(plan)

        assert coverage.coverage_percentage.value == 100.0

    def test_per_category_breakdown(self) -> None:
        service = CoverageCalculationService()
        s1 = _make_surface(id="s-1", presence=PresenceStatus.PRESENT,
                           category=SurfaceCategory.STRUCTURED_DATA)
        s2 = _make_surface(id="s-2", presence=PresenceStatus.ABSENT,
                           category=SurfaceCategory.STRUCTURED_DATA)
        s3 = _make_surface(id="s-3", presence=PresenceStatus.PRESENT,
                           category=SurfaceCategory.QA_PLATFORMS)

        plan = DistributionPlan(
            id="p-1",
            brand_id=BrandId("brand-1"),
            target_surfaces=(s1, s2, s3),
        )

        coverage = service.calculate_coverage(plan)

        structured = coverage.get_category_coverage(SurfaceCategory.STRUCTURED_DATA)
        qa = coverage.get_category_coverage(SurfaceCategory.QA_PLATFORMS)

        assert structured is not None
        assert structured.value == 50.0  # 1 out of 2
        assert qa is not None
        assert qa.value == 100.0  # 1 out of 1


# ---------------------------------------------------------------------------
# PRBriefGenerationService
# ---------------------------------------------------------------------------


class TestPRBriefGenerationService:
    def test_creates_complete_brief(self) -> None:
        service = PRBriefGenerationService()
        entity_data = {
            "brand_id": "acme-corp",
            "industry": "technology",
            "key_products": "Widget Pro, Widget Lite",
            "achievements": "Winner of Tech Award 2025",
            "leadership": "Jane Doe, CEO",
        }

        brief = service.generate_brief("Acme Corp", entity_data, "Innovation Leader")

        assert brief.brand_id.value == "acme-corp"
        assert "Acme Corp" in brief.headline
        assert "Innovation Leader" in brief.headline
        assert brief.narrative_angle == "Innovation Leader"
        assert len(brief.key_messages) >= 1
        assert len(brief.target_publications) >= 1
        assert "Acme Corp" in brief.entity_anchors

    def test_includes_technology_publications_for_tech_industry(self) -> None:
        service = PRBriefGenerationService()
        entity_data = {"industry": "technology", "brand_id": "techco"}

        brief = service.generate_brief("TechCo", entity_data, "AI Pioneer")

        assert "TechCrunch" in brief.target_publications

    def test_includes_entity_anchors_from_products(self) -> None:
        service = PRBriefGenerationService()
        entity_data = {
            "brand_id": "test",
            "key_products": "Alpha, Beta",
        }

        brief = service.generate_brief("TestBrand", entity_data, "Market Leader")

        assert "Alpha" in brief.entity_anchors
        assert "Beta" in brief.entity_anchors

    def test_fallback_publications_for_unknown_industry(self) -> None:
        service = PRBriefGenerationService()
        entity_data = {"brand_id": "test", "industry": "underwater_basket_weaving"}

        brief = service.generate_brief("Test", entity_data, "Niche Expert")

        assert len(brief.target_publications) > 0
        assert "Forbes" in brief.target_publications


# ---------------------------------------------------------------------------
# SurfaceMappingService
# ---------------------------------------------------------------------------


class TestSurfaceMappingService:
    def test_returns_technology_surfaces(self) -> None:
        service = SurfaceMappingService()
        surfaces = service.map_surfaces_for_brand("technology")

        assert len(surfaces) > 0
        names = [s.name for s in surfaces]
        assert "Wikipedia" in names
        assert "GitHub" in names
        assert "Stack Overflow" in names

    def test_returns_healthcare_surfaces(self) -> None:
        service = SurfaceMappingService()
        surfaces = service.map_surfaces_for_brand("healthcare")

        names = [s.name for s in surfaces]
        assert "PubMed" in names
        assert "Wikipedia" in names

    def test_falls_back_to_general_for_unknown_vertical(self) -> None:
        service = SurfaceMappingService()
        surfaces = service.map_surfaces_for_brand("obscure_industry")

        assert len(surfaces) > 0
        names = [s.name for s in surfaces]
        assert "Wikipedia" in names

    def test_all_surfaces_have_unknown_presence(self) -> None:
        service = SurfaceMappingService()
        surfaces = service.map_surfaces_for_brand("technology")

        for surface in surfaces:
            assert surface.brand_presence == PresenceStatus.UNKNOWN

    def test_surfaces_have_valid_urls(self) -> None:
        service = SurfaceMappingService()
        surfaces = service.map_surfaces_for_brand("finance")

        for surface in surfaces:
            assert surface.url.value.startswith("https://")

    def test_surfaces_have_unique_ids(self) -> None:
        service = SurfaceMappingService()
        surfaces = service.map_surfaces_for_brand("technology")
        ids = [s.id for s in surfaces]
        assert len(ids) == len(set(ids))
