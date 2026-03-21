"""
Tests for Agency Domain Entities

Verifies:
- Agency creation with valid data
- ClientBrand creation
- WhiteLabelConfig validation
- Entity immutability (frozen dataclasses)
"""

from __future__ import annotations

import pytest
from datetime import datetime, UTC

from lumina.shared.domain.value_objects import AIEngine

from lumina.agency.domain.entities import (
    Agency,
    ClientBrand,
    ClientReport,
    MonitoringConfig,
    WhiteLabelConfig,
)
from lumina.agency.domain.value_objects import AgencyPlanTier, ReportType


class TestAgency:
    """Tests for the Agency aggregate."""

    def test_create_agency_with_valid_data(self) -> None:
        """Agency is created successfully with valid data."""
        agency = Agency(
            id="agency-1",
            name="Acme Digital",
            slug="acme-digital",
            logo_url="https://acme.com/logo.png",
            primary_color="#1a2b3c",
            secondary_color="#ffffff",
            custom_domain="reports.acme.com",
            plan_tier=AgencyPlanTier.PROFESSIONAL,
            max_clients=25,
            is_active=True,
        )
        assert agency.id == "agency-1"
        assert agency.name == "Acme Digital"
        assert agency.slug == "acme-digital"
        assert agency.plan_tier == AgencyPlanTier.PROFESSIONAL
        assert agency.max_clients == 25
        assert agency.is_active is True
        assert agency.logo_url == "https://acme.com/logo.png"
        assert agency.custom_domain == "reports.acme.com"

    def test_create_agency_with_defaults(self) -> None:
        """Agency uses sensible defaults."""
        agency = Agency(name="Test Agency", slug="test-agency")
        assert agency.plan_tier == AgencyPlanTier.STARTER
        assert agency.max_clients == 5
        assert agency.is_active is True
        assert agency.logo_url is None
        assert agency.primary_color is None
        assert agency.custom_domain is None
        assert agency.domain_events == ()

    def test_create_agency_empty_name_raises(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="Agency name cannot be empty"):
            Agency(name="", slug="test")

    def test_create_agency_empty_slug_raises(self) -> None:
        """Empty slug raises ValueError."""
        with pytest.raises(ValueError, match="Agency slug cannot be empty"):
            Agency(name="Test", slug="")

    def test_create_agency_whitespace_name_raises(self) -> None:
        """Whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="Agency name cannot be empty"):
            Agency(name="   ", slug="test")

    def test_create_agency_negative_max_clients_raises(self) -> None:
        """Negative max_clients raises ValueError."""
        with pytest.raises(ValueError, match="max_clients must be non-negative"):
            Agency(name="Test", slug="test", max_clients=-1)

    def test_agency_is_frozen(self) -> None:
        """Agency is immutable."""
        agency = Agency(name="Test", slug="test")
        with pytest.raises(AttributeError):
            agency.name = "Changed"  # type: ignore[misc]

    def test_agency_plan_tier_max_clients(self) -> None:
        """AgencyPlanTier reports correct max_clients values."""
        assert AgencyPlanTier.STARTER.max_clients == 5
        assert AgencyPlanTier.PROFESSIONAL.max_clients == 25
        assert AgencyPlanTier.UNLIMITED.max_clients is None


class TestClientBrand:
    """Tests for the ClientBrand entity."""

    def test_create_client_brand(self) -> None:
        """ClientBrand is created successfully with valid data."""
        client = ClientBrand(
            id="client-1",
            agency_id="agency-1",
            brand_name="TechCorp",
            brand_logo_url="https://techcorp.com/logo.png",
            industry_vertical="technology",
            competitors=("CompetitorA", "CompetitorB"),
            is_active=True,
        )
        assert client.id == "client-1"
        assert client.agency_id == "agency-1"
        assert client.brand_name == "TechCorp"
        assert client.industry_vertical == "technology"
        assert client.competitors == ("CompetitorA", "CompetitorB")
        assert client.is_active is True

    def test_create_client_brand_empty_name_raises(self) -> None:
        """Empty brand_name raises ValueError."""
        with pytest.raises(ValueError, match="brand_name cannot be empty"):
            ClientBrand(agency_id="agency-1", brand_name="")

    def test_create_client_brand_empty_agency_id_raises(self) -> None:
        """Empty agency_id raises ValueError."""
        with pytest.raises(ValueError, match="agency_id cannot be empty"):
            ClientBrand(agency_id="", brand_name="Test")

    def test_client_brand_is_frozen(self) -> None:
        """ClientBrand is immutable."""
        client = ClientBrand(agency_id="agency-1", brand_name="Test")
        with pytest.raises(AttributeError):
            client.brand_name = "Changed"  # type: ignore[misc]

    def test_client_brand_default_monitoring_config(self) -> None:
        """ClientBrand uses default MonitoringConfig."""
        client = ClientBrand(agency_id="agency-1", brand_name="Test")
        assert client.monitoring_config.polling_frequency == "daily"
        assert len(client.monitoring_config.engines) == 4


class TestMonitoringConfig:
    """Tests for the MonitoringConfig value object."""

    def test_valid_frequencies(self) -> None:
        """All valid frequencies are accepted."""
        for freq in ("hourly", "daily", "weekly"):
            config = MonitoringConfig(polling_frequency=freq)
            assert config.polling_frequency == freq

    def test_invalid_frequency_raises(self) -> None:
        """Invalid frequency raises ValueError."""
        with pytest.raises(ValueError, match="polling_frequency must be one of"):
            MonitoringConfig(polling_frequency="monthly")

    def test_default_engines(self) -> None:
        """Default engines include all four AI engines."""
        config = MonitoringConfig()
        assert len(config.engines) == 4
        assert AIEngine.CLAUDE in config.engines
        assert AIEngine.GPT4O in config.engines

    def test_monitoring_config_is_frozen(self) -> None:
        """MonitoringConfig is immutable."""
        config = MonitoringConfig()
        with pytest.raises(AttributeError):
            config.polling_frequency = "weekly"  # type: ignore[misc]


class TestWhiteLabelConfig:
    """Tests for the WhiteLabelConfig entity."""

    def test_create_white_label_config(self) -> None:
        """WhiteLabelConfig is created with valid data."""
        config = WhiteLabelConfig(
            id="wl-1",
            agency_id="agency-1",
            company_name="Acme Agency",
            logo_url="https://acme.com/logo.png",
            primary_color="#1a2b3c",
            secondary_color="#ffffff",
            accent_color="#0066cc",
            custom_domain="reports.acme.com",
            email_from_name="Acme Reports",
            email_from_address="reports@acme.com",
            report_footer_text="Confidential - Acme Agency",
            powered_by_visible=False,
        )
        assert config.company_name == "Acme Agency"
        assert config.powered_by_visible is False
        assert config.custom_domain == "reports.acme.com"

    def test_white_label_config_defaults(self) -> None:
        """WhiteLabelConfig has sensible defaults."""
        config = WhiteLabelConfig()
        assert config.primary_color == "#000000"
        assert config.secondary_color == "#ffffff"
        assert config.accent_color == "#0066cc"
        assert config.powered_by_visible is True

    def test_white_label_config_is_frozen(self) -> None:
        """WhiteLabelConfig is immutable."""
        config = WhiteLabelConfig()
        with pytest.raises(AttributeError):
            config.company_name = "Changed"  # type: ignore[misc]


class TestClientReport:
    """Tests for the ClientReport entity."""

    def test_create_client_report(self) -> None:
        """ClientReport is created with valid data."""
        report = ClientReport(
            id="report-1",
            agency_id="agency-1",
            client_brand_id="client-1",
            report_type=ReportType.WEEKLY_SUMMARY,
            title="Weekly Summary",
            data=(("key", "value"),),
        )
        assert report.id == "report-1"
        assert report.report_type == ReportType.WEEKLY_SUMMARY
        assert report.data == (("key", "value"),)
        assert report.pdf_url is None

    def test_client_report_is_frozen(self) -> None:
        """ClientReport is immutable."""
        report = ClientReport(
            id="report-1",
            agency_id="agency-1",
            client_brand_id="client-1",
            title="Test",
        )
        with pytest.raises(AttributeError):
            report.title = "Changed"  # type: ignore[misc]

    def test_report_types(self) -> None:
        """All report types are valid."""
        assert ReportType.WEEKLY_SUMMARY.value == "weekly_summary"
        assert ReportType.MONTHLY_REVIEW.value == "monthly_review"
        assert ReportType.QUARTERLY_ANALYSIS.value == "quarterly_analysis"
        assert ReportType.CUSTOM.value == "custom"
