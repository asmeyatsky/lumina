"""
Agency Domain Ports (Protocol Interfaces)

Architectural Intent:
- Ports define the contracts the domain requires from the outside world
- Protocol-based (structural subtyping) — no inheritance required
- Infrastructure layer provides concrete adapters
"""

from __future__ import annotations

from typing import Protocol

from lumina.agency.domain.entities import (
    Agency,
    ClientBrand,
    ClientReport,
    WhiteLabelConfig,
)


class AgencyRepositoryPort(Protocol):
    """Port for persisting and retrieving Agency bounded context aggregates."""

    async def save_agency(self, agency: Agency) -> None:
        """Persist an agency."""
        ...

    async def get_agency(self, agency_id: str) -> Agency | None:
        """Retrieve an agency by its identifier."""
        ...

    async def save_client(self, client: ClientBrand) -> None:
        """Persist a client brand."""
        ...

    async def get_client(self, client_id: str) -> ClientBrand | None:
        """Retrieve a client brand by its identifier."""
        ...

    async def list_clients(self, agency_id: str) -> list[ClientBrand]:
        """List all client brands for an agency."""
        ...

    async def save_report(self, report: ClientReport) -> None:
        """Persist a client report."""
        ...

    async def list_reports(
        self, client_brand_id: str, limit: int = 20, offset: int = 0
    ) -> list[ClientReport]:
        """List reports for a client brand, paginated."""
        ...

    async def save_white_label_config(self, config: WhiteLabelConfig) -> None:
        """Persist a white-label configuration."""
        ...

    async def get_white_label_config(self, agency_id: str) -> WhiteLabelConfig | None:
        """Retrieve the white-label configuration for an agency."""
        ...


class ReportExportPort(Protocol):
    """Port for exporting reports to various formats."""

    async def export_pdf(
        self, report: ClientReport, branding: WhiteLabelConfig
    ) -> bytes:
        """Export a report as a branded PDF document.

        Args:
            report: The client report to export.
            branding: The white-label configuration for branding.

        Returns:
            The PDF content as bytes.
        """
        ...

    async def export_csv(self, data: dict[str, object]) -> bytes:
        """Export report data as CSV.

        Args:
            data: The data to export.

        Returns:
            The CSV content as bytes.
        """
        ...
