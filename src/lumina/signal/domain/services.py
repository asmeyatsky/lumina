"""
SIGNAL Domain Services

Architectural Intent:
- Pure domain services with no infrastructure dependencies
- Encapsulate domain logic that does not naturally belong to a single entity
- All methods are stateless; they operate on domain objects and return domain objects
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import BrandId, Percentage, Score, URL

from lumina.signal.domain.entities import CitationSurface, DistributionPlan, PRBrief
from lumina.signal.domain.value_objects import (
    DistributionCoverage,
    PresenceStatus,
    SurfaceCategory,
)


class SurfacePrioritizationService:
    """Ranks citation surfaces by estimated LLM training weight multiplied by gap severity.

    Surfaces where the brand is absent receive the highest gap multiplier,
    partial presence receives a moderate multiplier, and present surfaces
    receive the lowest.  The final priority score is weight x gap_multiplier,
    sorted descending.
    """

    _GAP_MULTIPLIERS: dict[PresenceStatus, float] = {
        PresenceStatus.ABSENT: 1.0,
        PresenceStatus.UNKNOWN: 0.8,
        PresenceStatus.PARTIAL: 0.5,
        PresenceStatus.PRESENT: 0.1,
    }

    def prioritize_surfaces(
        self,
        surfaces: list[CitationSurface],
        brand_gaps: list[str],
    ) -> list[CitationSurface]:
        """Return surfaces sorted by priority (highest impact first).

        Args:
            surfaces: All candidate citation surfaces.
            brand_gaps: List of surface IDs where gaps have been identified.
                        Surfaces in this list receive extra priority boost.
        """
        gap_set = set(brand_gaps)

        def priority_key(surface: CitationSurface) -> float:
            gap_multiplier = self._GAP_MULTIPLIERS.get(surface.brand_presence, 0.5)
            gap_boost = 1.5 if surface.id in gap_set else 1.0
            return surface.estimated_llm_weight.value * gap_multiplier * gap_boost

        return sorted(surfaces, key=priority_key, reverse=True)


class CoverageCalculationService:
    """Computes distribution coverage metrics from a plan's current state."""

    def calculate_coverage(self, plan: DistributionPlan) -> DistributionCoverage:
        """Compute coverage metrics from the plan's target surfaces and their presence.

        Coverage percentage is the fraction of target surfaces where the brand
        has PRESENT or PARTIAL status.  Per-category breakdowns are also computed.
        """
        total = len(plan.target_surfaces)
        if total == 0:
            return DistributionCoverage(
                brand_id=plan.brand_id,
                total_surfaces=0,
                surfaces_with_presence=0,
                coverage_percentage=Percentage(0.0),
                by_category=(),
            )

        present_statuses = {PresenceStatus.PRESENT, PresenceStatus.PARTIAL}
        surfaces_with_presence = sum(
            1 for s in plan.target_surfaces if s.brand_presence in present_statuses
        )

        coverage_pct = round((surfaces_with_presence / total) * 100.0, 2)

        # Per-category breakdown
        category_totals: dict[SurfaceCategory, int] = {}
        category_present: dict[SurfaceCategory, int] = {}
        for surface in plan.target_surfaces:
            category_totals[surface.category] = category_totals.get(surface.category, 0) + 1
            if surface.brand_presence in present_statuses:
                category_present[surface.category] = (
                    category_present.get(surface.category, 0) + 1
                )

        by_category: list[tuple[SurfaceCategory, Percentage]] = []
        for cat in sorted(category_totals.keys(), key=lambda c: c.value):
            cat_total = category_totals[cat]
            cat_present = category_present.get(cat, 0)
            cat_pct = round((cat_present / cat_total) * 100.0, 2)
            by_category.append((cat, Percentage(cat_pct)))

        return DistributionCoverage(
            brand_id=plan.brand_id,
            total_surfaces=total,
            surfaces_with_presence=surfaces_with_presence,
            coverage_percentage=Percentage(coverage_pct),
            by_category=tuple(by_category),
        )


