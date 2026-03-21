"""
Agency Domain Events

Architectural Intent:
- Immutable event records capturing state transitions in the Agency bounded context
- Published after use-case completion for cross-context communication
- All extend the shared DomainEvent base class
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lumina.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class ClientBrandOnboarded(DomainEvent):
    """Emitted when a new client brand is onboarded to an agency."""

    agency_id: str = ""
    brand_name: str = ""
    vertical: str = ""


@dataclass(frozen=True)
class ClientReportGenerated(DomainEvent):
    """Emitted when a report is generated for a client brand."""

    agency_id: str = ""
    client_brand_id: str = ""
    report_type: str = ""


@dataclass(frozen=True)
class WhiteLabelConfigured(DomainEvent):
    """Emitted when an agency configures its white-label branding."""

    agency_id: str = ""
    custom_domain: str | None = None


@dataclass(frozen=True)
class PortfolioAlertTriggered(DomainEvent):
    """Emitted when a portfolio-level alert is triggered for an agency."""

    agency_id: str = ""
    alert_type: str = ""
    affected_brands: tuple[str, ...] = ()
