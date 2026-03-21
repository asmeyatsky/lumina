"""
Agency Application Queries (Read-Side Use Cases)

Architectural Intent:
- Queries are read-only operations that never mutate state
- Each query encapsulates a single read-side use case
- Return domain entities or value objects directly (no DTOs at this layer)
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.errors import EntityNotFoundError
from lumina.shared.domain.value_objects import Score

from lumina.intelligence.domain.entities import AIVisibilityScore

from lumina.agency.domain.entities import Agency, ClientBrand, ClientReport
from lumina.agency.domain.ports import AgencyRepositoryPort
from lumina.agency.domain.services import PortfolioAnalysisService
from lumina.agency.domain.value_objects import ClientOverview, PortfolioSummary


@dataclass(frozen=True)
class GetPortfolioOverviewQuery:
    """Return portfolio summary with all client AVS scores."""

    repository: AgencyRepositoryPort

    async def execute(
        self,
        agency_id: str,
        client_scores: dict[str, AIVisibilityScore] | None = None,
    ) -> PortfolioSummary:
        """Fetch the portfolio overview for an agency.

        Args:
            agency_id: The agency to query.
            client_scores: Optional pre-fetched client AVS scores.
                Keys are brand names, values are AIVisibilityScore entities.

        Returns:
            A PortfolioSummary value object.

        Raises:
            EntityNotFoundError: If the agency does not exist.
        """
        agency = await self.repository.get_agency(agency_id)
        if agency is None:
            raise EntityNotFoundError(f"Agency {agency_id} not found")

        if client_scores is None:
            # Return empty summary when no scores are provided
            clients = await self.repository.list_clients(agency_id)
            return PortfolioSummary(
                agency_id=agency_id,
                total_clients=len([c for c in clients if c.is_active]),
                avg_avs=Score(0.0),
                clients_improving=0,
                clients_declining=0,
                top_performer="",
                needs_attention=[],
            )

        summary = PortfolioAnalysisService.generate_portfolio_summary(client_scores)
        # Override agency_id since the domain service may not have it
        return PortfolioSummary(
            agency_id=agency_id,
            total_clients=summary.total_clients,
            avg_avs=summary.avg_avs,
            clients_improving=summary.clients_improving,
            clients_declining=summary.clients_declining,
            top_performer=summary.top_performer,
            needs_attention=summary.needs_attention,
        )


@dataclass(frozen=True)
class GetClientDetailQuery:
    """Return detailed metrics for a specific client."""

    repository: AgencyRepositoryPort

    async def execute(self, client_id: str) -> ClientBrand:
        """Fetch detailed client brand information.

        Args:
            client_id: The client brand identifier.

        Returns:
            The ClientBrand entity.

        Raises:
            EntityNotFoundError: If the client does not exist.
        """
        client = await self.repository.get_client(client_id)
        if client is None:
            raise EntityNotFoundError(f"Client brand {client_id} not found")
        return client


@dataclass(frozen=True)
class ListClientReportsQuery:
    """Return reports for a client, paginated."""

    repository: AgencyRepositoryPort

    async def execute(
        self,
        client_brand_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ClientReport]:
        """Fetch paginated reports for a client brand.

        Args:
            client_brand_id: The client brand identifier.
            limit: Maximum number of reports to return.
            offset: Number of reports to skip.

        Returns:
            A list of ClientReport entities.
        """
        return await self.repository.list_reports(
            client_brand_id, limit=limit, offset=offset
        )


@dataclass(frozen=True)
class GetAgencyDashboardQuery:
    """Return agency-wide metrics including total clients, avg AVS, trends, and alerts."""

    repository: AgencyRepositoryPort

    async def execute(
        self,
        agency_id: str,
        client_scores: dict[str, AIVisibilityScore] | None = None,
    ) -> dict[str, object]:
        """Fetch the agency dashboard data.

        Args:
            agency_id: The agency to query.
            client_scores: Optional pre-fetched client AVS scores.

        Returns:
            A dictionary with dashboard metrics.

        Raises:
            EntityNotFoundError: If the agency does not exist.
        """
        agency = await self.repository.get_agency(agency_id)
        if agency is None:
            raise EntityNotFoundError(f"Agency {agency_id} not found")

        clients = await self.repository.list_clients(agency_id)
        active_clients = [c for c in clients if c.is_active]

        scores = client_scores or {}
        at_risk: list[str] = []
        rankings: list[ClientOverview] = []

        if scores:
            at_risk = PortfolioAnalysisService.identify_at_risk_clients(scores)
            rankings = PortfolioAnalysisService.rank_clients_by_performance(scores)

        # Compute average AVS
        if scores:
            avg_avs = round(
                sum(avs.overall.value for avs in scores.values()) / len(scores), 2
            )
        else:
            avg_avs = 0.0

        return {
            "agency_id": agency_id,
            "agency_name": agency.name,
            "plan_tier": agency.plan_tier.value,
            "total_clients": len(active_clients),
            "max_clients": agency.max_clients,
            "avg_avs": avg_avs,
            "at_risk_clients": at_risk,
            "top_performers": [
                {
                    "brand_name": r.brand_name,
                    "avs_score": r.avs_score.value,
                    "avs_trend": r.avs_trend,
                }
                for r in rankings[:5]
            ],
            "alerts_count": len(at_risk),
        }
