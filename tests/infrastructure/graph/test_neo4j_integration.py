"""
Neo4j Integration Tests

Tests the Neo4jGraphRepository against a live Neo4j instance.
All tests are marked with ``@pytest.mark.integration`` so they can be
excluded when no Neo4j server is available (``pytest -m "not integration"``).

Configuration:
    NEO4J_TEST_URI  — bolt URI  (default: bolt://localhost:7687)
    NEO4J_TEST_USER — username  (default: neo4j)
    NEO4J_TEST_PASS — password  (default: neo4j)
    NEO4J_TEST_DB   — database  (default: neo4j)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, UTC

import pytest
import pytest_asyncio

from neo4j import AsyncGraphDatabase, AsyncDriver

from lumina.shared.domain.value_objects import AIEngine, BrandId, Score
from lumina.graph.domain.entities import EntityDimension, EntityProfile, KnowledgeGap
from lumina.graph.domain.value_objects import DimensionType, GapSeverity
from lumina.graph.infrastructure.adapters.neo4j_adapter import Neo4jGraphRepository


NEO4J_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_TEST_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_TEST_PASS", "neo4j")
NEO4J_DB = os.environ.get("NEO4J_TEST_DB", "neo4j")

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def driver():
    """Create an async Neo4j driver for the test database."""
    drv: AsyncDriver = AsyncGraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS)
    )
    yield drv
    await drv.close()


@pytest_asyncio.fixture
async def repo(driver: AsyncDriver):
    """Create a repository and clean all test data before/after each test."""
    repository = Neo4jGraphRepository(driver, database=NEO4J_DB)

    # Teardown before — ensures a clean slate even if a previous run crashed
    await _clear_test_data(driver)

    yield repository

    # Teardown after
    await _clear_test_data(driver)


async def _clear_test_data(driver: AsyncDriver) -> None:
    """Remove all EntityProfile, EntityDimension, and KnowledgeGap nodes."""
    async with driver.session(database=NEO4J_DB) as session:
        await session.run("MATCH (d:EntityDimension) DETACH DELETE d")
        await session.run("MATCH (p:EntityProfile) DETACH DELETE p")
        await session.run("MATCH (g:KnowledgeGap) DETACH DELETE g")


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _make_profile(
    *,
    profile_id: str | None = None,
    brand_id: str = "test-brand",
    name: str = "Test Entity",
    description: str = "A test entity profile",
    dimensions: tuple[EntityDimension, ...] = (),
    health_score: float = 50.0,
) -> EntityProfile:
    now = datetime.now(UTC)
    return EntityProfile(
        id=profile_id or str(uuid.uuid4()),
        brand_id=BrandId(brand_id),
        name=name,
        description=description,
        dimensions=dimensions,
        health_score=Score(health_score),
        created_at=now,
        updated_at=now,
        domain_events=(),
    )


def _make_dimension(
    *,
    dim_id: str | None = None,
    dimension_type: DimensionType = DimensionType.IDENTITY,
    data: dict[str, str] | None = None,
    completeness: float = 75.0,
    sources: tuple[str, ...] = ("source-a",),
) -> EntityDimension:
    return EntityDimension(
        id=dim_id or str(uuid.uuid4()),
        dimension_type=dimension_type,
        data=tuple(sorted((data or {"key": "value"}).items())),
        completeness_score=Score(completeness),
        sources=sources,
        last_verified_at=datetime.now(UTC),
    )


def _make_gap(
    *,
    gap_id: str | None = None,
    brand_id: str = "test-brand",
    dimension_type: DimensionType = DimensionType.IDENTITY,
    severity: GapSeverity = GapSeverity.MEDIUM,
    description: str = "Missing identity data",
    identified_from: AIEngine | None = AIEngine.GPT4O,
    recommended_action: str = "Add structured data",
) -> KnowledgeGap:
    return KnowledgeGap(
        id=gap_id or str(uuid.uuid4()),
        brand_id=BrandId(brand_id),
        dimension_type=dimension_type,
        description=description,
        severity=severity,
        identified_from=identified_from,
        recommended_action=recommended_action,
    )


# ---------------------------------------------------------------------- #
# Profile tests
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_save_profile_creates_node(repo: Neo4jGraphRepository) -> None:
    profile = _make_profile(name="SaveTest")
    await repo.save_profile(profile)

    loaded = await repo.get_profile(profile.id)
    assert loaded is not None
    assert loaded.name == "SaveTest"
    assert loaded.brand_id.value == "test-brand"
    assert loaded.description == "A test entity profile"


@pytest.mark.asyncio
async def test_get_profile_returns_none_for_missing(repo: Neo4jGraphRepository) -> None:
    result = await repo.get_profile("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_get_profile_retrieves_with_all_dimensions(repo: Neo4jGraphRepository) -> None:
    dim_identity = _make_dimension(
        dimension_type=DimensionType.IDENTITY,
        data={"name": "Acme Corp", "founded": "2020"},
    )
    dim_products = _make_dimension(
        dimension_type=DimensionType.PRODUCTS_SERVICES,
        data={"product": "Widget Pro", "tier": "enterprise"},
        completeness=60.0,
    )
    profile = _make_profile(dimensions=(dim_identity, dim_products))
    await repo.save_profile(profile)

    loaded = await repo.get_profile(profile.id)
    assert loaded is not None
    assert len(loaded.dimensions) == 2

    dim_types = {d.dimension_type for d in loaded.dimensions}
    assert DimensionType.IDENTITY in dim_types
    assert DimensionType.PRODUCTS_SERVICES in dim_types


@pytest.mark.asyncio
async def test_save_profile_with_multiple_dimensions_creates_relationships(
    repo: Neo4jGraphRepository,
) -> None:
    dims = tuple(
        _make_dimension(
            dimension_type=dt,
            data={"info": f"data-for-{dt.value}"},
            completeness=float(i * 10 + 10),
        )
        for i, dt in enumerate(
            [DimensionType.IDENTITY, DimensionType.PEOPLE, DimensionType.ACHIEVEMENTS]
        )
    )
    profile = _make_profile(dimensions=dims)
    await repo.save_profile(profile)

    loaded = await repo.get_profile(profile.id)
    assert loaded is not None
    assert len(loaded.dimensions) == 3

    for dim in loaded.dimensions:
        assert dim.completeness_score.value > 0


@pytest.mark.asyncio
async def test_list_profiles_for_brand_returns_only_matching(
    repo: Neo4jGraphRepository,
) -> None:
    p_a = _make_profile(brand_id="brand-alpha", name="Alpha Entity")
    p_b = _make_profile(brand_id="brand-beta", name="Beta Entity")
    await repo.save_profile(p_a)
    await repo.save_profile(p_b)

    alpha_profiles = await repo.list_profiles_for_brand("brand-alpha")
    assert len(alpha_profiles) == 1
    assert alpha_profiles[0].name == "Alpha Entity"

    beta_profiles = await repo.list_profiles_for_brand("brand-beta")
    assert len(beta_profiles) == 1
    assert beta_profiles[0].name == "Beta Entity"


@pytest.mark.asyncio
async def test_update_existing_profile_via_save_twice(
    repo: Neo4jGraphRepository,
) -> None:
    profile_id = str(uuid.uuid4())
    original = _make_profile(profile_id=profile_id, name="Version 1", health_score=30.0)
    await repo.save_profile(original)

    updated = _make_profile(profile_id=profile_id, name="Version 2", health_score=80.0)
    await repo.save_profile(updated)

    loaded = await repo.get_profile(profile_id)
    assert loaded is not None
    assert loaded.name == "Version 2"
    assert loaded.health_score.value == 80.0


@pytest.mark.asyncio
async def test_round_trip_save_get_verify_all_fields(
    repo: Neo4jGraphRepository,
) -> None:
    dim = _make_dimension(
        dimension_type=DimensionType.TOPIC_AUTHORITY,
        data={"topic": "AI visibility", "strength": "high"},
        completeness=92.5,
        sources=("blog-post", "whitepaper"),
    )
    profile = _make_profile(
        brand_id="roundtrip-brand",
        name="RoundTrip Entity",
        description="Full round-trip verification",
        dimensions=(dim,),
        health_score=88.0,
    )
    await repo.save_profile(profile)

    loaded = await repo.get_profile(profile.id)
    assert loaded is not None

    # Profile fields
    assert loaded.id == profile.id
    assert loaded.brand_id.value == "roundtrip-brand"
    assert loaded.name == "RoundTrip Entity"
    assert loaded.description == "Full round-trip verification"
    assert loaded.health_score.value == 88.0

    # Dimension fields
    assert len(loaded.dimensions) == 1
    loaded_dim = loaded.dimensions[0]
    assert loaded_dim.id == dim.id
    assert loaded_dim.dimension_type == DimensionType.TOPIC_AUTHORITY
    assert loaded_dim.completeness_score.value == 92.5
    assert set(loaded_dim.sources) == {"blog-post", "whitepaper"}

    loaded_data = dict(loaded_dim.data)
    assert loaded_data["topic"] == "AI visibility"
    assert loaded_data["strength"] == "high"


@pytest.mark.asyncio
async def test_tenant_isolation_profiles_from_different_tenants_dont_leak(
    repo: Neo4jGraphRepository,
) -> None:
    """Profiles belonging to different brand_ids (acting as tenant keys)
    must not appear in each other's listings."""
    tenant_a_id = f"tenant-a-{uuid.uuid4().hex[:8]}"
    tenant_b_id = f"tenant-b-{uuid.uuid4().hex[:8]}"

    p_a1 = _make_profile(brand_id=tenant_a_id, name="Tenant A - Entity 1")
    p_a2 = _make_profile(brand_id=tenant_a_id, name="Tenant A - Entity 2")
    p_b1 = _make_profile(brand_id=tenant_b_id, name="Tenant B - Entity 1")

    await repo.save_profile(p_a1)
    await repo.save_profile(p_a2)
    await repo.save_profile(p_b1)

    a_profiles = await repo.list_profiles_for_brand(tenant_a_id)
    b_profiles = await repo.list_profiles_for_brand(tenant_b_id)

    assert len(a_profiles) == 2
    assert len(b_profiles) == 1

    a_names = {p.name for p in a_profiles}
    assert "Tenant A - Entity 1" in a_names
    assert "Tenant A - Entity 2" in a_names
    assert "Tenant B - Entity 1" not in a_names

    b_names = {p.name for p in b_profiles}
    assert "Tenant B - Entity 1" in b_names


