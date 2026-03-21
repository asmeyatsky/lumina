"""
Wikidata submission adapter.

Implements WikidataSubmissionPort using httpx for HTTP communication
with the Wikidata API (wbeditentity, wbsetclaim).
"""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"


class WikidataSubmissionAdapter:
    """Infrastructure adapter for creating and updating Wikidata entities.

    Implements WikidataSubmissionPort.

    Requires a bot username/password or OAuth credentials for the Wikidata API.
    The adapter handles login, CSRF token acquisition, and entity manipulation.
    """

    def __init__(
        self,
        username: str,
        password: str,
        timeout: float = 30.0,
    ) -> None:
        self._username = username
        self._password = password
        self._timeout = timeout

    async def _get_csrf_token(self, client: httpx.AsyncClient) -> str:
        """Authenticate and obtain a CSRF edit token from the Wikidata API."""
        # Step 1: Get login token
        login_token_response = await client.get(
            WIKIDATA_API_URL,
            params={
                "action": "query",
                "meta": "tokens",
                "type": "login",
                "format": "json",
            },
        )
        login_token_data = login_token_response.json()
        login_token = login_token_data["query"]["tokens"]["logintoken"]

        # Step 2: Log in
        await client.post(
            WIKIDATA_API_URL,
            data={
                "action": "login",
                "lgname": self._username,
                "lgpassword": self._password,
                "lgtoken": login_token,
                "format": "json",
            },
        )

        # Step 3: Get CSRF token
        csrf_response = await client.get(
            WIKIDATA_API_URL,
            params={
                "action": "query",
                "meta": "tokens",
                "format": "json",
            },
        )
        csrf_data = csrf_response.json()
        return csrf_data["query"]["tokens"]["csrftoken"]

    async def create_entity(self, data: dict[str, str]) -> str:
        """Create a new Wikidata entity with the given data.

        Args:
            data: Dictionary with entity properties. Expected keys include
                  'label', 'description', and optionally 'aliases'.

        Returns:
            The Wikidata entity ID (e.g. 'Q12345').
        """
        label = data.get("label", data.get("name", "Unknown"))
        description = data.get("description", "")
        aliases = [a.strip() for a in data.get("aliases", "").split(",") if a.strip()]

        entity_data: dict = {
            "labels": {
                "en": {"language": "en", "value": label},
            },
            "descriptions": {
                "en": {"language": "en", "value": description},
            },
        }
        if aliases:
            entity_data["aliases"] = {
                "en": [{"language": "en", "value": alias} for alias in aliases],
            }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                token = await self._get_csrf_token(client)

                response = await client.post(
                    WIKIDATA_API_URL,
                    data={
                        "action": "wbeditentity",
                        "new": "item",
                        "token": token,
                        "data": json.dumps(entity_data),
                        "format": "json",
                    },
                )
                result = response.json()

                if "entity" in result:
                    entity_id = result["entity"]["id"]
                    logger.info("Created Wikidata entity: %s", entity_id)
                    return entity_id
                else:
                    error_info = result.get("error", {}).get("info", "Unknown error")
                    logger.error("Wikidata entity creation failed: %s", error_info)
                    raise RuntimeError(f"Wikidata entity creation failed: {error_info}")

        except httpx.HTTPError as exc:
            logger.error("Wikidata HTTP error during entity creation: %s", str(exc))
            raise RuntimeError(f"Wikidata HTTP error: {exc}") from exc

    async def update_entity(self, wikidata_id: str, data: dict[str, str]) -> bool:
        """Update an existing Wikidata entity.

        Args:
            wikidata_id: The entity ID to update (e.g. 'Q12345').
            data: Dictionary with properties to update. Supports 'label',
                  'description', and 'aliases'.

        Returns:
            True if the update was successful.
        """
        update_data: dict = {}

        if "label" in data or "name" in data:
            label_val = data.get("label", data.get("name", ""))
            update_data["labels"] = {
                "en": {"language": "en", "value": label_val},
            }

        if "description" in data:
            update_data["descriptions"] = {
                "en": {"language": "en", "value": data["description"]},
            }

        if "aliases" in data:
            aliases = [a.strip() for a in data["aliases"].split(",") if a.strip()]
            update_data["aliases"] = {
                "en": [{"language": "en", "value": alias} for alias in aliases],
            }

        if not update_data:
            logger.warning("No updatable fields provided for %s", wikidata_id)
            return False

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                token = await self._get_csrf_token(client)

                response = await client.post(
                    WIKIDATA_API_URL,
                    data={
                        "action": "wbeditentity",
                        "id": wikidata_id,
                        "token": token,
                        "data": json.dumps(update_data),
                        "format": "json",
                    },
                )
                result = response.json()

                if "success" in result:
                    logger.info("Updated Wikidata entity: %s", wikidata_id)
                    return True
                else:
                    error_info = result.get("error", {}).get("info", "Unknown error")
                    logger.warning(
                        "Wikidata entity update failed for %s: %s",
                        wikidata_id,
                        error_info,
                    )
                    return False

        except httpx.HTTPError as exc:
            logger.error(
                "Wikidata HTTP error during entity update of %s: %s",
                wikidata_id,
                str(exc),
            )
            return False
