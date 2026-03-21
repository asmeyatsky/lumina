"""
Agency Pure Domain Services

Architectural Intent:
- Stateless, pure functions encapsulating domain logic
- No I/O, no side effects — only domain computations
- Operate exclusively on domain entities and value objects
"""

from __future__ import annotations

import re
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import Score

from lumina.intelligence.domain.entities import AIVisibilityScore, Recommendation

from lumina.agency.domain.entities import ClientReport, WhiteLabelConfig
from lumina.agency.domain.value_objects import (
    ClientOverview,
    PortfolioSummary,
    ReportType,
)


class PortfolioAnalysisService:
    """Pure domain service for analysing an agency's client portfolio."""

    @staticmethod
    def generate_portfolio_summary(
        client_scores: dict[str, AIVisibilityScore],
    ) -> PortfolioSummary:
        """Generate a summary of the entire agency portfolio.

        Args:
            client_scores: Mapping of brand name to their latest AIVisibilityScore.

        Returns:
            A PortfolioSummary value object with aggregate metrics.
        """
        if not client_scores:
            return PortfolioSummary(
                agency_id="",
                total_clients=0,
                avg_avs=Score(0.0),
                clients_improving=0,
                clients_declining=0,
                top_performer="",
                needs_attention=[],
            )

        total_clients = len(client_scores)
        scores_sum = sum(avs.overall.value for avs in client_scores.values())
        avg_score = round(scores_sum / total_clients, 2)

        clients_improving = 0
        clients_declining = 0
        needs_attention: list[str] = []
        top_performer = ""
        top_score = -1.0

        for brand_name, avs in client_scores.items():
            delta = avs.calculate_delta()
            if delta > 0:
                clients_improving += 1
            elif delta < 0:
                clients_declining += 1

            if avs.overall.value > top_score:
                top_score = avs.overall.value
                top_performer = brand_name

            # Flag brands with low scores or significant declines
            if avs.overall.value < 40.0 or delta < -5.0:
                needs_attention.append(brand_name)

        # Extract agency_id from the first AVS brand_id prefix if available
        first_avs = next(iter(client_scores.values()))
        agency_id = first_avs.brand_id.split(":")[0] if ":" in first_avs.brand_id else ""

        return PortfolioSummary(
            agency_id=agency_id,
            total_clients=total_clients,
            avg_avs=Score(avg_score),
            clients_improving=clients_improving,
            clients_declining=clients_declining,
            top_performer=top_performer,
            needs_attention=needs_attention,
        )

    @staticmethod
    def identify_at_risk_clients(
        client_scores: dict[str, AIVisibilityScore],
        threshold: float = 5.0,
    ) -> list[str]:
        """Identify client brands whose AVS has declined beyond the threshold.

        Args:
            client_scores: Mapping of brand name to their latest AIVisibilityScore.
            threshold: The minimum absolute decline to flag (default 5.0 points).

        Returns:
            List of brand names with AVS decline exceeding the threshold.
        """
        at_risk: list[str] = []
        for brand_name, avs in client_scores.items():
            delta = avs.calculate_delta()
            if delta < -threshold:
                at_risk.append(brand_name)
        return at_risk

    @staticmethod
    def rank_clients_by_performance(
        client_scores: dict[str, AIVisibilityScore],
    ) -> list[ClientOverview]:
        """Rank all clients by their current AVS score (highest first).

        Args:
            client_scores: Mapping of brand name to their latest AIVisibilityScore.

        Returns:
            Sorted list of ClientOverview value objects.
        """
        overviews: list[ClientOverview] = []
        for brand_name, avs in client_scores.items():
            delta = avs.calculate_delta()
            # Extract top recommendation hint from the lowest scoring component
            lowest_component = (
                min(avs.components, key=lambda c: c.score.value)
                if avs.components
                else None
            )
            top_recommendation = (
                f"Improve {lowest_component.module_name} score"
                if lowest_component
                else "No data available"
            )

            overviews.append(
                ClientOverview(
                    brand_id=avs.brand_id,
                    brand_name=brand_name,
                    avs_score=avs.overall,
                    avs_trend=delta,
                    citation_count=0,  # populated by caller with PULSE data
                    top_recommendation=top_recommendation,
                )
            )

        # Sort by AVS score descending
        overviews.sort(key=lambda o: o.avs_score.value, reverse=True)
        return overviews