# ---------------------------------------------------------------------- #
# Gap tests
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_save_gap_creates_gap_node(repo: Neo4jGraphRepository) -> None:
    gap = _make_gap(description="Missing product data")
    await repo.save_gap(gap)

    gaps = await repo.get_gaps_for_brand("test-brand")
    assert len(gaps) == 1
    assert gaps[0].description == "Missing product data"
    assert gaps[0].brand_id.value == "test-brand"


@pytest.mark.asyncio
async def test_get_gaps_for_brand_returns_sorted_by_severity(
    repo: Neo4jGraphRepository,
) -> None:
    brand = f"sort-brand-{uuid.uuid4().hex[:8]}"

    gap_low = _make_gap(brand_id=brand, severity=GapSeverity.LOW, description="Low gap")
    gap_critical = _make_gap(brand_id=brand, severity=GapSeverity.CRITICAL, description="Critical gap")
    gap_medium = _make_gap(brand_id=brand, severity=GapSeverity.MEDIUM, description="Medium gap")
    gap_high = _make_gap(brand_id=brand, severity=GapSeverity.HIGH, description="High gap")

    # Save in random order
    await repo.save_gap(gap_low)
    await repo.save_gap(gap_critical)
    await repo.save_gap(gap_medium)
    await repo.save_gap(gap_high)

    gaps = await repo.get_gaps_for_brand(brand)
    assert len(gaps) == 4

    severities = [g.severity for g in gaps]
    assert severities == [
        GapSeverity.CRITICAL,
        GapSeverity.HIGH,
        GapSeverity.MEDIUM,
        GapSeverity.LOW,
    ]


