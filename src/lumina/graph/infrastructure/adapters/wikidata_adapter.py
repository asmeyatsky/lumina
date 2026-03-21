"""
Wikidata Adapter — Implements WikidataPort

Architectural Intent:
- Infrastructure adapter for Wikidata entity alignment
- Uses httpx async client to call the Wikidata REST / SPARQL API
- All Wikidata-specific parsing is encapsulated here
"""

from __future__ import annotations

import httpx

from lumina.graph.domain.entities import EntityProfile


_WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
_WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"


class WikidataAdapter:
    """httpx-based implementation of WikidataPort."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_entity(self, name: str) -> dict | None:
        """Search Wikidata for an entity by name using the wbsearchentities action."""
        params = {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "format": "json",
            "limit": "1",
        }
        response = await self._client.get(_WIKIDATA_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        results = data.get("search", [])
        if not results:
            return None

        hit = results[0]
        return {
            "id": hit.get("id", ""),
            "label": hit.get("label", ""),
            "description": hit.get("description", ""),
        }

    async def get_entity_data(self, wikidata_id: str) -> dict:
        """Fetch structured data for a Wikidata entity via SPARQL."""
        sparql_query = f"""
        SELECT ?propertyLabel ?valueLabel WHERE {{
            wd:{wikidata_id} ?prop ?statement .
            ?statement ?ps ?value .
            ?property wikibase:claim ?prop .
            ?property wikibase:statementProperty ?ps .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 100
        """
        params = {"query": sparql_query, "format": "json"}
        headers = {"Accept": "application/sparql-results+json"}
        response = await self._client.get(
            _WIKIDATA_SPARQL_URL, params=params, headers=headers
        )
        response.raise_for_status()
        data = response.json()

        result: dict[str, str] = {}
        bindings = data.get("results", {}).get("bindings", [])
        for binding in bindings:
            prop_label = binding.get("propertyLabel", {}).get("value", "")
            value_label = binding.get("valueLabel", {}).get("value", "")
            if prop_label and value_label:
                result[prop_label] = value_label

        return result

    async def check_alignment(
        self,
        profile: EntityProfile,
        wikidata_data: dict,
    ) -> list[str]:
        """Compare profile identity data against Wikidata, returning mismatches."""
        mismatches: list[str] = []

        # Build a flat dict from the profile's identity dimension
        profile_data: dict[str, str] = {}
        for dim in profile.dimensions:
            profile_data.update(dim.data_as_dict)

        # Normalised comparison keys — we check common fields
        comparisons = [
            ("name", "name"),
            ("description", "description"),
            ("country", "country"),
            ("inception", "inception"),
            ("official_website", "official website"),
            ("industry", "industry"),
        ]

        for profile_key, wikidata_key in comparisons:
            profile_val = profile_data.get(profile_key, "").strip().lower()
            wikidata_val = str(wikidata_data.get(wikidata_key, "")).strip().lower()

            if not profile_val or not wikidata_val:
                continue

            if profile_val != wikidata_val:
                mismatches.append(
                    f"'{profile_key}' mismatch: profile='{profile_data.get(profile_key, '')}' "
                    f"vs wikidata='{wikidata_data.get(wikidata_key, '')}'"
                )

        return mismatches
