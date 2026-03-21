"""
Agency Domain Entities

Architectural Intent:
- Frozen dataclasses enforce immutability (DDD aggregate invariant protection)
- Domain events are collected as tuples (immutable collections)
- All mutations produce new instances via dataclasses.replace()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.events import DomainEvent
from lumina.shared.domain.value_objects import AIEngine

from lumina.agency.domain.value_objects import AgencyPlanTier, ReportType


@dataclass(frozen=True)
class MonitoringConfig:
    """Configuration for how a client brand is monitored across AI engines.

    Attributes:
        engines: Tuple of AI engines to monitor.
        prompt_battery_id: Optional prompt battery to use for monitoring.
        polling_frequency: How often to poll — 'hourly', 'daily', or 'weekly'.
        alert_channels: Tuple of notification channels (e.g. 'email', 'slack').
    """

    engines: tuple[AIEngine, ...] = (
        AIEngine.CLAUDE,
        AIEngine.GPT4O,
        AIEngine.GEMINI,
        AIEngine.PERPLEXITY,
    )
    prompt_battery_id: str | None = None
    polling_frequency: str = "daily"
    alert_channels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        valid_frequencies = ("hourly", "daily", "weekly")
        if self.polling_frequency not in valid_frequencies:
            raise ValueError(
                f"polling_frequency must be one of {valid_frequencies}, "
                f"got '{self.polling_frequency}'"
            )


@dataclass(frozen=True)
class Agency:
    """Aggregate root for an agency that manages multiple client brands.

    Attributes:
        id: Unique agency identifier.
        name: Display name of the agency.
        slug: URL-safe slug for the agency.
        logo_url: Optional URL to the agency logo.
        primary_color: Optional primary brand colour (hex).
        secondary_color: Optional secondary brand colour (hex).
        custom_domain: Optional custom domain for white-label access.
        plan_tier: The agency's subscription plan tier.
        max_clients: Maximum number of clients allowed under this plan.
        is_active: Whether the agency account is active.
        created_at: When the agency was created.
        domain_events: Collected domain events for this aggregate.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    slug: str = ""
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    custom_domain: str | None = None
    plan_tier: AgencyPlanTier = AgencyPlanTier.STARTER
    max_clients: int = 5
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    domain_events: tuple[DomainEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Agency name cannot be empty")
        if not self.slug or not self.slug.strip():
            raise ValueError("Agency slug cannot be empty")
        if self.max_clients < 0:
            raise ValueError(
                f"max_clients must be non-negative, got {self.max_clients}"
            )


@dataclass(frozen=True)
class ClientBrand:
    """A client brand managed by an agency.

    Attributes:
        id: Unique client brand identifier.
        agency_id: The owning agency's identifier.
        brand_name: Display name of the client brand.
        brand_logo_url: Optional URL to the client brand logo.
        industry_vertical: Industry vertical the brand belongs to.
        competitors: Tuple of competitor brand names.
        monitoring_config: Configuration for AI engine monitoring.
        created_at: When the client brand was onboarded.
        is_active: Whether the client brand is currently active.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    agency_id: str = ""
    brand_name: str = ""
    brand_logo_url: str | None = None
    industry_vertical: str = ""
    competitors: tuple[str, ...] = ()
    monitoring_config: MonitoringConfig = field(default_factory=MonitoringConfig)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.brand_name or not self.brand_name.strip():
            raise ValueError("ClientBrand brand_name cannot be empty")
        if not self.agency_id or not self.agency_id.strip():
            raise ValueError("ClientBrand agency_id cannot be empty")


@dataclass(frozen=True)
class WhiteLabelConfig:
    """White-label branding configuration for an agency.

    Controls how reports and dashboards appear to agency clients,
    including colours, logos, email settings, and footer text.

    Attributes:
        id: Unique configuration identifier.
        agency_id: The owning agency's identifier.
        company_name: The agency's display name in branded reports.
        logo_url: URL to the agency logo for branding.
        primary_color: Primary brand colour (hex, e.g. '#1a2b3c').
        secondary_color: Secondary brand colour (hex).
        accent_color: Accent colour (hex).
        custom_domain: Custom domain for white-label portal.
        email_from_name: Display name in outbound emails.
        email_from_address: From address in outbound emails.
        report_footer_text: Custom footer text in generated reports.
        powered_by_visible: Whether 'Powered by LUMINA' is shown.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    agency_id: str = ""
    company_name: str = ""
    logo_url: str = ""
    primary_color: str = "#000000"
    secondary_color: str = "#ffffff"
    accent_color: str = "#0066cc"
    custom_domain: str | None = None
    email_from_name: str = ""
    email_from_address: str = ""
    report_footer_text: str = ""
    powered_by_visible: bool = True


@dataclass(frozen=True)
class ClientReport:
    """A generated report for a client brand.

    Attributes:
        id: Unique report identifier.
        agency_id: The owning agency's identifier.
        client_brand_id: The client brand this report is for.
        report_type: The type of report (weekly, monthly, quarterly, custom).
        title: Report title.
        generated_at: When the report was generated.
        data: Report data stored as a tuple of key-value items for immutability.
        pdf_url: Optional URL to the generated PDF.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    agency_id: str = ""
    client_brand_id: str = ""
    report_type: ReportType = ReportType.WEEKLY_SUMMARY
    title: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: tuple[tuple[str, object], ...] = ()
    pdf_url: str | None = None