@pytest.mark.asyncio
async def test_save_gap_with_no_identified_from(repo: Neo4jGraphRepository) -> None:
    gap = _make_gap(identified_from=None, description="No source engine")
    await repo.save_gap(gap)

    gaps = await repo.get_gaps_for_brand("test-brand")
    matching = [g for g in gaps if g.description == "No source engine"]
    assert len(matching) == 1
    assert matching[0].identified_from is None


@pytest.mark.asyncio
async def test_gap_fields_round_trip(repo: Neo4jGraphRepository) -> None:
    brand = f"gap-rt-{uuid.uuid4().hex[:8]}"
    gap = _make_gap(
        brand_id=brand,
        dimension_type=DimensionType.COMPETITIVE_POSITION,
        severity=GapSeverity.HIGH,
        description="Competitor positioning unclear",
        identified_from=AIEngine.CLAUDE,
        recommended_action="Publish comparison content",
    )
    await repo.save_gap(gap)

    gaps = await repo.get_gaps_for_brand(brand)
    assert len(gaps) == 1

    loaded = gaps[0]
    assert loaded.id == gap.id
    assert loaded.brand_id.value == brand
    assert loaded.dimension_type == DimensionType.COMPETITIVE_POSITION
    assert loaded.severity == GapSeverity.HIGH
    assert loaded.description == "Competitor positioning unclear"
    assert loaded.identified_from == AIEngine.CLAUDE
    assert loaded.recommended_action == "Publish comparison content"
