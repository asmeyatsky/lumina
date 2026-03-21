"""
GRAPH Domain Entity Tests

Covers:
- EntityProfile.add_dimension creates a new profile with the dimension appended
- EntityProfile.calculate_health computes the correct score
- EntityDimension completeness scoring
- Immutability of all entities (frozen dataclasses)
"""

from __future__ import annotations

import pytest
from datetime import datetime, UTC

from lumina.shared.domain.value_objects import BrandId, Score

from lumina.graph.domain.entities import (
    EntityProfile,
    EntityDimension,
    KnowledgeGap,
    CompetitorEntityComparison,
)
from lumina.graph.domain.value_objects import DimensionType, GapSeverity
from lumina.graph.domain.events import EntityHealthChanged


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_dimension(
    dim_type: DimensionType = DimensionType.IDENTITY,
    completeness: float = 80.0,
    data: dict[str, str] | None = None,
    dim_id: str = "dim-1",
) -> EntityDimension:
    return EntityDimension(
        id=dim_id,
        dimension_type=dim_type,
        data=tuple(sorted((data or {"name": "Acme"}).items())),
        completeness_score=Score(completeness),
        sources=("website",),
        last_verified_at=datetime.now(UTC),
    )


def _make_profile(
    dimensions: tuple[EntityDimension, ...] = (),
    health: float = 0.0,
    profile_id: str = "prof-1",
) -> EntityProfile:
    return EntityProfile(
        id=profile_id,
        brand_id=BrandId("brand-1"),
        name="Acme Corp",
        description="A test brand",
        dimensions=dimensions,
        health_score=Score(health),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# EntityProfile.add_dimension
# ---------------------------------------------------------------------------


class TestAddDimension:
    def test_returns_new_profile_with_dimension_appended(self) -> None:
        profile = _make_profile()
        dim = _make_dimension()
        new_profile = profile.add_dimension(dim)

        assert len(new_profile.dimensions) == 1
        assert new_profile.dimensions[0] is dim
        # Original is untouched
        assert len(profile.dimensions) == 0

    def test_preserves_existing_dimensions(self) -> None:
        dim1 = _make_dimension(DimensionType.IDENTITY, dim_id="d1")
        dim2 = _make_dimension(DimensionType.PRODUCTS_SERVICES, dim_id="d2")
        profile = _make_profile(dimensions=(dim1,))

        new_profile = profile.add_dimension(dim2)
        assert len(new_profile.dimensions) == 2
        assert new_profile.dimensions[0] is dim1
        assert new_profile.dimensions[1] is dim2

    def test_updates_updated_at_timestamp(self) -> None:
        profile = _make_profile()
        original_updated = profile.updated_at
        dim = _make_dimension()
        new_profile = profile.add_dimension(dim)
        assert new_profile.updated_at >= original_updated

    def test_returns_different_instance(self) -> None:
        profile = _make_profile()
        new_profile = profile.add_dimension(_make_dimension())
        assert profile is not new_profile


# ---------------------------------------------------------------------------
# EntityProfile.calculate_health
# ---------------------------------------------------------------------------


class TestCalculateHealth:
    def test_empty_profile_has_zero_health(self) -> None:
        profile = _make_profile()
        result = profile.calculate_health()
        assert result.health_score.value == 0.0

    def test_single_dimension_contributes_proportionally(self) -> None:
        dim = _make_dimension(DimensionType.IDENTITY, completeness=80.0)
        profile = _make_profile(dimensions=(dim,))
        result = profile.calculate_health()

        # 80.0 / 8 dimension types = 10.0
        assert result.health_score.value == 10.0

    def test_all_dimensions_at_100_gives_100(self) -> None:
        dims = tuple(
            _make_dimension(dt, completeness=100.0, dim_id=f"d-{i}")
            for i, dt in enumerate(DimensionType)
        )
        profile = _make_profile(dimensions=dims)
        result = profile.calculate_health()
        assert result.health_score.value == 100.0

    def test_health_change_emits_event(self) -> None:
        dim = _make_dimension(DimensionType.IDENTITY, completeness=80.0)
        profile = _make_profile(dimensions=(dim,))
        result = profile.calculate_health()

        health_events = [
            e for e in result.domain_events if isinstance(e, EntityHealthChanged)
        ]
        assert len(health_events) == 1
        assert health_events[0].old_score == 0.0
        assert health_events[0].new_score == 10.0

    def test_no_event_when_health_unchanged(self) -> None:
        profile = _make_profile()  # health = 0
        result = profile.calculate_health()  # still 0, no dims
        health_events = [
            e for e in result.domain_events if isinstance(e, EntityHealthChanged)
        ]
        assert len(health_events) == 0

    def test_best_dimension_per_type_wins(self) -> None:
        """When two dimensions share a type, the higher completeness is used."""
        dim_low = _make_dimension(DimensionType.IDENTITY, completeness=20.0, dim_id="d1")
        dim_high = _make_dimension(DimensionType.IDENTITY, completeness=80.0, dim_id="d2")
        profile = _make_profile(dimensions=(dim_low, dim_high))
        result = profile.calculate_health()
        assert result.health_score.value == 10.0  # 80 / 8


# ---------------------------------------------------------------------------
# EntityProfile.update_dimension
# ---------------------------------------------------------------------------


class TestUpdateDimension:
    def test_updates_data_and_emits_event(self) -> None:
        dim = _make_dimension(data={"name": "Acme"})
        profile = _make_profile(dimensions=(dim,))

        new_profile = profile.update_dimension(
            dim.id, {"name": "Acme Inc", "url": "https://acme.com"}
        )

        updated_dim = new_profile.dimensions[0]
        assert dict(updated_dim.data)["name"] == "Acme Inc"
        assert dict(updated_dim.data)["url"] == "https://acme.com"
        assert len(new_profile.domain_events) == 1

    def test_raises_for_unknown_dimension(self) -> None:
        profile = _make_profile()
        with pytest.raises(ValueError, match="not found"):
            profile.update_dimension("nonexistent", {"x": "y"})


# ---------------------------------------------------------------------------
# EntityDimension
# ---------------------------------------------------------------------------


class TestEntityDimension:
    def test_from_dict_factory(self) -> None:
        dim = EntityDimension.from_dict(
            dimension_type=DimensionType.PRODUCTS_SERVICES,
            data={"name": "Widget", "category": "Tools"},
            completeness_score=Score(65.0),
            sources=("catalog",),
        )
        assert dim.dimension_type == DimensionType.PRODUCTS_SERVICES
        assert dim.completeness_score.value == 65.0
        assert dict(dim.data) == {"category": "Tools", "name": "Widget"}

    def test_data_as_dict(self) -> None:
        dim = _make_dimension(data={"a": "1", "b": "2"})
        assert dim.data_as_dict == {"a": "1", "b": "2"}


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_entity_profile_is_frozen(self) -> None:
        profile = _make_profile()
        with pytest.raises(AttributeError):
            profile.name = "Changed"  # type: ignore[misc]

    def test_entity_dimension_is_frozen(self) -> None:
        dim = _make_dimension()
        with pytest.raises(AttributeError):
            dim.completeness_score = Score(99.0)  # type: ignore[misc]

    def test_knowledge_gap_is_frozen(self) -> None:
        gap = KnowledgeGap(
            id="g1",
            brand_id=BrandId("b1"),
            dimension_type=DimensionType.IDENTITY,
            description="Missing",
            severity=GapSeverity.HIGH,
        )
        with pytest.raises(AttributeError):
            gap.severity = GapSeverity.LOW  # type: ignore[misc]

    def test_competitor_comparison_is_frozen(self) -> None:
        comp = CompetitorEntityComparison(
            brand_id=BrandId("b1"),
            competitor_id=BrandId("b2"),
            dimension_scores=(),
        )
        with pytest.raises(AttributeError):
            comp.brand_id = BrandId("b3")  # type: ignore[misc]
