"""
Agency Module REST API Routes

Architectural Intent:
- Thin HTTP adapter translating REST calls to application-layer use cases
- All business logic resides in the Agency bounded context
- Routes depend on the DI container for use case instances
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from lumina.agency.domain.entities import MonitoringConfig
from lumina.agency.domain.value_objects import AgencyPlanTier, ReportType


# =============================================================================
# Request / Response Schemas
# =============================================================================


class CreateAgencyRequest(BaseModel):
    """Request to create a new agency."""

    name: str
    slug: str
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    custom_domain: str | None = None
    plan_tier: str = "starter"
    max_clients: int = 5


class AgencyResponse(BaseModel):
    """Response for an agency."""

    id: str
    name: str
    slug: str
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    custom_domain: str | None = None
    plan_tier: str
    max_clients: int
    is_active: bool
    created_at: datetime


class OnboardClientRequest(BaseModel):
    """Request to onboard a new client brand."""

    brand_name: str
    industry_vertical: str = ""
    competitors: list[str] = Field(default_factory=list)
    polling_frequency: str = "daily"


class ClientBrandResponse(BaseModel):
    """Response for a client brand."""

    id: str
    agency_id: str
    brand_name: str
    brand_logo_url: str | None = None
    industry_vertical: str
    competitors: list[str]
    is_active: bool
    created_at: datetime


class WhiteLabelRequest(BaseModel):
    """Request to configure white-label branding."""

    company_name: str
    logo_url: str
    primary_color: str = "#000000"
    secondary_color: str = "#ffffff"
    accent_color: str = "#0066cc"
    custom_domain: str | None = None
    email_from_name: str = ""
    email_from_address: str = ""
    report_footer_text: str = ""
    powered_by_visible: bool = True


class WhiteLabelResponse(BaseModel):
    """Response for white-label configuration."""

    id: str
    agency_id: str
    company_name: str
    logo_url: str
    primary_color: str
    secondary_color: str
    accent_color: str
    custom_domain: str | None
    powered_by_visible: bool


class GenerateReportRequest(BaseModel):
    """Request to generate a client report."""

    report_type: str = "weekly_summary"


class ClientReportResponse(BaseModel):
    """Response for a client report."""

    id: str
    agency_id: str
    client_brand_id: str
    report_type: str
    title: str
    generated_at: datetime
    pdf_url: str | None = None


class BulkReportRequest(BaseModel):
    """Request to generate reports for all clients."""

    report_type: str = "weekly_summary"


class BulkReportResponse(BaseModel):
    """Response for bulk report generation."""

    agency_id: str
    reports_generated: int
    reports: list[ClientReportResponse]


class PortfolioOverviewResponse(BaseModel):
    """Response for portfolio overview."""

    agency_id: str
    total_clients: int
    avg_avs: float
    clients_improving: int
    clients_declining: int
    top_performer: str
    needs_attention: list[str]


class ClientReportListResponse(BaseModel):
    """Response for paginated client reports."""

    client_brand_id: str
    reports: list[ClientReportResponse]
    total_count: int


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/api/v1/agency", tags=["agency"])


@router.post("", response_model=AgencyResponse, status_code=201)
async def create_agency(
    body: CreateAgencyRequest,
    request: Request,
) -> AgencyResponse:
    """Create a new agency."""
    container = request.app.state.container

    from lumina.agency.domain.entities import Agency

    plan_tier = AgencyPlanTier(body.plan_tier)

    agency = Agency(
        id=str(uuid4()),
        name=body.name,
        slug=body.slug,
        logo_url=body.logo_url,
        primary_color=body.primary_color,
        secondary_color=body.secondary_color,
        custom_domain=body.custom_domain,
        plan_tier=plan_tier,
        max_clients=body.max_clients,
        is_active=True,
        created_at=datetime.now(UTC),
    )

    repo = container.agency_repository
    await repo.save_agency(agency)

    return AgencyResponse(
        id=agency.id,
        name=agency.name,
        slug=agency.slug,
        logo_url=agency.logo_url,
        primary_color=agency.primary_color,
        secondary_color=agency.secondary_color,
        custom_domain=agency.custom_domain,
        plan_tier=agency.plan_tier.value,
        max_clients=agency.max_clients,
        is_active=agency.is_active,
        created_at=agency.created_at,
    )


@router.get("/portfolio", response_model=PortfolioOverviewResponse)
async def get_portfolio_overview(
    request: Request,
    agency_id: str = "",
) -> PortfolioOverviewResponse:
    """Get portfolio overview for an agency."""
    container = request.app.state.container

    from lumina.agency.application.queries import GetPortfolioOverviewQuery

    query = GetPortfolioOverviewQuery(repository=container.agency_repository)
    summary = await query.execute(agency_id=agency_id)

    return PortfolioOverviewResponse(
        agency_id=summary.agency_id,
        total_clients=summary.total_clients,
        avg_avs=summary.avg_avs.value,
        clients_improving=summary.clients_improving,
        clients_declining=summary.clients_declining,
        top_performer=summary.top_performer,
        needs_attention=summary.needs_attention,
    )


@router.post("/clients", response_model=ClientBrandResponse, status_code=201)
async def onboard_client(
    body: OnboardClientRequest,
    request: Request,
    agency_id: str = "",
) -> ClientBrandResponse:
    """Onboard a new client brand under an agency."""
    container = request.app.state.container

    from lumina.agency.application.commands import OnboardClientCommand

    command = OnboardClientCommand(
        repository=container.agency_repository,
        event_bus=container.event_bus,
    )

    monitoring_config = MonitoringConfig(
        polling_frequency=body.polling_frequency,
    )

    client = await command.execute(
        agency_id=agency_id,
        brand_name=body.brand_name,
        industry_vertical=body.industry_vertical,
        competitors=tuple(body.competitors),
        monitoring_config=monitoring_config,
    )

    return ClientBrandResponse(
        id=client.id,
        agency_id=client.agency_id,
        brand_name=client.brand_name,
        brand_logo_url=client.brand_logo_url,
        industry_vertical=client.industry_vertical,
        competitors=list(client.competitors),
        is_active=client.is_active,
        created_at=client.created_at,
    )


@router.get("/clients", response_model=list[ClientBrandResponse])
async def list_clients(
    request: Request,
    agency_id: str = "",
) -> list[ClientBrandResponse]:
    """List all client brands for an agency."""
    container = request.app.state.container

    repo = container.agency_repository
    clients = await repo.list_clients(agency_id)

    return [
        ClientBrandResponse(
            id=c.id,
            agency_id=c.agency_id,
            brand_name=c.brand_name,
            brand_logo_url=c.brand_logo_url,
            industry_vertical=c.industry_vertical,
            competitors=list(c.competitors),
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in clients
    ]


@router.get("/clients/{client_id}", response_model=ClientBrandResponse)
async def get_client_detail(
    client_id: str,
    request: Request,
) -> ClientBrandResponse:
    """Get detailed metrics for a specific client."""
    container = request.app.state.container

    from lumina.agency.application.queries import GetClientDetailQuery

    query = GetClientDetailQuery(repository=container.agency_repository)
    client = await query.execute(client_id)

    return ClientBrandResponse(
        id=client.id,
        agency_id=client.agency_id,
        brand_name=client.brand_name,
        brand_logo_url=client.brand_logo_url,
        industry_vertical=client.industry_vertical,
        competitors=list(client.competitors),
        is_active=client.is_active,
        created_at=client.created_at,
    )


@router.put("/white-label", response_model=WhiteLabelResponse)
async def configure_white_label(
    body: WhiteLabelRequest,
    request: Request,
    agency_id: str = "",
) -> WhiteLabelResponse:
    """Configure white-label branding for an agency."""
    container = request.app.state.container

    from lumina.agency.application.commands import ConfigureWhiteLabelCommand

    command = ConfigureWhiteLabelCommand(
        repository=container.agency_repository,
        event_bus=container.event_bus,
    )

    config = await command.execute(
        agency_id=agency_id,
        company_name=body.company_name,
        logo_url=body.logo_url,
        primary_color=body.primary_color,
        secondary_color=body.secondary_color,
        accent_color=body.accent_color,
        custom_domain=body.custom_domain,
        email_from_name=body.email_from_name,
        email_from_address=body.email_from_address,
        report_footer_text=body.report_footer_text,
        powered_by_visible=body.powered_by_visible,
    )

    return WhiteLabelResponse(
        id=config.id,
        agency_id=config.agency_id,
        company_name=config.company_name,
        logo_url=config.logo_url,
        primary_color=config.primary_color,
        secondary_color=config.secondary_color,
        accent_color=config.accent_color,
        custom_domain=config.custom_domain,
        powered_by_visible=config.powered_by_visible,
    )


@router.post(
    "/clients/{client_id}/reports",
    response_model=ClientReportResponse,
    status_code=201,
)
async def generate_report(
    client_id: str,
    body: GenerateReportRequest,
    request: Request,
    agency_id: str = "",
) -> ClientReportResponse:
    """Generate a report for a specific client."""
    container = request.app.state.container

    from lumina.agency.application.commands import GenerateClientReportCommand

    report_type = ReportType(body.report_type)

    command = GenerateClientReportCommand(
        repository=container.agency_repository,
        event_bus=container.event_bus,
    )

    report = await command.execute(
        agency_id=agency_id,
        client_brand_id=client_id,
        report_type=report_type,
    )

    return ClientReportResponse(
        id=report.id,
        agency_id=report.agency_id,
        client_brand_id=report.client_brand_id,
        report_type=report.report_type.value,
        title=report.title,
        generated_at=report.generated_at,
        pdf_url=report.pdf_url,
    )


@router.post("/reports/bulk", response_model=BulkReportResponse, status_code=201)
async def bulk_generate_reports(
    body: BulkReportRequest,
    request: Request,
    agency_id: str = "",
) -> BulkReportResponse:
    """Generate reports for all active clients of an agency."""
    container = request.app.state.container

    from lumina.agency.application.commands import BulkGenerateReportsCommand

    report_type = ReportType(body.report_type)

    command = BulkGenerateReportsCommand(
        repository=container.agency_repository,
        event_bus=container.event_bus,
    )

    reports = await command.execute(
        agency_id=agency_id,
        report_type=report_type,
    )

    return BulkReportResponse(
        agency_id=agency_id,
        reports_generated=len(reports),
        reports=[
            ClientReportResponse(
                id=r.id,
                agency_id=r.agency_id,
                client_brand_id=r.client_brand_id,
                report_type=r.report_type.value,
                title=r.title,
                generated_at=r.generated_at,
                pdf_url=r.pdf_url,
            )
            for r in reports
        ],
    )


@router.get(
    "/clients/{client_id}/reports",
    response_model=ClientReportListResponse,
)
async def list_client_reports(
    client_id: str,
    request: Request,
    limit: int = 20,
    offset: int = 0,
) -> ClientReportListResponse:
    """List reports for a client, paginated."""
    container = request.app.state.container

    from lumina.agency.application.queries import ListClientReportsQuery

    query = ListClientReportsQuery(repository=container.agency_repository)
    reports = await query.execute(
        client_brand_id=client_id,
        limit=limit,
        offset=offset,
    )

    return ClientReportListResponse(
        client_brand_id=client_id,
        reports=[
            ClientReportResponse(
                id=r.id,
                agency_id=r.agency_id,
                client_brand_id=r.client_brand_id,
                report_type=r.report_type.value,
                title=r.title,
                generated_at=r.generated_at,
                pdf_url=r.pdf_url,
            )
            for r in reports
        ],
        total_count=len(reports),
    )


@router.get("/reports/{report_id}/download")
async def download_report_pdf(
    report_id: str,
    request: Request,
) -> Response:
    """Download a report as PDF."""
    container = request.app.state.container

    from lumina.agency.infrastructure.report_exporter import ReportExporter

    # In a full implementation, we would look up the report by ID
    # and the agency's white-label config, then export.
    # For now, return a placeholder response.
    return Response(
        content=b"%PDF-1.4 placeholder",
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{report_id}.pdf"',
        },
    )
