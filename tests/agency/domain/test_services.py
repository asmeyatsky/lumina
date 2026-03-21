"""
Tests for Agency Domain Services

Verifies:
- PortfolioAnalysisService generates correct summary
- PortfolioAnalysisService identifies at-risk clients
- PortfolioAnalysisService ranks by performance
- ReportGenerationService creates weekly summary
- WhiteLabelService validates config (rejects invalid colors, missing fields)
- WhiteLabelService applies branding to report data
"""

from __future__ import annotations

import pytest
from datetime import datetime, UTC

from lumina.shared.domain.value_objects import Score

from lumina.intelligence.domain.entities import (
    AIVisibilityScore,
    Recommendation,
    ScoreComponent,
)
from lumina.intelligence.domain.value_objects import EffortLevel

from lumina.agency.domain.entities import WhiteLabelConfig
from lumina.agency.domain.services import (
    PortfolioAnalysisService,
    ReportGenerationService,
    WhiteLabelService,
)


class TestPortfolioAnalysisService:
    """Tests for the portfolio analysis domain service."""

    def _make_avs(
        self,
        brand_id: str,
        score: float,
        previous: float | None = None,
    ) -> AIVisibilityScore:
        """Helper to create an AIVisibilityScore with optional previous score."""
        return AIVisibilityScore(
            brand_id=brand_id,
            overall=Score(score),
            previous_score=Score(previous) if previous is not None else None,
            components=(
                ScoreComponent(module_name="pulse", score=Score(score), weight=0.30),
                ScoreComponent(module_name="graph", score=Score(score), weight=0.25),
                ScoreComponent(module_name="beam", score=Score(score), weight=0.25),
                ScoreComponent(module_name="signal", score=Score(score), weight=0.20),
            ),
        )

    def test_generates_correct_summary(self) -> None:
        """Portfolio summary contains accurate aggregate metrics."""
        client_scores = {
            "BrandA": self._make_avs("brand-a", 80.0, 70.0),
            "BrandB": self._make_avs("brand-b", 60.0, 65.0),
            "BrandC": self._make_avs("brand-c", 50.0, 50.0),
        }

        summary = PortfolioAnalysisService.generate_portfolio_summary(client_scores)

        assert summary.total_clients == 3
        assert summary.avg_avs.value == pytest.approx(63.33, abs=0.01)
        assert summary.clients_improving == 1  # BrandA: +10
        assert summary.clients_declining == 1  # BrandB: -5
        assert summary.top_performer == "BrandA"

    def test_generates_empty_summary_for_no_clients(self) -> None:
        """Empty input produces an empty summary."""
        summary = PortfolioAnalysisService.generate_portfolio_summary({})
        assert summary.total_clients == 0
        assert summary.avg_avs.value == 0.0
        assert summary.top_performer == ""

    def test_identifies_at_risk_clients(self) -> None:
        """Clients with AVS decline greater than threshold are flagged."""
        client_scores = {
            "BrandA": self._make_avs("brand-a", 60.0, 70.0),  # -10 (at risk)
            "BrandB": self._make_avs("brand-b", 68.0, 70.0),  # -2 (ok)
            "BrandC": self._make_avs("brand-c", 40.0, 55.0),  # -15 (at risk)
        }

        at_risk = PortfolioAnalysisService.identify_at_risk_clients(
            client_scores, threshold=5.0
        )

        assert len(at_risk) == 2
        assert "BrandA" in at_risk
        assert "BrandC" in at_risk
        assert "BrandB" not in at_risk

    def test_identifies_no_at_risk_when_all_stable(self) -> None:
        """No clients flagged when all are stable or improving."""
        client_scores = {
            "BrandA": self._make_avs("brand-a", 80.0, 70.0),  # +10
            "BrandB": self._make_avs("brand-b", 70.0, 70.0),  # 0
        }

        at_risk = PortfolioAnalysisService.identify_at_risk_clients(client_scores)
        assert at_risk == []

    def test_custom_threshold(self) -> None:
        """Custom threshold is applied correctly."""
        client_scores = {
            "BrandA": self._make_avs("brand-a", 67.0, 70.0),  # -3
        }

        # Default threshold (5.0) — not at risk
        assert PortfolioAnalysisService.identify_at_risk_clients(client_scores) == []

        # Custom threshold (2.0) — at risk
        at_risk = PortfolioAnalysisService.identify_at_risk_clients(
            client_scores, threshold=2.0
        )
        assert at_risk == ["BrandA"]

    def test_ranks_by_performance(self) -> None:
        """Clients are ranked by AVS score descending."""
        client_scores = {
            "BrandC": self._make_avs("brand-c", 50.0, 50.0),
            "BrandA": self._make_avs("brand-a", 80.0, 70.0),
            "BrandB": self._make_avs("brand-b", 65.0, 60.0),
        }

        ranked = PortfolioAnalysisService.rank_clients_by_performance(client_scores)

        assert len(ranked) == 3
        assert ranked[0].brand_name == "BrandA"
        assert ranked[0].avs_score.value == 80.0
        assert ranked[1].brand_name == "BrandB"
        assert ranked[1].avs_score.value == 65.0
        assert ranked[2].brand_name == "BrandC"
        assert ranked[2].avs_score.value == 50.0

    def test_ranks_include_trend_data(self) -> None:
        """Ranked clients include correct trend deltas."""
        client_scores = {
            "BrandA": self._make_avs("brand-a", 80.0, 70.0),
        }

        ranked = PortfolioAnalysisService.rank_clients_by_performance(client_scores)

        assert ranked[0].avs_trend == pytest.approx(10.0)

    def test_needs_attention_includes_low_scores(self) -> None:
        """Brands with scores below 40 are flagged as needing attention."""
        client_scores = {
            "BrandA": self._make_avs("brand-a", 35.0, 35.0),
            "BrandB": self._make_avs("brand-b", 80.0, 80.0),
        }

        summary = PortfolioAnalysisService.generate_portfolio_summary(client_scores)
        assert "BrandA" in summary.needs_attention
        assert "BrandB" not in summary.needs_attention


