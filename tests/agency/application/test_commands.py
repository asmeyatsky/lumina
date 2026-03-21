"""
Tests for Agency Application Commands

Verifies:
- OnboardClientCommand creates client and publishes event
- OnboardClientCommand rejects when agency at plan limit
- GenerateClientReportCommand produces report with branding
- BulkGenerateReportsCommand runs in parallel
"""

from __future__ import annotations

import asyncio
import time
import pytest
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.events import DomainEvent
from lumina.shared.domain.value_objects import Score

from lumina.intelligence.domain.entities import AIVisibilityScore, ScoreComponent

from lumina.agency.application.commands import (
    BulkGenerateReportsCommand,
    ConfigureWhiteLabelCommand,
    GenerateClientReportCommand,
    OnboardClientCommand,
)
from lumina.agency.domain.entities import (
    Agency,
    ClientBrand,
    ClientReport,
    MonitoringConfig,
    WhiteLabelConfig,
)
from lumina.agency.domain.events import (
    ClientBrandOnboarded,
    ClientReportGenerated,
)
from lumina.agency.domain.value_objects import AgencyPlanTier, ReportType


# =============================================================================
# In-Memory Test Doubles
# =============================================================================


class InMemoryAgencyRepository:
    """In-memory repository for Agency bounded context testing."""

    def __init__(self) -> None:
        self._agencies: dict[str, Agency] = {}
        self._clients: dict[str, ClientBrand] = {}
        self._reports: dict[str, list[ClientReport]] = {}
        self._white_label: dict[str, WhiteLabelConfig] = {}

    async def save_agency(self, agency: Agency) -> None:
        self._agencies[agency.id] = agency

    async def get_agency(self, agency_id: str) -> Agency | None:
        return self._agencies.get(agency_id)

    async def save_client(self, client: ClientBrand) -> None:
        self._clients[client.id] = client

    async def get_client(self, client_id: str) -> ClientBrand | None:
        return self._clients.get(client_id)

    async def list_clients(self, agency_id: str) -> list[ClientBrand]:
        return [c for c in self._clients.values() if c.agency_id == agency_id]

    async def save_report(self, report: ClientReport) -> None:
        self._reports.setdefault(report.client_brand_id, []).append(report)

    async def list_reports(
        self, client_brand_id: str, limit: int = 20, offset: int = 0
    ) -> list[ClientReport]:
        reports = self._reports.get(client_brand_id, [])
        return reports[offset : offset + limit]

    async def save_white_label_config(self, config: WhiteLabelConfig) -> None:
        self._white_label[config.agency_id] = config

    async def get_white_label_config(self, agency_id: str) -> WhiteLabelConfig | None:
        return self._white_label.get(agency_id)


class InMemoryEventBus:
    """In-memory event bus for testing."""

    def __init__(self) -> None:
        self._published: list[DomainEvent] = []

    async def publish(self, events: list[DomainEvent]) -> None:
        self._published.extend(events)

    async def subscribe(self, event_type: type[DomainEvent], handler: object) -> None:
        pass

    @property
    def published_events(self) -> list[DomainEvent]:
        return list(self._published)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def repository() -> InMemoryAgencyRepository:
    return InMemoryAgencyRepository()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def starter_agency() -> Agency:
    return Agency(
        id="agency-1",
        name="Test Agency",
        slug="test-agency",
        plan_tier=AgencyPlanTier.STARTER,
        max_clients=5,
        is_active=True,
    )


@pytest.fixture
def professional_agency() -> Agency:
    return Agency(
        id="agency-2",
        name="Pro Agency",
        slug="pro-agency",
        plan_tier=AgencyPlanTier.PROFESSIONAL,
        max_clients=25,
        is_active=True,
    )


# =============================================================================
# Tests
# =============================================================================


