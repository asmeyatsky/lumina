"""
HubSpot Adapter — Syncs LUMINA brand data to HubSpot CRM.

Architectural Intent:
- Uses HubSpot CRM API v3 via httpx for contact, company, and deal management
- Pushes LUMINA metrics (AVS, citation frequency, GEO score) as custom properties
- Creates timeline events for significant metric changes
- Supports OAuth 2.0 authentication flow
- Built-in rate limiter (100 requests per 10 seconds)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("lumina.integrations.hubspot")

_HUBSPOT_API_BASE = "https://api.hubapi.com"


class _HubSpotRateLimiter:
    """Token-bucket rate limiter for HubSpot API (100 req / 10s)."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 10.0) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        while True:
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < self._window]
            if len(self._timestamps) < self._max_requests:
                self._timestamps.append(now)
                return
            wait_time = self._window - (now - self._timestamps[0]) + 0.1
            logger.debug("HubSpot rate limit — sleeping %.1fs", wait_time)
            await asyncio.sleep(wait_time)


class HubSpotAdapter:
    """HubSpot CRM integration adapter.

    Attributes:
        access_token: OAuth 2.0 access token.
        refresh_token: OAuth 2.0 refresh token for automatic renewal.
        client_id: OAuth application client ID.
        client_secret: OAuth application client secret.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        access_token: str,
        *,
        refresh_token: str = "",
        client_id: str = "",
        client_secret: str = "",
        timeout: float = 15.0,
    ) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._rate_limiter = _HubSpotRateLimiter()

    # -- Contact operations ----------------------------------------------------

    async def create_contact(self, email: str, properties: dict[str, str]) -> dict[str, Any]:
        """Create a new HubSpot contact.

        Args:
            email: Contact email address.
            properties: Additional contact properties (firstname, lastname, etc.).

        Returns:
            The created contact object from HubSpot.
        """
        props = {"email": email, **properties}
        payload = {"properties": props}
        return await self._api_post("/crm/v3/objects/contacts", payload)

    async def update_contact(self, contact_id: str, properties: dict[str, str]) -> dict[str, Any]:
        """Update an existing HubSpot contact.

        Args:
            contact_id: HubSpot contact ID.
            properties: Properties to update.

        Returns:
            The updated contact object.
        """
        payload = {"properties": properties}
        return await self._api_patch(f"/crm/v3/objects/contacts/{contact_id}", payload)

    async def search_contact_by_email(self, email: str) -> dict[str, Any] | None:
        """Search for a contact by email address.

        Returns:
            The contact object if found, None otherwise.
        """
        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "email", "operator": "EQ", "value": email}
                    ]
                }
            ],
            "limit": 1,
        }
        result = await self._api_post("/crm/v3/objects/contacts/search", payload)
        results = result.get("results", [])
        return results[0] if results else None

    # -- Company operations ----------------------------------------------------

    async def create_company(self, name: str, properties: dict[str, str]) -> dict[str, Any]:
        """Create a new HubSpot company."""
        props = {"name": name, **properties}
        payload = {"properties": props}
        return await self._api_post("/crm/v3/objects/companies", payload)

    async def update_company(self, company_id: str, properties: dict[str, str]) -> dict[str, Any]:
        """Update an existing HubSpot company."""
        payload = {"properties": properties}
        return await self._api_patch(f"/crm/v3/objects/companies/{company_id}", payload)

    # -- Deal operations -------------------------------------------------------

    async def create_deal(self, name: str, properties: dict[str, str]) -> dict[str, Any]:
        """Create a new HubSpot deal."""
        props = {"dealname": name, **properties}
        payload = {"properties": props}
        return await self._api_post("/crm/v3/objects/deals", payload)

    # -- LUMINA-specific sync --------------------------------------------------

    async def push_lumina_metrics(
        self,
        company_id: str,
        *,
        avs_score: float | None = None,
        citation_frequency: float | None = None,
        geo_score: float | None = None,
    ) -> dict[str, Any]:
        """Push LUMINA metrics as custom properties on a HubSpot company.

        Custom properties must be created in HubSpot first:
          - lumina_avs_score (number)
          - lumina_citation_frequency (number)
          - lumina_geo_score (number)
        """
        properties: dict[str, str] = {}
        if avs_score is not None:
            properties["lumina_avs_score"] = str(avs_score)
        if citation_frequency is not None:
            properties["lumina_citation_frequency"] = str(citation_frequency)
        if geo_score is not None:
            properties["lumina_geo_score"] = str(geo_score)

        if not properties:
            return {}

        return await self.update_company(company_id, properties)

    async def create_timeline_event(
        self,
        object_type: str,
        object_id: str,
        event_template_id: str,
        tokens: dict[str, str],
    ) -> dict[str, Any]:
        """Create a timeline event on a HubSpot object.

        This uses HubSpot's Timeline Events API to record significant changes
        (e.g. AVS drop, citation surge) directly on the CRM record.

        Args:
            object_type: HubSpot object type (contacts, companies, deals).
            object_id: The CRM object ID.
            event_template_id: ID of the timeline event template.
            tokens: Key-value pairs to fill the template.

        Returns:
            The created timeline event.
        """
        payload = {
            "eventTemplateId": event_template_id,
            "objectId": object_id,
            "tokens": tokens,
        }
        return await self._api_post(
            f"/crm/v3/timeline/events",
            payload,
        )

    # -- OAuth 2.0 support ----------------------------------------------------

    async def refresh_access_token(self) -> str:
        """Exchange the refresh token for a new access token.

        Returns:
            The new access token.
        """
        if not self._refresh_token:
            raise ValueError("No refresh token configured")

        payload = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{_HUBSPOT_API_BASE}/oauth/v1/token",
                data=payload,
            )
            response.raise_for_status()
            data = response.json()

        self._access_token = data["access_token"]
        if "refresh_token" in data:
            self._refresh_token = data["refresh_token"]

        logger.info("HubSpot access token refreshed")
        return self._access_token

    async def test_connection(self) -> bool:
        """Validate that the current credentials are working."""
        try:
            await self._api_get("/crm/v3/objects/contacts", params={"limit": "1"})
            return True
        except Exception as exc:
            logger.warning("HubSpot connection test failed: %s", exc)
            return False

    # -- HTTP helpers ----------------------------------------------------------

    async def _api_get(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        await self._rate_limiter.acquire()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{_HUBSPOT_API_BASE}{path}",
                headers=self._headers(),
                params=params or {},
            )
            if response.status_code == 401 and self._refresh_token:
                await self.refresh_access_token()
                response = await client.get(
                    f"{_HUBSPOT_API_BASE}{path}",
                    headers=self._headers(),
                    params=params or {},
                )
            response.raise_for_status()
            return response.json()

    async def _api_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self._rate_limiter.acquire()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{_HUBSPOT_API_BASE}{path}",
                headers=self._headers(),
                json=payload,
            )
            if response.status_code == 401 and self._refresh_token:
                await self.refresh_access_token()
                response = await client.post(
                    f"{_HUBSPOT_API_BASE}{path}",
                    headers=self._headers(),
                    json=payload,
                )
            response.raise_for_status()
            return response.json()

    async def _api_patch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self._rate_limiter.acquire()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.patch(
                f"{_HUBSPOT_API_BASE}{path}",
                headers=self._headers(),
                json=payload,
            )
            if response.status_code == 401 and self._refresh_token:
                await self.refresh_access_token()
                response = await client.patch(
                    f"{_HUBSPOT_API_BASE}{path}",
                    headers=self._headers(),
                    json=payload,
                )
            response.raise_for_status()
            return response.json()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