class TestReportGenerationService:
    """Tests for the report generation domain service."""

    def test_creates_weekly_summary(self) -> None:
        """Weekly summary contains all expected sections."""
        avs = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(72.5),
            previous_score=Score(65.0),
            components=(
                ScoreComponent(module_name="pulse", score=Score(80.0), weight=0.30),
                ScoreComponent(module_name="graph", score=Score(60.0), weight=0.25),
                ScoreComponent(module_name="beam", score=Score(70.0), weight=0.25),
                ScoreComponent(module_name="signal", score=Score(50.0), weight=0.20),
            ),
        )

        recommendations = [
            Recommendation(
                id="rec-1",
                brand_id="brand-1",
                source_module="pulse",
                action_description="Improve citation rate",
                expected_avs_impact=Score(10.0),
                effort_level=EffortLevel.LOW,
                priority_rank=1,
            ),
        ]

        citation_data = {"total_citations": 42, "engines_citing": 3}

        report = ReportGenerationService.generate_weekly_summary(
            brand_id="brand-1",
            avs_data=avs,
            citation_data=citation_data,
            recommendations=recommendations,
            agency_id="agency-1",
        )

        assert report.client_brand_id == "brand-1"
        assert report.agency_id == "agency-1"
        assert report.report_type.value == "weekly_summary"
        assert "Weekly" in report.title

        # Verify report data sections
        data_dict = dict(report.data)
        assert "executive_summary" in data_dict
        assert "avs_trend" in data_dict
        assert "citation_highlights" in data_dict
        assert "recommendations" in data_dict
        assert "next_steps" in data_dict

        # Check executive summary content
        exec_summary = data_dict["executive_summary"]
        assert exec_summary["avs_score"] == 72.5
        assert exec_summary["avs_delta"] == pytest.approx(7.5)

    def test_creates_monthly_review(self) -> None:
        """Monthly review contains historical analysis."""
        avs_history = [
            AIVisibilityScore(
                brand_id="brand-1",
                overall=Score(60.0),
            ),
            AIVisibilityScore(
                brand_id="brand-1",
                overall=Score(65.0),
            ),
            AIVisibilityScore(
                brand_id="brand-1",
                overall=Score(72.0),
            ),
        ]

        report = ReportGenerationService.generate_monthly_review(
            brand_id="brand-1",
            avs_history=avs_history,
            content_scores=[{"url": "https://example.com", "score": 75.0}],
            distribution_coverage={"overall_coverage": 85.0},
            agency_id="agency-1",
        )

        assert report.report_type.value == "monthly_review"
        assert "Monthly" in report.title

        data_dict = dict(report.data)
        exec_summary = data_dict["executive_summary"]
        assert exec_summary["data_points"] == 3
        assert exec_summary["monthly_delta"] == pytest.approx(12.0)


