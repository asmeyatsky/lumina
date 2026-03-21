"""
Prompt Battery Library Manager

Architectural Intent:
- Loads pre-built prompt batteries from vertical modules
- Provides lookup, filtering, and customization of batteries
- Substitutes {brand}, {competitor_1}, {competitor_2} placeholders
- Stateless after construction — all state lives in the vertical modules
"""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from lumina.pulse.domain.entities import PromptBattery, PromptTemplate
from lumina.shared.domain.value_objects import BrandId

from lumina.infrastructure.prompt_library.verticals.saas import SAAS_TEMPLATES
from lumina.infrastructure.prompt_library.verticals.fintech import FINTECH_TEMPLATES
from lumina.infrastructure.prompt_library.verticals.healthtech import HEALTHTECH_TEMPLATES
from lumina.infrastructure.prompt_library.verticals.ecommerce import ECOMMERCE_TEMPLATES
from lumina.infrastructure.prompt_library.verticals.cloud import CLOUD_TEMPLATES


_VERTICAL_REGISTRY: dict[str, tuple[PromptTemplate, ...]] = {
    "saas": SAAS_TEMPLATES,
    "fintech": FINTECH_TEMPLATES,
    "healthtech": HEALTHTECH_TEMPLATES,
    "ecommerce": ECOMMERCE_TEMPLATES,
    "cloud": CLOUD_TEMPLATES,
}


class PromptLibrary:
    """Loads and serves pre-built prompt batteries for GEO monitoring.

    Each vertical ships a curated set of :class:`PromptTemplate` instances.
    The library assembles them into :class:`PromptBattery` objects, optionally
    substituting brand and competitor placeholders.
    """

    def __init__(self) -> None:
        self._verticals = dict(_VERTICAL_REGISTRY)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_battery_for_vertical(
        self,
        vertical: str,
        brand_name: str,
    ) -> PromptBattery:
        """Return a prompt battery for the given *vertical*, pre-filled with
        the supplied *brand_name*.

        Raises :class:`ValueError` if the vertical is unknown.
        """
        templates = self._get_templates(vertical)

        # Substitute {brand} only — competitors are filled via customize_battery
        filled = tuple(
            replace(t, text=t.text.replace("{brand}", brand_name))
            for t in templates
        )

        return PromptBattery(
            id=str(uuid4()),
            brand_id=BrandId(brand_name),
            name=f"{vertical} monitoring battery",
            prompts=filled,
            vertical=vertical,
            schedule_cron="0 6 * * *",  # daily at 06:00 UTC
        )

    def get_all_verticals(self) -> list[str]:
        """Return the names of every registered vertical."""
        return sorted(self._verticals.keys())

    def get_templates_by_category(self, category: str) -> list[PromptTemplate]:
        """Return all templates across all verticals that match *category*."""
        results: list[PromptTemplate] = []
        for templates in self._verticals.values():
            for t in templates:
                if t.category == category:
                    results.append(t)
        return results

    def customize_battery(
        self,
        battery: PromptBattery,
        brand_name: str,
        competitors: list[str] | None = None,
    ) -> PromptBattery:
        """Return a copy of *battery* with placeholders substituted.

        Supported placeholders:
        - ``{brand}`` — replaced with *brand_name*
        - ``{competitor_1}`` — replaced with *competitors[0]* (if provided)
        - ``{competitor_2}`` — replaced with *competitors[1]* (if provided)

        Missing competitors are replaced with a descriptive fallback such as
        ``"leading alternative"`` so that prompts remain usable.
        """
        competitors = competitors or []
        comp_1 = competitors[0] if len(competitors) > 0 else "leading alternative"
        comp_2 = competitors[1] if len(competitors) > 1 else "another competitor"

        customized: list[PromptTemplate] = []
        for t in battery.prompts:
            new_text = (
                t.text
                .replace("{brand}", brand_name)
                .replace("{competitor_1}", comp_1)
                .replace("{competitor_2}", comp_2)
            )
            customized.append(replace(t, text=new_text))

        return replace(
            battery,
            prompts=tuple(customized),
            brand_id=BrandId(brand_name),
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_templates(self, vertical: str) -> tuple[PromptTemplate, ...]:
        templates = self._verticals.get(vertical)
        if templates is None:
            available = ", ".join(sorted(self._verticals.keys()))
            raise ValueError(
                f"Unknown vertical '{vertical}'. Available: {available}"
            )
        return templates
