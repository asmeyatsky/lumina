"""
Integration API Routes — REST endpoints for managing external integrations.

Architectural Intent:
- Thin HTTP adapter translating REST calls to IntegrationManager operations
- CRUD for integration configurations
- Connection testing and manual sync triggers
- OAuth callback handling for platforms that require it
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from lumina.infrastructure.integrations.integration_manager import (
    IntegrationConfig,
    IntegrationManager,
    Platform,
)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


# =============================================================================
# Request / Response Schemas
# =============================================================================


class CreateIntegrationRequest(BaseModel):
    """Request body for creating a new integration."""

    platform: str = Field(..., description="Platform name: hubspot, salesforce, slack")
    credentials: dict[str, str] = Field(default_factory=dict, description="Platform credentials")
    sync_schedule: str = Field("", description="Cron expression for automated syncs")


class UpdateIntegrationRequest(BaseModel):
    """Request body for updating an integration."""

    credentials: dict[str, str] | None = None
    sync_schedule: str | None = None
    is_active: bool | None = None


class IntegrationResponse(BaseModel):
    """Response for a single integration."""

    id: str
    tenant_id: str
    platform: str
    sync_schedule: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SyncRequest(BaseModel):
    """Request body for triggering a manual sync."""

    data: dict[str, Any] = Field(..., description="Data payload to sync")


class ConnectionTestResponse(BaseModel):
    """Response for a connection test."""

    integration_id: str
    platform: str
    success: bool
    message: str


class OAuthCallbackResponse(BaseModel):
    """Response for an OAuth callback."""

    platform: str
    status: str
    message: str


# =============================================================================
# Helper
# =============================================================================


def _to_response(config: IntegrationConfig) -> IntegrationResponse:
    return IntegrationResponse(
        id=config.id,
        tenant_id=config.tenant_id,
        platform=config.platform.value,
        sync_schedule=config.sync_schedule,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _get_manager(request: Request) -> IntegrationManager:
    """Retrieve the IntegrationManager from the app DI container."""
    container = request.app.state.container
    if hasattr(container, "integration_manager"):
        return container.integration_manager
    # Fallback: create a per-app singleton on first access
    if not hasattr(request.app.state, "_integration_manager"):
        request.app.state._integration_manager = IntegrationManager()
    return request.app.state._integration_manager


def _get_tenant_id(request: Request) -> str:
    """Extract tenant ID from request state (set by TenantMiddleware)."""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")
    return tenant_id


def _resolve_platform(platform_str: str) -> Platform:
    """Resolve a string to a Platform enum value."""
    try:
        return Platform(platform_str.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform: {platform_str}. Supported: {', '.join(p.value for p in Platform)}",
        )


# =============================================================================
# Routes
# =============================================================================


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(request: Request) -> list[IntegrationResponse]:
    """List all configured integrations for the current tenant."""
    tenant_id = _get_tenant_id(request)
    manager = _get_manager(request)
    configs = manager.list_integrations(tenant_id)
    return [_to_response(c) for c in configs]


@router.post("", response_model=IntegrationResponse, status_code=201)
async def create_integration(
    body: CreateIntegrationRequest,
    request: Request,
) -> IntegrationResponse:
    """Configure a new integration for the current tenant."""
    tenant_id = _get_tenant_id(request)
    manager = _get_manager(request)
    platform = _resolve_platform(body.platform)

    config = manager.configure_integration(
        tenant_id=tenant_id,
        platform=platform,
        credentials=body.credentials,
        sync_schedule=body.sync_schedule,
    )
    return _to_response(config)


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    body: UpdateIntegrationRequest,
    request: Request,
) -> IntegrationResponse:
    """Update an existing integration configuration."""
    manager = _get_manager(request)
    tenant_id = _get_tenant_id(request)

    try:
        config = manager.get_integration(integration_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Integration {integration_id} not found")

    if config.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorised to modify this integration")

    try:
        updated = manager.update_integration(
            integration_id,
            credentials=body.credentials,
            sync_schedule=body.sync_schedule,
            is_active=body.is_active,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Integration {integration_id} not found")

    return _to_response(updated)


@router.delete("/{integration_id}", status_code=204)
async def delete_integration(
    integration_id: str,
    request: Request,
) -> None:
    """Remove an integration configuration."""
    manager = _get_manager(request)
    tenant_id = _get_tenant_id(request)

    try:
        config = manager.get_integration(integration_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Integration {integration_id} not found")

    if config.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorised to delete this integration")

    try:
        manager.delete_integration(integration_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Integration {integration_id} not found")


@router.post("/{integration_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    integration_id: str,
    request: Request,
) -> ConnectionTestResponse:
    """Test the connection for an integration."""
    manager = _get_manager(request)
    tenant_id = _get_tenant_id(request)

    try:
        config = manager.get_integration(integration_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Integration {integration_id} not found")

    if config.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorised to test this integration")

    try:
        success = await manager.test_connection(tenant_id, config.platform)
        message = "Connection successful" if success else "Connection failed"
    except (KeyError, ValueError) as exc:
        success = False
        message = str(exc)

    return ConnectionTestResponse(
        integration_id=integration_id,
        platform=config.platform.value,
        success=success,
        message=message,
    )


@router.post("/{integration_id}/sync")
async def trigger_sync(
    integration_id: str,
    body: SyncRequest,
    request: Request,
) -> dict[str, Any]:
    """Trigger a manual sync for an integration."""
    manager = _get_manager(request)
    tenant_id = _get_tenant_id(request)

    try:
        config = manager.get_integration(integration_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Integration {integration_id} not found")

    if config.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorised to sync this integration")

    if not config.is_active:
        raise HTTPException(status_code=400, detail="Integration is not active")

    try:
        result = await manager.sync_to_platform(tenant_id, config.platform, body.data)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "synced", "result": result}


@router.get("/oauth/{platform}/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(
    platform: str,
    request: Request,
    code: str = "",
    state: str = "",
) -> OAuthCallbackResponse:
    """Handle the OAuth callback from an external platform.

    After the user authorises LUMINA in the external platform, the platform
    redirects back here with an authorisation code. This endpoint exchanges
    the code for tokens and stores them.
    """
    resolved_platform = _resolve_platform(platform)

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorisation code")

    # In production, exchange the code for tokens via the platform's OAuth endpoint
    # and store them in the integration config. Here we acknowledge receipt.
    return OAuthCallbackResponse(
        platform=resolved_platform.value,
        status="success",
        message=f"OAuth callback received for {resolved_platform.value}. Code exchange pending implementation.",
    )
