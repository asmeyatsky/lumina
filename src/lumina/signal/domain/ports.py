"""
SIGNAL Domain Ports — Protocol interfaces for infrastructure adapters

Architectural Intent:
- Domain layer defines what it needs via Protocol interfaces
- Infrastructure layer provides concrete implementations
- Application layer wires ports to adapters at composition root
- No domain code ever imports from infrastructure
"""

from __future__ import annotations

from typing import Protocol

from lumina.signal.domain.entities import (
    CitationSurface,
    DistributionPlan,
    PRBrief,
)


class SignalRepositoryPort(Protocol):
    """Persistence port for the SIGNAL bounded context."""

    async def save_plan(self, plan: DistributionPlan) -> None:
        """Persist a distribution plan (insert or update)."""
        ...

    async def get_plan(self, plan_id: str) -> DistributionPlan | None:
        """Retrieve a distribution plan by its identifier."""
        ...

    async def list_plans_for_brand(self, brand_id: str) -> list[DistributionPlan]:
        """List all distribution plans for a given brand."""
        ...

    async def save_surface(self, surface: CitationSurface) -> None:
        """Persist a citation surface record."""
        ...

    async def get_surfaces_for_brand(self, brand_id: str) -> list[CitationSurface]:
        """Retrieve all known citation surfaces associated with a brand."""
        ...

    async def save_pr_brief(self, brief: PRBrief) -> None:
        """Persist a PR brief."""
        ...

    async def get_pr_briefs_for_brand(self, brand_id: str) -> list[PRBrief]:
        """Retrieve all PR briefs for a given brand."""
        ...


class StructuredDataSubmissionPort(Protocol):
    """Port for submitting structured data to search engine consoles."""

    async def submit_to_google_search_console(self, json_ld: str) -> bool:
        """Submit a JSON-LD document to Google Search Console.

        Returns True if the submission was accepted.
        """
        ...

    async def submit_to_bing_webmaster(self, json_ld: str) -> bool:
        """Submit a JSON-LD document to Bing Webmaster Tools.

        Returns True if the submission was accepted.
        """
        ...


class ContentSyndicationPort(Protocol):
    """Port for syndicating content to external platforms."""

    async def syndicate_to_platform(self, platform: str, content: str) -> str:
        """Syndicate content to a named platform.

        Returns the URL where the content was published.
        """
        ...


class WikidataSubmissionPort(Protocol):
    """Port for creating and updating Wikidata entities."""

    async def create_entity(self, data: dict[str, str]) -> str:
        """Create a new Wikidata entity.

        Returns the Wikidata entity ID (e.g. 'Q12345').
        """
        ...

    async def update_entity(self, wikidata_id: str, data: dict[str, str]) -> bool:
        """Update an existing Wikidata entity.

        Returns True if the update was successful.
        """
        ...