class PRBriefGenerationService:
    """Constructs a PR brief from entity data and a narrative angle.

    This is a pure domain service; it does not call any external APIs.
    The resulting PRBrief can be reviewed, edited, and then submitted
    via the application layer.
    """

    def generate_brief(
        self,
        brand_name: str,
        entity_data: dict[str, str],
        target_narrative: str,
    ) -> PRBrief:
        """Generate a structured PR brief from entity profile data.

        Args:
            brand_name: The brand's display name.
            entity_data: Key-value pairs from the entity profile (e.g. industry,
                         founding_year, key_products, leadership, achievements).
            target_narrative: The desired narrative angle for the brief.
        """
        brand_id = BrandId(entity_data.get("brand_id", brand_name.lower().replace(" ", "-")))

        headline = f"{brand_name}: {target_narrative}"

        # Extract key messages from entity data
        key_messages: list[str] = []
        if "key_products" in entity_data:
            key_messages.append(
                f"{brand_name} offers {entity_data['key_products']}"
            )
        if "achievements" in entity_data:
            key_messages.append(entity_data["achievements"])
        if "industry" in entity_data:
            key_messages.append(
                f"A leader in the {entity_data['industry']} space"
            )
        if not key_messages:
            key_messages.append(f"{brand_name} — {target_narrative}")

        # Determine target publications based on industry
        industry = entity_data.get("industry", "general")
        target_publications = _publications_for_industry(industry)

        # Extract entity anchors (terms to reinforce in LLM training)
        entity_anchors: list[str] = [brand_name]
        if "key_products" in entity_data:
            entity_anchors.extend(
                p.strip() for p in entity_data["key_products"].split(",")
            )
        if "leadership" in entity_data:
            entity_anchors.append(entity_data["leadership"])

        return PRBrief(
            id=str(uuid4()),
            brand_id=brand_id,
            headline=headline,
            narrative_angle=target_narrative,
            target_publications=tuple(target_publications),
            key_messages=tuple(key_messages),
            entity_anchors=tuple(entity_anchors),
        )