class ReportGenerationService:
    """Pure domain service for generating client reports."""

    @staticmethod
    def generate_weekly_summary(
        brand_id: str,
        avs_data: AIVisibilityScore,
        citation_data: dict[str, object],
        recommendations: list[Recommendation],
        agency_id: str = "",
    ) -> ClientReport:
        """Generate a weekly summary report for a client brand.

        Args:
            brand_id: The client brand identifier.
            avs_data: The current AI Visibility Score data.
            citation_data: Citation monitoring data from PULSE.
            recommendations: Current recommendations from the Intelligence Engine.
            agency_id: The owning agency's identifier.

        Returns:
            A ClientReport entity with weekly summary data.
        """
        # Build the report data as an immutable tuple of items
        report_sections: list[tuple[str, object]] = [
            ("executive_summary", {
                "avs_score": avs_data.overall.value,
                "avs_delta": avs_data.calculate_delta(),
                "period": "weekly",
            }),
            ("avs_trend", {
                "current_score": avs_data.overall.value,
                "previous_score": (
                    avs_data.previous_score.value
                    if avs_data.previous_score
                    else None
                ),
                "components": [
                    {
                        "module": c.module_name,
                        "score": c.score.value,
                        "weight": c.weight,
                    }
                    for c in avs_data.components
                ],
            }),
            ("citation_highlights", dict(citation_data) if citation_data else {}),
            ("recommendations", [
                {
                    "action": r.action_description,
                    "impact": r.expected_avs_impact.value,
                    "effort": r.effort_level.value,
                    "priority": r.priority_rank,
                }
                for r in recommendations[:5]  # Top 5 recommendations
            ]),
            ("next_steps", [
                r.action_description for r in recommendations[:3]
            ]),
        ]

        return ClientReport(
            id=str(uuid4()),
            agency_id=agency_id,
            client_brand_id=brand_id,
            report_type=ReportType.WEEKLY_SUMMARY,
            title=f"Weekly AI Visibility Summary — {datetime.now(UTC).strftime('%B %d, %Y')}",
            generated_at=datetime.now(UTC),
            data=tuple(report_sections),
        )

    @staticmethod
    def generate_monthly_review(
        brand_id: str,
        avs_history: list[AIVisibilityScore],
        content_scores: list[dict[str, object]],
        distribution_coverage: dict[str, object],
        agency_id: str = "",
    ) -> ClientReport:
        """Generate a monthly review report for a client brand.

        Args:
            brand_id: The client brand identifier.
            avs_history: Historical AVS records for the month.
            content_scores: Content scoring data from BEAM.
            distribution_coverage: Distribution coverage data from SIGNAL.
            agency_id: The owning agency's identifier.

        Returns:
            A ClientReport entity with monthly review data.
        """
        # Calculate monthly statistics
        if avs_history:
            scores = [avs.overall.value for avs in avs_history]
            avg_score = round(sum(scores) / len(scores), 2)
            min_score = min(scores)
            max_score = max(scores)
            latest = avs_history[-1]
            earliest = avs_history[0]
            monthly_delta = latest.overall.value - earliest.overall.value
        else:
            avg_score = 0.0
            min_score = 0.0
            max_score = 0.0
            monthly_delta = 0.0

        report_sections: list[tuple[str, object]] = [
            ("executive_summary", {
                "period": "monthly",
                "avg_avs": avg_score,
                "min_avs": min_score,
                "max_avs": max_score,
                "monthly_delta": round(monthly_delta, 2),
                "data_points": len(avs_history),
            }),
            ("avs_trend_chart", {
                "data_points": [
                    {
                        "date": avs.calculated_at.isoformat(),
                        "score": avs.overall.value,
                    }
                    for avs in avs_history
                ],
            }),
            ("content_performance", {
                "total_assets_scored": len(content_scores),
                "scores": content_scores,
            }),
            ("distribution_coverage", dict(distribution_coverage)),
            ("next_steps", [
                "Continue optimising low-scoring content assets",
                "Expand distribution to uncovered AI surfaces",
                "Monitor competitor activity for strategic adjustments",
            ]),
        ]

        return ClientReport(
            id=str(uuid4()),
            agency_id=agency_id,
            client_brand_id=brand_id,
            report_type=ReportType.MONTHLY_REVIEW,
            title=f"Monthly AI Visibility Review — {datetime.now(UTC).strftime('%B %Y')}",
            generated_at=datetime.now(UTC),
            data=tuple(report_sections),
        )


class WhiteLabelService:
    """Pure domain service for white-label branding operations."""

    _HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")

    @staticmethod
    def validate_config(config: WhiteLabelConfig) -> list[str]:
        """Validate a white-label configuration and return a list of errors.

        Args:
            config: The white-label configuration to validate.

        Returns:
            A list of validation error strings. Empty list means the config is valid.
        """
        errors: list[str] = []

        if not config.company_name or not config.company_name.strip():
            errors.append("company_name is required")

        if not config.logo_url or not config.logo_url.strip():
            errors.append("logo_url is required")
        elif not config.logo_url.startswith(("http://", "https://")):
            errors.append("logo_url must start with http:// or https://")

        hex_pattern = WhiteLabelService._HEX_COLOR_PATTERN
        for color_field in ("primary_color", "secondary_color", "accent_color"):
            value = getattr(config, color_field)
            if not hex_pattern.match(value):
                errors.append(
                    f"{color_field} must be a valid hex colour (e.g. '#1a2b3c'), "
                    f"got '{value}'"
                )

        if config.email_from_address and "@" not in config.email_from_address:
            errors.append("email_from_address must be a valid email address")

        if config.custom_domain:
            if "." not in config.custom_domain:
                errors.append(
                    "custom_domain must be a valid domain (e.g. 'reports.agency.com')"
                )

        return errors

    @staticmethod
    def apply_branding(
        report_data: dict[str, object],
        config: WhiteLabelConfig,
    ) -> dict[str, object]:
        """Inject white-label branding into report data.

        Args:
            report_data: The raw report data dictionary.
            config: The white-label configuration to apply.

        Returns:
            A new dictionary with branding injected.
        """
        branded = dict(report_data)

        branded["branding"] = {
            "company_name": config.company_name,
            "logo_url": config.logo_url,
            "primary_color": config.primary_color,
            "secondary_color": config.secondary_color,
            "accent_color": config.accent_color,
            "email_from_name": config.email_from_name,
            "email_from_address": config.email_from_address,
        }

        branded["footer"] = {
            "text": config.report_footer_text,
            "powered_by_visible": config.powered_by_visible,
        }

        if config.powered_by_visible:
            branded["footer"]["powered_by_text"] = "Powered by LUMINA"

        if config.custom_domain:
            branded["portal_url"] = f"https://{config.custom_domain}"

        return branded
