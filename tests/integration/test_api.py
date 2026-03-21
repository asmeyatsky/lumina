"""
Integration Tests for the LUMINA FastAPI Application

Verifies:
- Health check endpoint returns 200
- PULSE endpoints return correct status codes
- Error handling maps domain errors to HTTP status codes
- Tenant header middleware blocks requests without X-Tenant-ID
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from lumina.presentation.api.app import create_app
from lumina.presentation.config.dependency_injection import Container


@pytest.fixture
def app():
    """Create a fresh FastAPI app with the DI container pre-wired."""
    application = create_app()
    # Wire the container directly (bypassing lifespan for test simplicity)
    application.state.container = Container()
    return application


@pytest.fixture
async def client(app):
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestHealthCheck:
    """Tests for the health check endpoint."""

    async def test_health_check_returns_200(self, client: AsyncClient) -> None:
        """Health check returns 200 with correct body."""
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["version"] == "1.0.0"
        assert body["service"] == "lumina"

    async def test_health_check_no_tenant_header_required(
        self, client: AsyncClient
    ) -> None:
        """Health check does not require X-Tenant-ID header."""
        response = await client.get("/health")
        assert response.status_code == 200


class TestTenantMiddleware:
    """Tests for the tenant header middleware."""

    async def test_request_without_tenant_header_returns_400(
        self, client: AsyncClient
    ) -> None:
        """Non-exempt endpoints require X-Tenant-ID header."""
        response = await client.get("/api/v1/pulse/brands/test-brand/trends")
        assert response.status_code == 400
        body = response.json()
        assert "X-Tenant-ID" in body["detail"]

    async def test_request_with_tenant_header_succeeds(
        self, client: AsyncClient
    ) -> None:
        """Endpoints work when X-Tenant-ID is provided."""
        response = await client.get(
            "/api/v1/pulse/brands/test-brand/trends",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 200

    async def test_empty_tenant_header_returns_400(
        self, client: AsyncClient
    ) -> None:
        """Empty X-Tenant-ID header is rejected."""
        response = await client.get(
            "/api/v1/pulse/brands/test-brand/trends",
            headers={"X-Tenant-ID": "   "},
        )
        assert response.status_code == 400


class TestPulseEndpoints:
    """Tests for PULSE module endpoints."""

    async def test_trigger_monitoring_run_returns_201(
        self, client: AsyncClient
    ) -> None:
        """POST /pulse/monitoring-runs returns 201 with a run_id."""
        response = await client.post(
            "/api/v1/pulse/monitoring-runs",
            json={
                "brand_id": "test-brand",
                "engines": ["claude", "gpt-4o"],
            },
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 201
        body = response.json()
        assert "run_id" in body
        assert body["brand_id"] == "test-brand"
        assert body["status"] == "pending"

    async def test_get_monitoring_run_returns_404(
        self, client: AsyncClient
    ) -> None:
        """GET /pulse/monitoring-runs/{run_id} returns 404 for unknown run."""
        response = await client.get(
            "/api/v1/pulse/monitoring-runs/nonexistent-run",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 404
        body = response.json()
        assert body["error_type"] == "entity_not_found"

    async def test_create_prompt_battery_returns_201(
        self, client: AsyncClient
    ) -> None:
        """POST /pulse/batteries returns 201."""
        response = await client.post(
            "/api/v1/pulse/batteries",
            json={
                "brand_id": "test-brand",
                "name": "Test Battery",
                "prompts": ["What is X?", "Tell me about Y."],
            },
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Test Battery"
        assert len(body["prompts"]) == 2

    async def test_get_trends_returns_200(
        self, client: AsyncClient
    ) -> None:
        """GET /pulse/brands/{brand_id}/trends returns 200."""
        response = await client.get(
            "/api/v1/pulse/brands/test-brand/trends",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["brand_id"] == "test-brand"

    async def test_get_share_of_voice_returns_200(
        self, client: AsyncClient
    ) -> None:
        """GET /pulse/brands/{brand_id}/share-of-voice returns 200."""
        response = await client.get(
            "/api/v1/pulse/brands/test-brand/share-of-voice",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 200


class TestErrorHandling:
    """Tests for error handling across the API."""

    async def test_entity_not_found_returns_404(
        self, client: AsyncClient
    ) -> None:
        """EntityNotFoundError is mapped to 404."""
        response = await client.get(
            "/api/v1/graph/profiles/nonexistent-brand",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 404
        body = response.json()
        assert body["error_type"] == "entity_not_found"

    async def test_beam_asset_not_found_returns_404(
        self, client: AsyncClient
    ) -> None:
        """EntityNotFoundError from BEAM is mapped to 404."""
        response = await client.get(
            "/api/v1/beam/assets/test-asset/score",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 404

    async def test_404_for_unknown_route(
        self, client: AsyncClient
    ) -> None:
        """Unknown routes return 404."""
        response = await client.get(
            "/api/v1/nonexistent",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 404

    async def test_graph_dimension_update_returns_404(
        self, client: AsyncClient
    ) -> None:
        """PUT to non-existent dimension returns 404."""
        response = await client.put(
            "/api/v1/graph/profiles/brand-1/dimensions/dim-1",
            json={"value": "updated"},
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 404

    async def test_signal_plan_returns_404(
        self, client: AsyncClient
    ) -> None:
        """GET non-existent distribution plan returns 404."""
        response = await client.get(
            "/api/v1/signal/plans/nonexistent",
            headers={"X-Tenant-ID": "tenant-1"},
        )
        assert response.status_code == 404
