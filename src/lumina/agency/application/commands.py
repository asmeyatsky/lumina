"""
Agency Application Commands (Use Cases)

Architectural Intent:
- Commands orchestrate domain logic and infrastructure interactions
- Each command represents a single write-side use case
- Domain events are published after successful persistence
- Bulk operations use asyncio.gather for parallelism
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.errors import EntityNotFoundError, ValidationError
from lumina.shared.domain.value_objects import BrandId, Score
from lumina.shared.ports.event_bus import EventBusPort

from lumina.intelligence.domain.entities import AIVisibilityScore, Recommendation

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
    WhiteLabelConfigured,
)
from lumina.agency.domain.ports import AgencyRepositoryPort, ReportExportPort
from lumina.agency.domain.services import (
    ReportGenerationService,
    WhiteLabelService,
)
from lumina.agency.domain.value_objects import ReportType


@dataclass(frozen=True)
class OnboardClientCommand:
    """Create a new client brand under an agency.

    Validates agency plan limits and sets up monitoring configuration.
    """

    repository: AgencyRepositoryPort
    event_bus: EventBusPort

    async def execute(
        self,
        agency_id: str,
        brand_name: str,
        industry_vertical: str = "",
        competitors: tuple[str, ...] = (),
        monitoring_config: MonitoringConfig | None = None,
    ) -> ClientBrand:
        """Execute client onboarding.

        Args:
            agency_id: The agency to onboard the client under.
            brand_name: The client brand name.
            industry_vertical: The industry vertical.
            competitors: Tuple of competitor brand names.
            monitoring_config: Optional monitoring configuration.

        Returns:
            The created ClientBrand entity.

        Raises:
            EntityNotFoundError: If the agency does not exist.
            ValidationError: If the agency is at its plan limit.
        """
        agency = await self.repository.get_agency(agency_id)
        if agency is None:
            raise EntityNotFoundError(f"Agency {agency_id} not found")

        if not agency.is_active:
            raise ValidationError(f"Agency {agency_id} is not active")

        # Check plan limits
        existing_clients = await self.repository.list_clients(agency_id)
        active_clients = [c for c in existing_clients if c.is_active]

        plan_limit = agency.plan_tier.max_clients
        if plan_limit is not None and len(active_clients) >= plan_limit:
            raise ValidationError(
                f"Agency has reached its {agency.plan_tier.value} plan limit "
                f"of {plan_limit} clients. "
                f"Upgrade to add more clients."
            )

        config = monitoring_config or MonitoringConfig()

        client = ClientBrand(
            id=str(uuid4()),
            agency_id=agency_id,
            brand_name=brand_name,
            industry_vertical=industry_vertical,
            competitors=competitors,
            monitoring_config=config,
            created_at=datetime.now(UTC),
            is_active=True,
        )

        await self.repository.save_client(client)

        event = ClientBrandOnboarded(
            aggregate_id=client.id,
            agency_id=agency_id,
            brand_name=brand_name,
            vertical=industry_vertical,
        )
        await self.event_bus.publish([event])

        return client


@dataclass(frozen=True)
class ConfigureWhiteLabelCommand:
    """Save white-label configuration for an agency."""

    repository: AgencyRepositoryPort
    event_bus: EventBusPort

    async def execute(
        self,
        agency_id: str,
        company_name: str,
        logo_url: str,
        primary_color: str = "#000000",
        secondary_color: str = "#ffffff",
        accent_color: str = "#0066cc",
        custom_domain: str | None = None,
        email_from_name: str = "",
        email_from_address: str = "",
        report_footer_text: str = "",
        powered_by_visible: bool = True,
    ) -> WhiteLabelConfig:
        """Execute white-label configuration.

        Args:
            agency_id: The agency to configure.
            company_name: Display name for branding.
            logo_url: URL to the agency logo.
            primary_color: Primary brand colour.
            secondary_color: Secondary brand colour.
            accent_color: Accent colour.
            custom_domain: Optional custom domain.
            email_from_name: Display name in outbound emails.
            email_from_address: From address in outbound emails.
            report_footer_text: Custom footer text.
            powered_by_visible: Whether to show 'Powered by LUMINA'.

        Returns:
            The saved WhiteLabelConfig entity.

        Raises:
            EntityNotFoundError: If the agency does not exist.
            ValidationError: If the configuration is invalid.
        """
        agency = await self.repository.get_agency(agency_id)
        if agency is None:
            raise EntityNotFoundError(f"Agency {agency_id} not found")

        config = WhiteLabelConfig(
            id=str(uuid4()),
            agency_id=agency_id,
            company_name=company_name,
            logo_url=logo_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            accent_color=accent_color,
            custom_domain=custom_domain,
            email_from_name=email_from_name,
            email_from_address=email_from_address,
            report_footer_text=report_footer_text,
            powered_by_visible=powered_by_visible,
        )

        # Validate configuration
        errors = WhiteLabelService.validate_config(config)
        if errors:
            raise ValidationError(
                f"White-label configuration is invalid: {'; '.join(errors)}"
            )

        await self.repository.save_white_label_config(config)

        event = WhiteLabelConfigured(
            aggregate_id=config.id,
            agency_id=agency_id,
            custom_domain=custom_domain,
        )
        await self.event_bus.publish([event])

        return config


@dataclass(frozen=True)
class GenerateClientReportCommand:
    """Generate a report for a specific client with white-label branding applied."""

    repository: AgencyRepositoryPort
    event_bus: EventBusPort

    async def execute(
        self,
        agency_id: str,
        client_brand_id: str,
        report_type: ReportType = ReportType.WEEKLY_SUMMARY,
        avs_data: AIVisibilityScore | None = None,
        citation_data: dict[str, object] | None = None,
        recommendations: list[Recommendation] | None = None,
        avs_history: list[AIVisibilityScore] | None = None,
        content_scores: list[dict[str, object]] | None = None,
        distribution_coverage: dict[str, object] | None = None,
    ) -> ClientReport:
        """Execute report generation for a single client.

        Args:
            agency_id: The owning agency.
            client_brand_id: The client brand to report on.
            report_type: The type of report to generate.
            avs_data: Current AVS data (for weekly).
            citation_data: Citation data from PULSE (for weekly).
            recommendations: Recommendations from Intelligence Engine (for weekly).
            avs_history: Historical AVS data (for monthly).
            content_scores: Content scores from BEAM (for monthly).
            distribution_coverage: Coverage from SIGNAL (for monthly).

        Returns:
            The generated ClientReport entity with branding applied.

        Raises:
            EntityNotFoundError: If the agency or client does not exist.
        """
        agency = await self.repository.get_agency(agency_id)
        if agency is None:
            raise EntityNotFoundError(f"Agency {agency_id} not found")

        client = await self.repository.get_client(client_brand_id)
        if client is None:
            raise EntityNotFoundError(
                f"Client brand {client_brand_id} not found"
            )

        # Generate the report using the domain service
        if report_type == ReportType.WEEKLY_SUMMARY:
            default_avs = avs_data or AIVisibilityScore(
                brand_id=client_brand_id, overall=Score(0.0)
            )
            report = ReportGenerationService.generate_weekly_summary(
                brand_id=client_brand_id,
                avs_data=default_avs,
                citation_data=citation_data or {},
                recommendations=recommendations or [],
                agency_id=agency_id,
            )
        elif report_type == ReportType.MONTHLY_REVIEW:
            report = ReportGenerationService.generate_monthly_review(
                brand_id=client_brand_id,
                avs_history=avs_history or [],
                content_scores=content_scores or [],
                distribution_coverage=distribution_coverage or {},
                agency_id=agency_id,
            )
        else:
            # Custom or quarterly — generate a basic report structure
            report = ClientReport(
                id=str(uuid4()),
                agency_id=agency_id,
                client_brand_id=client_brand_id,
                report_type=report_type,
                title=f"{report_type.value.replace('_', ' ').title()} — "
                      f"{datetime.now(UTC).strftime('%B %d, %Y')}",
                generated_at=datetime.now(UTC),
                data=(),
            )

        # Apply white-label branding if configured
        branding = await self.repository.get_white_label_config(agency_id)
        if branding is not None:
            branded_data = WhiteLabelService.apply_branding(
                dict(report.data), branding
            )
            from dataclasses import replace
            report = replace(
                report,
                data=tuple(branded_data.items()),
            )

        await self.repository.save_report(report)

        event = ClientReportGenerated(
            aggregate_id=report.id,
            agency_id=agency_id,
            client_brand_id=client_brand_id,
            report_type=report_type.value,
        )
        await self.event_bus.publish([event])

        return report


@dataclass(frozen=True)
class BulkGenerateReportsCommand:
    """Generate reports for all active clients of an agency in parallel."""

    repository: AgencyRepositoryPort
    event_bus: EventBusPort

    async def execute(
        self,
        agency_id: str,
        report_type: ReportType = ReportType.WEEKLY_SUMMARY,
        client_avs_data: dict[str, AIVisibilityScore] | None = None,
        client_citation_data: dict[str, dict[str, object]] | None = None,
        client_recommendations: dict[str, list[Recommendation]] | None = None,
    ) -> list[ClientReport]:
        """Execute bulk report generation for all active clients.

        Args:
            agency_id: The agency to generate reports for.
            report_type: The type of report to generate.
            client_avs_data: Mapping of client_brand_id to AVS data.
            client_citation_data: Mapping of client_brand_id to citation data.
            client_recommendations: Mapping of client_brand_id to recommendations.

        Returns:
            List of generated ClientReport entities.

        Raises:
            EntityNotFoundError: If the agency does not exist.
        """
        agency = await self.repository.get_agency(agency_id)
        if agency is None:
            raise EntityNotFoundError(f"Agency {agency_id} not found")

        clients = await self.repository.list_clients(agency_id)
        active_clients = [c for c in clients if c.is_active]

        if not active_clients:
            return []

        avs_map = client_avs_data or {}
        citation_map = client_citation_data or {}
        rec_map = client_recommendations or {}

        generate_cmd = GenerateClientReportCommand(
            repository=self.repository,
            event_bus=self.event_bus,
        )

        # Generate reports in parallel using asyncio.gather
        tasks = [
            generate_cmd.execute(
                agency_id=agency_id,
                client_brand_id=client.id,
                report_type=report_type,
                avs_data=avs_map.get(client.id),
                citation_data=citation_map.get(client.id),
                recommendations=rec_map.get(client.id),
            )
            for client in active_clients
        ]

        reports = await asyncio.gather(*tasks)
        return list(reports)