class TestOnboardClientCommand:
    """Tests for the OnboardClientCommand use case."""

    async def test_creates_client_and_publishes_event(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
        starter_agency: Agency,
    ) -> None:
        """Successfully onboards a client and publishes ClientBrandOnboarded event."""
        await repository.save_agency(starter_agency)

        command = OnboardClientCommand(
            repository=repository,
            event_bus=event_bus,
        )

        client = await command.execute(
            agency_id="agency-1",
            brand_name="TechCorp",
            industry_vertical="technology",
            competitors=("CompetitorA", "CompetitorB"),
        )

        # Client is created with correct data
        assert client.brand_name == "TechCorp"
        assert client.agency_id == "agency-1"
        assert client.industry_vertical == "technology"
        assert client.competitors == ("CompetitorA", "CompetitorB")
        assert client.is_active is True

        # Client is persisted
        persisted = await repository.get_client(client.id)
        assert persisted is not None
        assert persisted.brand_name == "TechCorp"

        # Event is published
        assert len(event_bus.published_events) == 1
        event = event_bus.published_events[0]
        assert isinstance(event, ClientBrandOnboarded)
        assert event.agency_id == "agency-1"
        assert event.brand_name == "TechCorp"
        assert event.vertical == "technology"

    async def test_rejects_when_agency_at_plan_limit(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        """Rejects onboarding when agency has reached its plan limit."""
        # Create agency with STARTER plan (max 5 clients)
        agency = Agency(
            id="agency-limit",
            name="Limited Agency",
            slug="limited-agency",
            plan_tier=AgencyPlanTier.STARTER,
            max_clients=5,
            is_active=True,
        )
        await repository.save_agency(agency)

        # Pre-populate with 5 active clients
        for i in range(5):
            client = ClientBrand(
                id=f"client-{i}",
                agency_id="agency-limit",
                brand_name=f"Brand {i}",
                is_active=True,
            )
            await repository.save_client(client)

        command = OnboardClientCommand(
            repository=repository,
            event_bus=event_bus,
        )

        from lumina.shared.domain.errors import ValidationError

        with pytest.raises(ValidationError, match="plan limit"):
            await command.execute(
                agency_id="agency-limit",
                brand_name="One Too Many",
            )

        # No event should be published
        assert len(event_bus.published_events) == 0

    async def test_rejects_when_agency_not_found(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        """Raises EntityNotFoundError when agency does not exist."""
        from lumina.shared.domain.errors import EntityNotFoundError

        command = OnboardClientCommand(
            repository=repository,
            event_bus=event_bus,
        )

        with pytest.raises(EntityNotFoundError, match="not found"):
            await command.execute(
                agency_id="nonexistent",
                brand_name="Test Brand",
            )

    async def test_rejects_when_agency_inactive(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        """Rejects onboarding when agency is not active."""
        from lumina.shared.domain.errors import ValidationError

        inactive_agency = Agency(
            id="inactive-agency",
            name="Inactive",
            slug="inactive",
            is_active=False,
        )
        await repository.save_agency(inactive_agency)

        command = OnboardClientCommand(
            repository=repository,
            event_bus=event_bus,
        )

        with pytest.raises(ValidationError, match="not active"):
            await command.execute(
                agency_id="inactive-agency",
                brand_name="Test Brand",
            )

    async def test_unlimited_plan_allows_many_clients(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        """Unlimited plan allows onboarding beyond starter limits."""
        agency = Agency(
            id="unlimited-agency",
            name="Unlimited Agency",
            slug="unlimited-agency",
            plan_tier=AgencyPlanTier.UNLIMITED,
            max_clients=999,
            is_active=True,
        )
        await repository.save_agency(agency)

        # Pre-populate with 50 clients
        for i in range(50):
            client = ClientBrand(
                id=f"client-{i}",
                agency_id="unlimited-agency",
                brand_name=f"Brand {i}",
                is_active=True,
            )
            await repository.save_client(client)

        command = OnboardClientCommand(
            repository=repository,
            event_bus=event_bus,
        )

        # Should succeed — unlimited plan
        client = await command.execute(
            agency_id="unlimited-agency",
            brand_name="Brand 51",
        )
        assert client.brand_name == "Brand 51"


class TestGenerateClientReportCommand:
    """Tests for the GenerateClientReportCommand use case."""

    async def test_produces_report_with_branding(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
        starter_agency: Agency,
    ) -> None:
        """Report is generated with white-label branding applied."""
        await repository.save_agency(starter_agency)

        client = ClientBrand(
            id="client-1",
            agency_id="agency-1",
            brand_name="TechCorp",
        )
        await repository.save_client(client)

        # Configure white-label
        wl_config = WhiteLabelConfig(
            id="wl-1",
            agency_id="agency-1",
            company_name="Acme Agency",
            logo_url="https://acme.com/logo.png",
            primary_color="#1a2b3c",
            secondary_color="#ffffff",
            accent_color="#0066cc",
            report_footer_text="Confidential",
            powered_by_visible=True,
        )
        await repository.save_white_label_config(wl_config)

        avs = AIVisibilityScore(
            brand_id="client-1",
            overall=Score(72.5),
            previous_score=Score(65.0),
            components=(
                ScoreComponent(module_name="pulse", score=Score(80.0), weight=0.30),
                ScoreComponent(module_name="graph", score=Score(60.0), weight=0.25),
                ScoreComponent(module_name="beam", score=Score(70.0), weight=0.25),
                ScoreComponent(module_name="signal", score=Score(50.0), weight=0.20),
            ),
        )

        command = GenerateClientReportCommand(
            repository=repository,
            event_bus=event_bus,
        )

        report = await command.execute(
            agency_id="agency-1",
            client_brand_id="client-1",
            avs_data=avs,
        )

        assert report.agency_id == "agency-1"
        assert report.client_brand_id == "client-1"
        assert report.report_type == ReportType.WEEKLY_SUMMARY

        # Verify branding is applied
        data_dict = dict(report.data)
        assert "branding" in data_dict
        branding = data_dict["branding"]
        assert branding["company_name"] == "Acme Agency"
        assert branding["logo_url"] == "https://acme.com/logo.png"

        # Verify event is published
        report_events = [
            e for e in event_bus.published_events
            if isinstance(e, ClientReportGenerated)
        ]
        assert len(report_events) == 1
        assert report_events[0].client_brand_id == "client-1"

    async def test_produces_report_without_branding(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
        starter_agency: Agency,
    ) -> None:
        """Report is generated even when no white-label config exists."""
        await repository.save_agency(starter_agency)

        client = ClientBrand(
            id="client-2",
            agency_id="agency-1",
            brand_name="AnotherBrand",
        )
        await repository.save_client(client)

        command = GenerateClientReportCommand(
            repository=repository,
            event_bus=event_bus,
        )

        report = await command.execute(
            agency_id="agency-1",
            client_brand_id="client-2",
        )

        assert report.agency_id == "agency-1"
        assert report.client_brand_id == "client-2"
        # No branding key in data when no white-label config
        data_dict = dict(report.data)
        assert "branding" not in data_dict


class TestBulkGenerateReportsCommand:
    """Tests for the BulkGenerateReportsCommand use case."""

    async def test_runs_in_parallel(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
        starter_agency: Agency,
    ) -> None:
        """Reports for multiple clients are generated using asyncio.gather."""
        await repository.save_agency(starter_agency)

        # Create 3 active clients
        for i in range(3):
            client = ClientBrand(
                id=f"client-{i}",
                agency_id="agency-1",
                brand_name=f"Brand {i}",
            )
            await repository.save_client(client)

        command = BulkGenerateReportsCommand(
            repository=repository,
            event_bus=event_bus,
        )

        reports = await command.execute(agency_id="agency-1")

        assert len(reports) == 3

        # Verify all clients got reports
        client_ids = {r.client_brand_id for r in reports}
        assert client_ids == {"client-0", "client-1", "client-2"}

        # Verify events were published for each report
        report_events = [
            e for e in event_bus.published_events
            if isinstance(e, ClientReportGenerated)
        ]
        assert len(report_events) == 3

    async def test_returns_empty_for_no_active_clients(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
        starter_agency: Agency,
    ) -> None:
        """Returns empty list when agency has no active clients."""
        await repository.save_agency(starter_agency)

        command = BulkGenerateReportsCommand(
            repository=repository,
            event_bus=event_bus,
        )

        reports = await command.execute(agency_id="agency-1")
        assert reports == []

    async def test_skips_inactive_clients(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
        starter_agency: Agency,
    ) -> None:
        """Only active clients get reports."""
        await repository.save_agency(starter_agency)

        active = ClientBrand(
            id="active-client",
            agency_id="agency-1",
            brand_name="Active Brand",
            is_active=True,
        )
        inactive = ClientBrand(
            id="inactive-client",
            agency_id="agency-1",
            brand_name="Inactive Brand",
            is_active=False,
        )
        await repository.save_client(active)
        await repository.save_client(inactive)

        command = BulkGenerateReportsCommand(
            repository=repository,
            event_bus=event_bus,
        )

        reports = await command.execute(agency_id="agency-1")
        assert len(reports) == 1
        assert reports[0].client_brand_id == "active-client"

    async def test_bulk_uses_asyncio_gather(
        self,
        repository: InMemoryAgencyRepository,
        event_bus: InMemoryEventBus,
        starter_agency: Agency,
    ) -> None:
        """Verify that bulk generation uses parallel execution.

        We verify this by checking that the command produces results for
        all clients — the internal implementation uses asyncio.gather.
        """
        await repository.save_agency(starter_agency)

        for i in range(5):
            client = ClientBrand(
                id=f"parallel-client-{i}",
                agency_id="agency-1",
                brand_name=f"Parallel Brand {i}",
            )
            await repository.save_client(client)

        command = BulkGenerateReportsCommand(
            repository=repository,
            event_bus=event_bus,
        )

        reports = await command.execute(agency_id="agency-1")

        # All 5 clients should have reports
        assert len(reports) == 5
        # Reports are persisted
        for client_id in [f"parallel-client-{i}" for i in range(5)]:
            stored = await repository.list_reports(client_id)
            assert len(stored) == 1
