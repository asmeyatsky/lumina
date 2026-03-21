"""
Integration Manager — Orchestrates all external platform integrations.

Architectural Intent:
- Central registry for all integration connections per tenant
- Routes sync operations to the correct platform adapter
- Manages integration lifecycle: configure, test, sync, deactivate
- Stores integration configuration (in-memory for now, database-ready)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger("lumina.integrations.manager")


class Platform(str, Enum):
    """Supported integration platforms."""

    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    SLACK = "slack"


@dataclass
class IntegrationConfig:
    """Configuration for a single tenant-platform integration.

    Attributes:
        id: Unique integration config identifier.
        tenant_id: The tenant this integration belongs to.
        platform: Target platform.
        credentials: Platform-specific credentials dict.
        sync_schedule: Cron expression for automated syncs (empty = manual only).
        is_active: Whether the integration is currently enabled.
        created_at: When the integration was first configured.
        updated_at: When the configuration was last modified.
    """

    id: str
    tenant_id: str
    platform: Platform
    credentials: dict[str, str] = field(default_factory=dict)
    sync_schedule: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class IntegrationManager:
    """Orchestrates integration connections across tenants and platforms.

    Manages configuration storage (in-memory) and routes sync operations
    to the correct adapter.
    """

    def __init__(self) -> None:
        # Storage: integration_id -> IntegrationConfig
        self._configs: dict[str, IntegrationConfig] = {}
        # Adapter factories: platform -> callable that creates an adapter from credentials
        self._adapter_factories: dict[Platform, Any] = {}

    # -- Adapter registration --------------------------------------------------

    def register_adapter_factory(
        self, platform: Platform, factory: Any
    ) -> None:
        """Register a factory function that creates a platform adapter from credentials.

        The factory should accept a dict of credentials and return an adapter instance.
        """
        self._adapter_factories[platform] = factory

    # -- Integration CRUD ------------------------------------------------------

    def configure_integration(
        self,
        tenant_id: str,
        platform: Platform,
        credentials: dict[str, str],
        *,
        sync_schedule: str = "",
    ) -> IntegrationConfig:
        """Configure a new integration for a tenant.

        Args:
            tenant_id: Tenant identifier.
            platform: Target platform.
            credentials: Platform-specific credentials.
            sync_schedule: Optional cron schedule for automated syncs.

        Returns:
            The created IntegrationConfig.
        """
        config = IntegrationConfig(
            id=str(uuid4()),
            tenant_id=tenant_id,
            platform=platform,
            credentials=credentials,
            sync_schedule=sync_schedule,
        )
        self._configs[config.id] = config
        logger.info(
            "Integration configured: %s for tenant %s on %s",
            config.id,
            tenant_id,
            platform.value,
        )
        return config

    def update_integration(
        self,
        integration_id: str,
        *,
        credentials: dict[str, str] | None = None,
        sync_schedule: str | None = None,
        is_active: bool | None = None,
    ) -> IntegrationConfig:
        """Update an existing integration configuration.

        Args:
            integration_id: The integration to update.
            credentials: New credentials (replaces existing if provided).
            sync_schedule: New sync schedule.
            is_active: Enable/disable the integration.

        Returns:
            The updated IntegrationConfig.

        Raises:
            KeyError: If the integration does not exist.
        """
        config = self._configs.get(integration_id)
        if config is None:
            raise KeyError(f"Integration {integration_id} not found")

        if credentials is not None:
            config.credentials = credentials
        if sync_schedule is not None:
            config.sync_schedule = sync_schedule
        if is_active is not None:
            config.is_active = is_active
        config.updated_at = datetime.now(UTC)

        logger.info("Integration updated: %s", integration_id)
        return config

    def delete_integration(self, integration_id: str) -> None:
        """Remove an integration configuration.

        Raises:
            KeyError: If the integration does not exist.
        """
        if integration_id not in self._configs:
            raise KeyError(f"Integration {integration_id} not found")
        del self._configs[integration_id]
        logger.info("Integration deleted: %s", integration_id)

    def get_integration(self, integration_id: str) -> IntegrationConfig:
        """Get a single integration by ID.

        Raises:
            KeyError: If not found.
        """
        config = self._configs.get(integration_id)
        if config is None:
            raise KeyError(f"Integration {integration_id} not found")
        return config

    def list_integrations(self, tenant_id: str) -> list[IntegrationConfig]:
        """List all integrations for a tenant.

        Args:
            tenant_id: Tenant identifier.

        Returns:
            List of IntegrationConfig objects for the tenant.
        """
        return [
            config
            for config in self._configs.values()
            if config.tenant_id == tenant_id
        ]

    # -- Sync operations -------------------------------------------------------

    async def sync_to_platform(
        self,
        tenant_id: str,
        platform: Platform,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Route a data sync to the correct platform adapter.

        Args:
            tenant_id: Tenant identifier.
            platform: Target platform.
            data: Data payload to sync.

        Returns:
            Sync result from the adapter.

        Raises:
            KeyError: If no integration is configured for this tenant/platform.
            ValueError: If no adapter factory is registered for the platform.
        """
        config = self._find_active_config(tenant_id, platform)

        factory = self._adapter_factories.get(platform)
        if factory is None:
            raise ValueError(f"No adapter factory registered for platform {platform.value}")

        adapter = factory(config.credentials)

        # Dispatch based on platform
        if platform == Platform.HUBSPOT:
            return await self._sync_hubspot(adapter, data)
        elif platform == Platform.SALESFORCE:
            return await self._sync_salesforce(adapter, data)
        elif platform == Platform.SLACK:
            return await self._sync_slack(adapter, data)
        else:
            raise ValueError(f"Unsupported platform: {platform.value}")

    async def test_connection(
        self,
        tenant_id: str,
        platform: Platform,
    ) -> bool:
        """Test the connection for a tenant's platform integration.

        Args:
            tenant_id: Tenant identifier.
            platform: Target platform.

        Returns:
            True if connection is successful.

        Raises:
            KeyError: If no integration is configured.
            ValueError: If no adapter factory is registered.
        """
        config = self._find_active_config(tenant_id, platform)

        factory = self._adapter_factories.get(platform)
        if factory is None:
            raise ValueError(f"No adapter factory registered for platform {platform.value}")

        adapter = factory(config.credentials)
        return await adapter.test_connection()

    # -- Internal helpers ------------------------------------------------------

    def _find_active_config(self, tenant_id: str, platform: Platform) -> IntegrationConfig:
        """Find an active integration config for a tenant/platform pair."""
        for config in self._configs.values():
            if (
                config.tenant_id == tenant_id
                and config.platform == platform
                and config.is_active
            ):
                return config
        raise KeyError(
            f"No active integration found for tenant {tenant_id} on platform {platform.value}"
        )

    @staticmethod
    async def _sync_hubspot(adapter: Any, data: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a HubSpot sync operation."""
        action = data.get("action", "push_metrics")
        if action == "push_metrics":
            company_id = data["company_id"]
            return await adapter.push_lumina_metrics(
                company_id,
                avs_score=data.get("avs_score"),
                citation_frequency=data.get("citation_frequency"),
                geo_score=data.get("geo_score"),
            )
        elif action == "create_contact":
            return await adapter.create_contact(
                data["email"], data.get("properties", {})
            )
        else:
            raise ValueError(f"Unknown HubSpot action: {action}")

    @staticmethod
    async def _sync_salesforce(adapter: Any, data: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a Salesforce sync operation."""
        action = data.get("action", "sync_brand")
        if action == "sync_brand":
            return await adapter.sync_brand_data(
                brand_id=data["brand_id"],
                brand_name=data["brand_name"],
                avs_score=data.get("avs_score"),
                citation_frequency=data.get("citation_frequency"),
                geo_score=data.get("geo_score"),
            )
        elif action == "create_task":
            return await adapter.create_recommendation_task(
                owner_id=data["owner_id"],
                subject=data["subject"],
                description=data["description"],
                priority=data.get("priority", "Normal"),
            )
        else:
            raise ValueError(f"Unknown Salesforce action: {action}")

    @staticmethod
    async def _sync_slack(adapter: Any, data: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a Slack sync operation."""
        action = data.get("action", "post_summary")
        if action == "post_summary":
            return await adapter.post_avs_summary(
                brand_id=data["brand_id"],
                avs_score=data["avs_score"],
                delta=data.get("delta", 0.0),
                period=data.get("period", "daily"),
                components=data.get("components"),
            )
        else:
            raise ValueError(f"Unknown Slack action: {action}")