class TestWhiteLabelService:
    """Tests for the white-label branding domain service."""

    def test_validates_valid_config(self) -> None:
        """Valid configuration returns no errors."""
        config = WhiteLabelConfig(
            agency_id="agency-1",
            company_name="Acme Agency",
            logo_url="https://acme.com/logo.png",
            primary_color="#1a2b3c",
            secondary_color="#ffffff",
            accent_color="#0066cc",
            email_from_address="reports@acme.com",
        )

        errors = WhiteLabelService.validate_config(config)
        assert errors == []

    def test_rejects_missing_company_name(self) -> None:
        """Missing company_name produces an error."""
        config = WhiteLabelConfig(
            company_name="",
            logo_url="https://acme.com/logo.png",
        )

        errors = WhiteLabelService.validate_config(config)
        assert any("company_name" in e for e in errors)

    def test_rejects_missing_logo_url(self) -> None:
        """Missing logo_url produces an error."""
        config = WhiteLabelConfig(
            company_name="Acme",
            logo_url="",
        )

        errors = WhiteLabelService.validate_config(config)
        assert any("logo_url" in e for e in errors)

    def test_rejects_invalid_logo_url(self) -> None:
        """Non-HTTP logo_url produces an error."""
        config = WhiteLabelConfig(
            company_name="Acme",
            logo_url="ftp://acme.com/logo.png",
        )

        errors = WhiteLabelService.validate_config(config)
        assert any("logo_url must start with http" in e for e in errors)

    def test_rejects_invalid_hex_colors(self) -> None:
        """Invalid hex colours produce errors."""
        config = WhiteLabelConfig(
            company_name="Acme",
            logo_url="https://acme.com/logo.png",
            primary_color="red",
            secondary_color="not-a-color",
            accent_color="#gggggg",
        )

        errors = WhiteLabelService.validate_config(config)
        assert any("primary_color" in e for e in errors)
        assert any("secondary_color" in e for e in errors)
        assert any("accent_color" in e for e in errors)

    def test_rejects_invalid_email(self) -> None:
        """Invalid email address produces an error."""
        config = WhiteLabelConfig(
            company_name="Acme",
            logo_url="https://acme.com/logo.png",
            email_from_address="not-an-email",
        )

        errors = WhiteLabelService.validate_config(config)
        assert any("email_from_address" in e for e in errors)

    def test_rejects_invalid_custom_domain(self) -> None:
        """Invalid custom domain produces an error."""
        config = WhiteLabelConfig(
            company_name="Acme",
            logo_url="https://acme.com/logo.png",
            custom_domain="notadomain",
        )

        errors = WhiteLabelService.validate_config(config)
        assert any("custom_domain" in e for e in errors)

    def test_applies_branding_to_report_data(self) -> None:
        """Branding is injected into report data."""
        report_data: dict[str, object] = {
            "executive_summary": {"avs_score": 72.5},
            "recommendations": [],
        }

        config = WhiteLabelConfig(
            agency_id="agency-1",
            company_name="Acme Agency",
            logo_url="https://acme.com/logo.png",
            primary_color="#1a2b3c",
            secondary_color="#ffffff",
            accent_color="#0066cc",
            report_footer_text="Confidential",
            powered_by_visible=True,
        )

        branded = WhiteLabelService.apply_branding(report_data, config)

        # Original data is preserved
        assert branded["executive_summary"] == {"avs_score": 72.5}
        assert branded["recommendations"] == []

        # Branding is injected
        assert "branding" in branded
        branding = branded["branding"]
        assert branding["company_name"] == "Acme Agency"
        assert branding["logo_url"] == "https://acme.com/logo.png"
        assert branding["primary_color"] == "#1a2b3c"

        # Footer is injected
        assert "footer" in branded
        footer = branded["footer"]
        assert footer["text"] == "Confidential"
        assert footer["powered_by_visible"] is True
        assert footer["powered_by_text"] == "Powered by LUMINA"

    def test_applies_branding_without_powered_by(self) -> None:
        """Powered by text is omitted when powered_by_visible is False."""
        config = WhiteLabelConfig(
            company_name="Acme",
            logo_url="https://acme.com/logo.png",
            powered_by_visible=False,
        )

        branded = WhiteLabelService.apply_branding({}, config)
        assert "powered_by_text" not in branded["footer"]

    def test_applies_branding_with_custom_domain(self) -> None:
        """Portal URL is added when custom domain is configured."""
        config = WhiteLabelConfig(
            company_name="Acme",
            logo_url="https://acme.com/logo.png",
            custom_domain="reports.acme.com",
        )

        branded = WhiteLabelService.apply_branding({}, config)
        assert branded["portal_url"] == "https://reports.acme.com"

    def test_applies_branding_does_not_mutate_original(self) -> None:
        """apply_branding returns a new dict without mutating the original."""
        original: dict[str, object] = {"key": "value"}
        config = WhiteLabelConfig(
            company_name="Acme",
            logo_url="https://acme.com/logo.png",
        )

        branded = WhiteLabelService.apply_branding(original, config)
        assert "branding" in branded
        assert "branding" not in original