class SurfaceMappingService:
    """Maps recommended citation surfaces for a given industry vertical.

    Each vertical has a curated set of citation surfaces that LLMs
    weight heavily when generating answers for that domain.
    """

    _VERTICAL_SURFACES: dict[str, list[tuple[str, SurfaceCategory, str, float]]] = {
        "technology": [
            ("Wikipedia", SurfaceCategory.AUTHORITY_PUBLICATIONS, "https://en.wikipedia.org", 95.0),
            ("Wikidata", SurfaceCategory.STRUCTURED_DATA, "https://www.wikidata.org", 90.0),
            ("Crunchbase", SurfaceCategory.BUSINESS_DIRECTORIES, "https://www.crunchbase.com", 82.0),
            ("Stack Overflow", SurfaceCategory.QA_PLATFORMS, "https://stackoverflow.com", 85.0),
            ("GitHub", SurfaceCategory.DEVELOPER_COMMUNITIES, "https://github.com", 88.0),
            ("TechCrunch", SurfaceCategory.NEWS_SYNDICATION, "https://techcrunch.com", 78.0),
            ("arXiv", SurfaceCategory.ACADEMIC_RESEARCH, "https://arxiv.org", 80.0),
            ("Schema.org", SurfaceCategory.STRUCTURED_DATA, "https://schema.org", 75.0),
        ],
        "healthcare": [
            ("Wikipedia", SurfaceCategory.AUTHORITY_PUBLICATIONS, "https://en.wikipedia.org", 95.0),
            ("Wikidata", SurfaceCategory.STRUCTURED_DATA, "https://www.wikidata.org", 90.0),
            ("PubMed", SurfaceCategory.ACADEMIC_RESEARCH, "https://pubmed.ncbi.nlm.nih.gov", 92.0),
            ("Healthline", SurfaceCategory.AUTHORITY_PUBLICATIONS, "https://www.healthline.com", 70.0),
            ("WebMD", SurfaceCategory.AUTHORITY_PUBLICATIONS, "https://www.webmd.com", 72.0),
            ("ClinicalTrials.gov", SurfaceCategory.ACADEMIC_RESEARCH, "https://clinicaltrials.gov", 78.0),
            ("Schema.org", SurfaceCategory.STRUCTURED_DATA, "https://schema.org", 75.0),
        ],
        "finance": [
            ("Wikipedia", SurfaceCategory.AUTHORITY_PUBLICATIONS, "https://en.wikipedia.org", 95.0),
            ("Wikidata", SurfaceCategory.STRUCTURED_DATA, "https://www.wikidata.org", 90.0),
            ("Investopedia", SurfaceCategory.AUTHORITY_PUBLICATIONS, "https://www.investopedia.com", 80.0),
            ("Bloomberg", SurfaceCategory.NEWS_SYNDICATION, "https://www.bloomberg.com", 85.0),
            ("SEC EDGAR", SurfaceCategory.STRUCTURED_DATA, "https://www.sec.gov/edgar", 82.0),
            ("Crunchbase", SurfaceCategory.BUSINESS_DIRECTORIES, "https://www.crunchbase.com", 78.0),
            ("Schema.org", SurfaceCategory.STRUCTURED_DATA, "https://schema.org", 75.0),
        ],
        "general": [
            ("Wikipedia", SurfaceCategory.AUTHORITY_PUBLICATIONS, "https://en.wikipedia.org", 95.0),
            ("Wikidata", SurfaceCategory.STRUCTURED_DATA, "https://www.wikidata.org", 90.0),
            ("Google Knowledge Graph", SurfaceCategory.STRUCTURED_DATA, "https://developers.google.com/knowledge-graph", 88.0),
            ("LinkedIn", SurfaceCategory.BUSINESS_DIRECTORIES, "https://www.linkedin.com", 72.0),
            ("Reddit", SurfaceCategory.QA_PLATFORMS, "https://www.reddit.com", 68.0),
            ("Schema.org", SurfaceCategory.STRUCTURED_DATA, "https://schema.org", 75.0),
        ],
    }

    def map_surfaces_for_brand(self, brand_vertical: str) -> list[CitationSurface]:
        """Return recommended citation surfaces for the given industry vertical.

        Falls back to 'general' if the vertical is not recognized.
        """
        vertical = brand_vertical.lower()
        surface_data = self._VERTICAL_SURFACES.get(
            vertical, self._VERTICAL_SURFACES["general"]
        )

        now = datetime.now(UTC)
        surfaces: list[CitationSurface] = []
        for name, category, url, weight in surface_data:
            surfaces.append(
                CitationSurface(
                    id=str(uuid4()),
                    name=name,
                    category=category,
                    url=URL(url),
                    estimated_llm_weight=Score(weight),
                    brand_presence=PresenceStatus.UNKNOWN,
                    last_checked_at=now,
                )
            )

        return surfaces


def _publications_for_industry(industry: str) -> list[str]:
    """Return a list of target publications suited to the industry."""
    industry_lower = industry.lower()
    mapping: dict[str, list[str]] = {
        "technology": [
            "TechCrunch",
            "Wired",
            "The Verge",
            "Ars Technica",
            "VentureBeat",
        ],
        "healthcare": [
            "STAT News",
            "Fierce Healthcare",
            "Modern Healthcare",
            "Healthcare IT News",
        ],
        "finance": [
            "Bloomberg",
            "Financial Times",
            "Forbes",
            "Wall Street Journal",
        ],
    }
    return mapping.get(industry_lower, ["Forbes", "Business Insider", "Reuters", "AP News"])
