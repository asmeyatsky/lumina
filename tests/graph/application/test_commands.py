"""
GRAPH Application Command Tests

Covers:
- CreateEntityProfileCommand creates and saves a profile
- RunGapAnalysisCommand identifies gaps and publishes events
- GenerateJsonLdCommand produces valid documents

All ports are mocked — no infrastructure dependencies.
"""

from __future__ import annotations

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock

from lumina.shared.domain.value_objects import BrandId, Score
from lumina.shared.domain.errors import EntityNotFoundError

from lumina.graph.domain.entities import EntityProfile, EntityDimension
from lumina.graph.domain.events import (
    EntityProfileCreated,
    KnowledgeGapIdentified,
)
from lumina.graph.domain.value_objects import DimensionType
from lumina.graph.application.commands import (
    CreateEntityProfileCommand,
    DimensionInput,
    RunGapAnalysisCommand,
    GenerateJsonLdCommand,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save_profile = AsyncMock()
    repo.get_profile = AsyncMock(return_value=None)
    repo.save_gap = AsyncMock()
    return repo


def _make_mock_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


def _stored_profile(
    profile_id: str = "prof-1",
    brand_id: str = "brand-1",
    dims: tuple[EntityDimension, ...] = (),
) -> EntityProfile:
    return EntityProfile(
        id=profile_id,
        brand_id=BrandId(brand_id),
        name="Acme Corp",
        description="A test brand",
        dimensions=dims,
        health_score=Score(0.0),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# CreateEntityProfileCommand
# ---------------------------------------------------------------------------


class TestCreateEntityProfileCommand:
    @pytest.mark.asyncio
    async def test_creates_and_saves_profile(self) -> None:
        repo = _make_mock_repo()
        bus = _make_mock_event_bus()
        cmd = CreateEntityProfileCommand(repo, bus)

        profile = await cmd.execute(
            brand_id="brand-1",
            name="Acme Corp",
            description="Best widgets in the west",
        )

        assert profile.name == "Acme Corp"
        assert profile.brand_id == BrandId("brand-1")
        repo.save_profile.assert_awaited_once()
        bus.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publishes_entity_profile_created_event(self) -> None:
        repo = _make_mock_repo()
        bus = _make_mock_event_bus()
        cmd = CreateEntityProfileCommand(repo, bus)

        await cmd.execute(
            brand_id="brand-1",
            name="Acme",
            description="Test",
        )

        published_events = bus.publish.call_args[0][0]
        created_events = [e for e in published_events if isinstance(e, EntityProfileCreated)]
        assert len(created_events) >= 1
        assert created_events[0].brand_id == "brand-1"
        assert created_events[0].profile_name == "Acme"

    @pytest.mark.asyncio
    async def test_creates_with_initial_dimensions(self) -> None:
        repo = _make_mock_repo()
        bus = _make_mock_event_bus()
        cmd = CreateEntityProfileCommand(repo, bus)

        dims = [
            DimensionInput(
                dimension_type=DimensionType.IDENTITY,
                data={"name": "Acme"},
                completeness_score=75.0,
                sources=("website",),
            ),
            DimensionInput(
                dimension_type=DimensionType.PRODUCTS_SERVICES,
                data={"name": "Widget"},
                completeness_score=50.0,
            ),
        ]

        profile = await cmd.execute(
            brand_id="brand-1",
            name="Acme",
            description="Test",
            dimensions=dims,
        )

        assert len(profile.dimensions) == 2
        assert profile.dimensions[0].dimension_type == DimensionType.IDENTITY
        assert profile.dimensions[1].dimension_type == DimensionType.PRODUCTS_SERVICES

    @pytest.mark.asyncio
    async def test_calculates_health_from_initial_dimensions(self) -> None:
        repo = _make_mock_repo()
        bus = _make_mock_event_bus()
        cmd = CreateEntityProfileCommand(repo, bus)

        dims = [
            DimensionInput(
                dimension_type=DimensionType.IDENTITY,
                data={"name": "Acme"},
                completeness_score=80.0,
            ),
        ]

        profile = await cmd.execute(
            brand_id="brand-1",
            name="Acme",
            description="Test",
            dimensions=dims,
        )

        # Health should be > 0 since we have one dimension
        assert profile.health_score.value == 10.0  # 80 / 8

    @pytest.mark.asyncio
    async def test_returned_profile_has_cleared_events(self) -> None:
        repo = _make_mock_repo()
        bus = _make_mock_event_bus()
        cmd = CreateEntityProfileCommand(repo, bus)

        profile = await cmd.execute(
            brand_id="brand-1", name="Acme", description="Test"
        )

        assert len(profile.domain_events) == 0


# ---------------------------------------------------------------------------
# RunGapAnalysisCommand
# ---------------------------------------------------------------------------


class TestRunGapAnalysisCommand:
    @pytest.mark.asyncio
    async def test_identifies_gaps_and_saves_them(self) -> None:
        repo = _make_mock_repo()
        bus = _make_mock_event_bus()
        stored = _stored_profile(
            dims=(
                EntityDimension(
                    id="d1",
                    dimension_type=DimensionType.IDENTITY,
                    data=(("name", "Acme"),),
                    completeness_score=Score(80.0),
                    sources=("website",),
                    last_verified_at=datetime.now(UTC),
                ),
            ),
        )
        repo.get_profile.return_value = stored

        cmd = RunGapAnalysisCommand(repo, bus)
        gaps = await cmd.execute(
            profile_id="prof-1",
            ai_knowledge={"identity": {"name": "Acme"}},
        )

        # At least gaps for missing dimension types
        assert len(gaps) >= 7  # 8 types - 1 present = 7 missing
        # All gaps should be saved
        assert repo.save_gap.await_count == len(gaps)

    @pytest.mark.asyncio
    async def test_publishes_gap_identified_events(self) -> None:
        repo = _make_mock_repo()
        bus = _make_mock_event_bus()
        stored = _stored_profile(
            dims=(
                EntityDimension(
                    id="d1",
                    dimension_type=DimensionType.IDENTITY,
                    data=(("name", "Acme"),),
                    completeness_score=Score(80.0),
                    sources=("website",),
                    last_verified_at=datetime.now(UTC),
                ),
            ),
        )
        repo.get_profile.return_value = stored

        cmd = RunGapAnalysisCommand(repo, bus)
        gaps = await cmd.execute(
            profile_id="prof-1",
            ai_knowledge={},
        )

        bus.publish.assert_awaited_once()
        published = bus.publish.call_args[0][0]
        gap_events = [e for e in published if isinstance(e, KnowledgeGapIdentified)]
        assert len(gap_events) == len(gaps)

    @pytest.mark.asyncio
    async def test_raises_when_profile_not_found(self) -> None:
        repo = _make_mock_repo()
        bus = _make_mock_event_bus()
        repo.get_profile.return_value = None

        cmd = RunGapAnalysisCommand(repo, bus)
        with pytest.raises(EntityNotFoundError):
            await cmd.execute(profile_id="nonexistent", ai_knowledge={})


# ---------------------------------------------------------------------------
# GenerateJsonLdCommand
# ---------------------------------------------------------------------------


class TestGenerateJsonLdCommand:
    @pytest.mark.asyncio
    async def test_produces_valid_documents(self) -> None:
        repo = _make_mock_repo()
        stored = _stored_profile(
            dims=(
                EntityDimension(
                    id="d1",
                    dimension_type=DimensionType.IDENTITY,
                    data=(("name", "Acme"), ("description", "Best widgets")),
                    completeness_score=Score(80.0),
                    sources=("website",),
                    last_verified_at=datetime.now(UTC),
                ),
                EntityDimension(
                    id="d2",
                    dimension_type=DimensionType.PRODUCTS_SERVICES,
                    data=(("name", "Widget Pro"),),
                    completeness_score=Score(60.0),
                    sources=("catalog",),
                    last_verified_at=datetime.now(UTC),
                ),
            ),
        )
        repo.get_profile.return_value = stored

        cmd = GenerateJsonLdCommand(repo)
        docs = await cmd.execute(profile_id="prof-1")

        assert len(docs) == 2

        # Verify JSON-LD structure
        org_doc = next(d for d in docs if d.type == "Organization")
        assert org_doc.context == "https://schema.org"
        d = org_doc.to_dict()
        assert d["@type"] == "Organization"
        assert d["name"] == "Acme"

        prod_doc = next(d for d in docs if d.type == "Product")
        assert prod_doc.context == "https://schema.org"

    @pytest.mark.asyncio
    async def test_raises_when_profile_not_found(self) -> None:
        repo = _make_mock_repo()
        repo.get_profile.return_value = None

        cmd = GenerateJsonLdCommand(repo)
        with pytest.raises(EntityNotFoundError):
            await cmd.execute(profile_id="nonexistent")

    @pytest.mark.asyncio
    async def test_empty_profile_returns_no_documents(self) -> None:
        repo = _make_mock_repo()
        repo.get_profile.return_value = _stored_profile()

        cmd = GenerateJsonLdCommand(repo)
        docs = await cmd.execute(profile_id="prof-1")
        assert docs == []
