"""
GRAPH Domain Ports

Architectural Intent:
- Protocol-based interfaces that the domain declares and the infrastructure implements
- No concrete imports from infrastructure — dependency inversion in action
- The application layer wires concrete adapters to these ports
"""

from __future__ import annotations

from typing import Protocol

from lumina.graph.domain.entities import EntityProfile, KnowledgeGap
from lumina.graph.domain.value_objects import JsonLdDocument


class GraphRepositoryPort(Protocol):
    """Persistence port for entity profiles and knowledge gaps."""

    async def save_profile(self, profile: EntityProfile) -> None:
        """Persist (upsert) an entity profile."""
        ...

    async def get_profile(self, profile_id: str) -> EntityProfile | None:
        """Retrieve a profile by its unique identifier."""
        ...

    async def list_profiles_for_brand(self, brand_id: str) -> list[EntityProfile]:
        """Return all profiles associated with a brand."""
        ...

    async def save_gap(self, gap: KnowledgeGap) -> None:
        """Persist a knowledge gap record."""
        ...

    async def get_gaps_for_brand(self, brand_id: str) -> list[KnowledgeGap]:
        """Return all knowledge gaps for a brand, ordered by severity."""
        ...


class WikidataPort(Protocol):
    """External service port for Wikidata entity alignment."""

    async def search_entity(self, name: str) -> dict | None:
        """Search Wikidata for an entity by name.

        Returns a dict with at least ``{"id": "Q...", "label": "...", "description": "..."}``
        or ``None`` if no match is found.
        """
        ...

    async def get_entity_data(self, wikidata_id: str) -> dict:
        """Fetch structured entity data from Wikidata by QID.

        Returns a dict of property-label to value mappings.
        """
        ...

    async def check_alignment(
        self,
        profile: EntityProfile,
        wikidata_data: dict,
    ) -> list[str]:
        """Compare the profile against Wikidata data.

        Returns a list of mismatch descriptions (empty list means full alignment).
        """
        ...


class SchemaValidatorPort(Protocol):
    """External validation port for JSON-LD documents."""

    async def validate_json_ld(
        self,
        document: JsonLdDocument,
    ) -> tuple[bool, list[str]]:
        """Validate a JSON-LD document against schema.org.

        Returns ``(is_valid, list_of_errors)``.
        """
        ...
