"""
Tests for the LUMINA external platform integrations.

Covers:
- HubSpot adapter contact creation
- Salesforce adapter OAuth refresh flow
- Integration manager routing to correct adapter
- Integration manager handling of missing integrations
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from lumina.infrastructure.integrations.hubspot_adapter import HubSpotAdapter
from lumina.infrastructure.integrations.integration_manager import (
    IntegrationManager,
    Platform,
)
from lumina.infrastructure.integrations.salesforce_adapter import SalesforceAdapter


# =============================================================================
# HubSpot Adapter Tests
# =============================================================================


class TestHubSpotAdapter:
    @pytest.mark.asyncio
    async def test_creates_contact(self) -> None:
        """Verify HubSpot adapter creates a contact with correct payload."""
        adapter = HubSpotAdapter(access_token="test-token")

        captured_payload: dict[str, Any] = {}
        captured_url: str = ""

        async def mock_post(
            self: Any, url: str, *, headers: Any = None, json: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal captured_payload, captured_url
            captured_url = url
            captured_payload = json or {}
            return httpx.Response(
                201,
                json={
                    "id": "contact-123",
                    "properties": {
                        "email": "user@example.com",
                        "firstname": "Jane",
                        "lastname": "Doe",
                    },
                },
                request=httpx.Request("POST", url),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await adapter.create_contact(
                "user@example.com",
                {"firstname": "Jane", "lastname": "Doe"},
            )

        assert "/crm/v3/objects/contacts" in captured_url
        assert captured_payload["properties"]["email"] == "user@example.com"
        assert captured_payload["properties"]["firstname"] == "Jane"
        assert result["id"] == "contact-123"

    @pytest.mark.asyncio
    async def test_pushes_lumina_metrics(self) -> None:
        """Verify HubSpot adapter pushes LUMINA metrics as custom properties."""
        adapter = HubSpotAdapter(access_token="test-token")

        captured_payload: dict[str, Any] = {}

        async def mock_patch(
            self: Any, url: str, *, headers: Any = None, json: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal captured_payload
            captured_payload = json or {}
            return httpx.Response(
                200,
                json={"id": "company-456", "properties": {}},
                request=httpx.Request("PATCH", url),
            )

        with patch.object(httpx.AsyncClient, "patch", mock_patch):
            await adapter.push_lumina_metrics(
                "company-456",
                avs_score=78.5,
                citation_frequency=0.42,
                geo_score=65.0,
            )

        assert captured_payload["properties"]["lumina_avs_score"] == "78.5"
        assert captured_payload["properties"]["lumina_citation_frequency"] == "0.42"
        assert captured_payload["properties"]["lumina_geo_score"] == "65.0"

    @pytest.mark.asyncio
    async def test_connection_test_returns_true_on_success(self) -> None:
        """Verify test_connection returns True when API responds successfully."""
        adapter = HubSpotAdapter(access_token="test-token")

        async def mock_get(
            self: Any, url: str, *, headers: Any = None, params: Any = None, **kwargs: Any
        ) -> httpx.Response:
            return httpx.Response(
                200,
                json={"results": []},
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            result = await adapter.test_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_connection_test_returns_false_on_failure(self) -> None:
        """Verify test_connection returns False when API fails."""
        adapter = HubSpotAdapter(access_token="bad-token")

        async def mock_get(
            self: Any, url: str, *, headers: Any = None, params: Any = None, **kwargs: Any
        ) -> httpx.Response:
            return httpx.Response(
                401,
                json={"message": "Unauthorized"},
                request=httpx.Request("GET", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get):
            result = await adapter.test_connection()

        assert result is False


# =============================================================================
# Salesforce Adapter Tests
# =============================================================================


class TestSalesforceAdapter:
    @pytest.mark.asyncio
    async def test_handles_oauth_refresh(self) -> None:
        """Verify Salesforce adapter refreshes token on 401 and retries."""
        adapter = SalesforceAdapter(
            instance_url="https://na1.salesforce.com",
            access_token="expired-token",
            refresh_token="valid-refresh-token",
            client_id="client-id",
            client_secret="client-secret",
        )

        call_count = 0

        async def mock_get(
            self: Any, url: str, *, headers: Any = None, params: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            auth_header = (headers or {}).get("Authorization", "")
            if "expired-token" in auth_header:
                return httpx.Response(
                    401,
                    json=[{"errorCode": "INVALID_SESSION_ID"}],
                    request=httpx.Request("GET", url),
                )
            return httpx.Response(
                200,
                json={"sobjects": []},
                request=httpx.Request("GET", url),
            )

        async def mock_post(
            self: Any, url: str, *, data: Any = None, headers: Any = None, json: Any = None, **kwargs: Any
        ) -> httpx.Response:
            # Token refresh endpoint
            return httpx.Response(
                200,
                json={
                    "access_token": "new-valid-token",
                    "instance_url": "https://na1.salesforce.com",
                },
                request=httpx.Request("POST", url),
            )

        with patch.object(httpx.AsyncClient, "get", mock_get), \
             patch.object(httpx.AsyncClient, "post", mock_post):
            result = await adapter.test_connection()

        assert result is True
        assert adapter._access_token == "new-valid-token"

    @pytest.mark.asyncio
    async def test_refresh_raises_without_refresh_token(self) -> None:
        """Verify refresh_access_token raises when no refresh token is set."""
        adapter = SalesforceAdapter(
            instance_url="https://na1.salesforce.com",
            access_token="some-token",
        )

        with pytest.raises(ValueError, match="No refresh token"):
            await adapter.refresh_access_token()

    @pytest.mark.asyncio
    async def test_creates_record(self) -> None:
        """Verify Salesforce adapter creates a record with correct payload."""
        adapter = SalesforceAdapter(
            instance_url="https://na1.salesforce.com",
            access_token="valid-token",
        )

        captured_payload: dict[str, Any] = {}

        async def mock_post(
            self: Any, url: str, *, headers: Any = None, json: Any = None, **kwargs: Any
        ) -> httpx.Response:
            nonlocal captured_payload
            captured_payload = json or {}
            return httpx.Response(
                201,
                json={"id": "001XXXXXXXXXXXX", "success": True},
                request=httpx.Request("POST", url),
            )

        with patch.object(httpx.AsyncClient, "post", mock_post):
            result = await adapter.create_record(
                "LUMINA_Brand__c",
                {"Name": "Acme Corp", "External_Brand_Id__c": "brand-acme"},
            )

        assert result["id"] == "001XXXXXXXXXXXX"
        assert captured_payload["Name"] == "Acme Corp"


# =============================================================================
# Integration Manager Tests
# =============================================================================


class _MockHubSpotAdapter:
    """Mock HubSpot adapter for testing."""

    def __init__(self, credentials: dict[str, str]) -> None:
        self.credentials = credentials
        self.synced_data: list[dict[str, Any]] = []

    async def push_lumina_metrics(self, company_id: str, **kwargs: Any) -> dict[str, Any]:
        result = {"company_id": company_id, **kwargs}
        self.synced_data.append(result)
        return result

    async def create_contact(self, email: str, properties: dict[str, str]) -> dict[str, Any]:
        return {"id": "contact-new", "properties": {"email": email, **properties}}

    async def test_connection(self) -> bool:
        return True


class _MockSalesforceAdapter:
    """Mock Salesforce adapter for testing."""

    def __init__(self, credentials: dict[str, str]) -> None:
        self.credentials = credentials

    async def sync_brand_data(self, **kwargs: Any) -> dict[str, Any]:
        return {"action": "created", "id": "001XXXX"}

    async def test_connection(self) -> bool:
        return True


class TestIntegrationManager:
    def test_routes_to_correct_adapter(self) -> None:
        """Verify integration manager routes sync to the correct platform adapter."""
        import asyncio

        manager = IntegrationManager()

        # Register adapter factories
        manager.register_adapter_factory(
            Platform.HUBSPOT, lambda creds: _MockHubSpotAdapter(creds)
        )
        manager.register_adapter_factory(
            Platform.SALESFORCE, lambda creds: _MockSalesforceAdapter(creds)
        )

        # Configure integrations
        manager.configure_integration(
            tenant_id="tenant-1",
            platform=Platform.HUBSPOT,
            credentials={"access_token": "hs-token"},
        )
        manager.configure_integration(
            tenant_id="tenant-1",
            platform=Platform.SALESFORCE,
            credentials={"access_token": "sf-token", "instance_url": "https://na1.salesforce.com"},
        )

        # Sync to HubSpot
        result = asyncio.get_event_loop().run_until_complete(
            manager.sync_to_platform(
                "tenant-1",
                Platform.HUBSPOT,
                {
                    "action": "push_metrics",
                    "company_id": "comp-1",
                    "avs_score": 75.0,
                },
            )
        )
        assert result["company_id"] == "comp-1"

    def test_handles_missing_integration(self) -> None:
        """Verify integration manager raises KeyError for unconfigured tenant/platform."""
        import asyncio

        manager = IntegrationManager()
        manager.register_adapter_factory(
            Platform.HUBSPOT, lambda creds: _MockHubSpotAdapter(creds)
        )

        with pytest.raises(KeyError, match="No active integration found"):
            asyncio.get_event_loop().run_until_complete(
                manager.sync_to_platform(
                    "nonexistent-tenant",
                    Platform.HUBSPOT,
                    {"action": "push_metrics", "company_id": "x"},
                )
            )

    def test_handles_missing_adapter_factory(self) -> None:
        """Verify integration manager raises ValueError when no factory is registered."""
        import asyncio

        manager = IntegrationManager()
        # Configure an integration but do not register a factory
        manager.configure_integration(
            tenant_id="tenant-1",
            platform=Platform.HUBSPOT,
            credentials={"access_token": "token"},
        )

        with pytest.raises(ValueError, match="No adapter factory registered"):
            asyncio.get_event_loop().run_until_complete(
                manager.sync_to_platform(
                    "tenant-1",
                    Platform.HUBSPOT,
                    {"action": "push_metrics", "company_id": "x"},
                )
            )

    def test_list_integrations_filters_by_tenant(self) -> None:
        """Verify list_integrations returns only configs for the given tenant."""
        manager = IntegrationManager()
        manager.configure_integration(
            tenant_id="tenant-1", platform=Platform.HUBSPOT, credentials={}
        )
        manager.configure_integration(
            tenant_id="tenant-2", platform=Platform.SALESFORCE, credentials={}
        )
        manager.configure_integration(
            tenant_id="tenant-1", platform=Platform.SLACK, credentials={}
        )

        tenant_1_integrations = manager.list_integrations("tenant-1")
        assert len(tenant_1_integrations) == 2
        assert all(c.tenant_id == "tenant-1" for c in tenant_1_integrations)

        tenant_2_integrations = manager.list_integrations("tenant-2")
        assert len(tenant_2_integrations) == 1

    def test_update_and_delete_integration(self) -> None:
        """Verify update and delete operations work correctly."""
        manager = IntegrationManager()
        config = manager.configure_integration(
            tenant_id="tenant-1",
            platform=Platform.HUBSPOT,
            credentials={"access_token": "old-token"},
        )

        # Update
        updated = manager.update_integration(
            config.id,
            credentials={"access_token": "new-token"},
            is_active=False,
        )
        assert updated.credentials["access_token"] == "new-token"
        assert updated.is_active is False

        # Delete
        manager.delete_integration(config.id)
        assert len(manager.list_integrations("tenant-1")) == 0

    def test_delete_nonexistent_raises(self) -> None:
        """Verify deleting a nonexistent integration raises KeyError."""
        manager = IntegrationManager()
        with pytest.raises(KeyError, match="not found"):
            manager.delete_integration("nonexistent-id")

    @pytest.mark.asyncio
    async def test_test_connection_delegates_to_adapter(self) -> None:
        """Verify test_connection calls the adapter's test_connection method."""
        manager = IntegrationManager()
        manager.register_adapter_factory(
            Platform.HUBSPOT, lambda creds: _MockHubSpotAdapter(creds)
        )
        manager.configure_integration(
            tenant_id="tenant-1",
            platform=Platform.HUBSPOT,
            credentials={"access_token": "token"},
        )

        result = await manager.test_connection("tenant-1", Platform.HUBSPOT)
        assert result is True
