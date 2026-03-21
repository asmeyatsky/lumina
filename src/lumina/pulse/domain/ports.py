"""
PULSE Domain Ports — Protocol interfaces for infrastructure adapters

Architectural Intent:
- Ports define the contracts that infrastructure must satisfy
- The domain layer depends only on these protocols, never on concrete implementations
- Each port models a specific infrastructure capability needed by PULSE
"""

from __future__ import annotations

from typing import Protocol, Optional

from lumina.pulse.domain.entities import (
    Citation,
    CitationResult,
    MonitoringRun,
    PromptBattery,
)


class PulseRepositoryPort(Protocol):
    """Persistence port for PULSE aggregates.

    Provides fine-grained persistence operations beyond the generic
    RepositoryPort — tailored to the MonitoringRun and PromptBattery
    aggregate lifecycle.
    """

    async def save_run(self, run: MonitoringRun) -> None:
        """Persist a monitoring run (insert or update)."""
        ...

    async def get_run(self, run_id: str) -> Optional[MonitoringRun]:
        """Retrieve a monitoring run by its identifier."""
        ...

    async def list_runs_for_brand(
        self, brand_id: str, limit: int = 50
    ) -> list[MonitoringRun]:
        """List recent monitoring runs for a brand, most recent first."""
        ...

    async def save_battery(self, battery: PromptBattery) -> None:
        """Persist a prompt battery (insert or update)."""
        ...

    async def get_battery(self, battery_id: str) -> Optional[PromptBattery]:
        """Retrieve a prompt battery by its identifier."""
        ...

    async def list_batteries_for_brand(
        self, brand_id: str
    ) -> list[PromptBattery]:
        """List all prompt batteries belonging to a brand."""
        ...


class AlertPort(Protocol):
    """Port for sending operational alerts about citation changes.

    Infrastructure adapters may implement this via email, Slack,
    webhooks, or any notification channel.
    """

    async def send_citation_drop_alert(
        self,
        brand_id: str,
        engine: str,
        prompt_text: str,
        previous_position: str,
    ) -> None:
        """Alert when a brand loses a citation position."""
        ...

    async def send_hallucination_alert(
        self,
        brand_id: str,
        engine: str,
        claim: str,
        prompt_text: str,
    ) -> None:
        """Alert when an AI engine produces a hallucinated claim about a brand."""
        ...

    async def send_competitor_surge_alert(
        self,
        brand_id: str,
        competitor_id: str,
        engine: str,
        surge_percentage: float,
    ) -> None:
        """Alert when a competitor's citation rate surges significantly."""
        ...


class CitationNLPPort(Protocol):
    """Port for ML-based citation extraction.

    Provides a higher-accuracy alternative to the rule-based
    CitationExtractionService. Infrastructure adapters may call
    an NLP model or external API.
    """

    async def extract_citations_ml(
        self,
        response: str,
        brand: str,
        competitors: tuple[str, ...],
    ) -> list[Citation]:
        """Extract citations using ML-based NLP analysis."""
        ...
