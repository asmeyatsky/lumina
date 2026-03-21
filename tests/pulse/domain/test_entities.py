"""
Tests for PULSE domain entities.

Validates immutability, state transitions, and domain event collection
on the MonitoringRun aggregate root.
"""

from __future__ import annotations

from datetime import datetime, UTC

import pytest

from lumina.shared.domain.value_objects import AIEngine, BrandId, Score

from lumina.pulse.domain.entities import (
    Citation,
    CitationResult,
    MonitoringRun,
    PromptBattery,
    PromptTemplate,
)
from lumina.pulse.domain.events import MonitoringRunCompleted, MonitoringRunFailed
from lumina.pulse.domain.value_objects import (
    CitationPosition,
    RunStatus,
    Sentiment,
)


# -- Fixtures ---------------------------------------------------------------


def _make_prompt_template(
    id: str = "pt-1",
    text: str = "What is the best CRM?",
    category: str = "comparison",
) -> PromptTemplate:
    return PromptTemplate(
        id=id,
        text=text,
        category=category,
        intent_tags=("comparison", "crm"),
    )


def _make_battery(
    id: str = "bat-1",
    brand_id: str = "brand-acme",
) -> PromptBattery:
    return PromptBattery(
        id=id,
        brand_id=BrandId(value=brand_id),
        name="CRM Comparison Battery",
        prompts=(_make_prompt_template(),),
        vertical="saas",
        schedule_cron="0 */6 * * *",
        is_active=True,
    )


def _make_citation(
    brand_name: str = "Acme",
    position: CitationPosition = CitationPosition.FIRST,
) -> Citation:
    return Citation(
        brand_name=brand_name,
        context="Acme is the best CRM for startups.",
        position=position,
        is_recommendation=True,
    )


def _make_citation_result(run_id: str = "run-1") -> CitationResult:
    return CitationResult(
        id="cr-1",
        run_id=run_id,
        engine=AIEngine.CLAUDE,
        prompt_text="What is the best CRM?",
        raw_response="Acme is the best CRM for startups.",
        citations=(_make_citation(),),
        sentiment=Sentiment.POSITIVE,
        accuracy_score=Score(value=85.0),
        response_latency_ms=320,
    )


def _make_monitoring_run(id: str = "run-1") -> MonitoringRun:
    return MonitoringRun(
        id=id,
        brand_id=BrandId(value="brand-acme"),
        battery_id="bat-1",
        started_at=datetime.now(UTC),
        status=RunStatus.PENDING,
    )


# -- MonitoringRun.complete() tests -----------------------------------------


class TestMonitoringRunComplete:
    def test_complete_produces_new_instance_with_completed_status(self) -> None:
        run = _make_monitoring_run()
        results = (_make_citation_result(run_id=run.id),)
        completed = run.complete(results)

        assert completed is not run
        assert completed.status == RunStatus.COMPLETED
        assert completed.results == results
        assert completed.completed_at is not None

    def test_complete_preserves_original_run_unchanged(self) -> None:
        run = _make_monitoring_run()
        results = (_make_citation_result(run_id=run.id),)
        _ = run.complete(results)

        assert run.status == RunStatus.PENDING
        assert run.results == ()
        assert run.completed_at is None

    def test_complete_collects_monitoring_run_completed_event(self) -> None:
        run = _make_monitoring_run()
        results = (_make_citation_result(run_id=run.id),)
        completed = run.complete(results)

        assert len(completed.domain_events) == 1
        event = completed.domain_events[0]
        assert isinstance(event, MonitoringRunCompleted)
        assert event.aggregate_id == run.id
        assert event.brand_id == "brand-acme"
        assert event.battery_id == "bat-1"
        assert event.total_citations == 1

    def test_complete_counts_total_citations_across_results(self) -> None:
        run = _make_monitoring_run()
        result1 = CitationResult(
            id="cr-1",
            run_id=run.id,
            engine=AIEngine.CLAUDE,
            prompt_text="prompt 1",
            raw_response="response 1",
            citations=(_make_citation(), _make_citation(brand_name="Rival")),
            sentiment=Sentiment.POSITIVE,
            accuracy_score=Score(value=80.0),
            response_latency_ms=200,
        )
        result2 = CitationResult(
            id="cr-2",
            run_id=run.id,
            engine=AIEngine.GPT4O,
            prompt_text="prompt 2",
            raw_response="response 2",
            citations=(_make_citation(),),
            sentiment=Sentiment.NEUTRAL,
            accuracy_score=Score(value=70.0),
            response_latency_ms=150,
        )
        completed = run.complete((result1, result2))

        event = completed.domain_events[0]
        assert isinstance(event, MonitoringRunCompleted)
        assert event.total_citations == 3

    def test_complete_records_unique_engines_queried(self) -> None:
        run = _make_monitoring_run()
        result1 = _make_citation_result(run_id=run.id)
        result2 = CitationResult(
            id="cr-2",
            run_id=run.id,
            engine=AIEngine.GPT4O,
            prompt_text="prompt",
            raw_response="response",
            citations=(),
            sentiment=Sentiment.NEUTRAL,
            accuracy_score=Score(value=50.0),
            response_latency_ms=100,
        )
        completed = run.complete((result1, result2))

        event = completed.domain_events[0]
        assert isinstance(event, MonitoringRunCompleted)
        assert set(event.engines_queried) == {"claude", "gpt-4o"}


# -- MonitoringRun.fail() tests ---------------------------------------------


class TestMonitoringRunFail:
    def test_fail_produces_new_instance_with_failed_status(self) -> None:
        run = _make_monitoring_run()
        failed = run.fail("Engine timeout")

        assert failed is not run
        assert failed.status == RunStatus.FAILED
        assert failed.completed_at is not None

    def test_fail_preserves_original_run_unchanged(self) -> None:
        run = _make_monitoring_run()
        _ = run.fail("Engine timeout")

        assert run.status == RunStatus.PENDING
        assert run.completed_at is None

    def test_fail_collects_monitoring_run_failed_event(self) -> None:
        run = _make_monitoring_run()
        failed = run.fail("Engine timeout")

        assert len(failed.domain_events) == 1
        event = failed.domain_events[0]
        assert isinstance(event, MonitoringRunFailed)
        assert event.aggregate_id == run.id
        assert event.reason == "Engine timeout"

    def test_fail_does_not_overwrite_existing_results(self) -> None:
        run = _make_monitoring_run()
        failed = run.fail("timeout")

        assert failed.results == ()


# -- MonitoringRun.collect_events() tests ------------------------------------


class TestMonitoringRunCollectEvents:
    def test_collect_events_returns_events_and_clean_aggregate(self) -> None:
        run = _make_monitoring_run()
        completed = run.complete((_make_citation_result(run_id=run.id),))

        clean, events = completed.collect_events()

        assert len(events) == 1
        assert clean.domain_events == ()
        assert clean.status == RunStatus.COMPLETED


# -- PromptBattery tests -----------------------------------------------------


class TestPromptBattery:
    def test_creation_with_valid_data(self) -> None:
        battery = _make_battery()

        assert battery.id == "bat-1"
        assert battery.brand_id.value == "brand-acme"
        assert battery.name == "CRM Comparison Battery"
        assert len(battery.prompts) == 1
        assert battery.vertical == "saas"
        assert battery.is_active is True

    def test_creation_fails_with_empty_id(self) -> None:
        with pytest.raises(ValueError, match="id cannot be empty"):
            PromptBattery(
                id="",
                brand_id=BrandId(value="brand-1"),
                name="Test",
                prompts=(),
                vertical="saas",
                schedule_cron="* * * * *",
            )

    def test_creation_fails_with_empty_name(self) -> None:
        with pytest.raises(ValueError, match="name cannot be empty"):
            PromptBattery(
                id="bat-1",
                brand_id=BrandId(value="brand-1"),
                name="",
                prompts=(),
                vertical="saas",
                schedule_cron="* * * * *",
            )

    def test_prompts_is_immutable_tuple(self) -> None:
        battery = _make_battery()
        assert isinstance(battery.prompts, tuple)


# -- Citation tests ----------------------------------------------------------


class TestCitation:
    def test_construction_with_valid_data(self) -> None:
        citation = _make_citation()

        assert citation.brand_name == "Acme"
        assert citation.position == CitationPosition.FIRST
        assert citation.is_recommendation is True

    def test_construction_fails_with_empty_brand_name(self) -> None:
        with pytest.raises(ValueError, match="brand_name cannot be empty"):
            Citation(
                brand_name="",
                context="some context",
                position=CitationPosition.FIRST,
                is_recommendation=False,
            )

    def test_construction_fails_with_empty_context_when_cited(self) -> None:
        with pytest.raises(ValueError, match="context cannot be empty"):
            Citation(
                brand_name="Acme",
                context="",
                position=CitationPosition.FIRST,
                is_recommendation=False,
            )

    def test_construction_allows_empty_context_when_not_cited(self) -> None:
        citation = Citation(
            brand_name="Acme",
            context="",
            position=CitationPosition.NOT_CITED,
            is_recommendation=False,
        )
        assert citation.position == CitationPosition.NOT_CITED


# -- CitationPosition ordering tests ----------------------------------------


class TestCitationPosition:
    def test_first_is_less_than_second(self) -> None:
        assert CitationPosition.FIRST < CitationPosition.SECOND

    def test_first_is_less_than_not_cited(self) -> None:
        assert CitationPosition.FIRST < CitationPosition.NOT_CITED

    def test_not_cited_is_greater_than_all_others(self) -> None:
        positions = [
            CitationPosition.FIRST,
            CitationPosition.SECOND,
            CitationPosition.THIRD,
            CitationPosition.MENTIONED,
        ]
        for pos in positions:
            assert CitationPosition.NOT_CITED > pos

    def test_ordering_is_consistent(self) -> None:
        ordered = sorted(
            [
                CitationPosition.MENTIONED,
                CitationPosition.FIRST,
                CitationPosition.NOT_CITED,
                CitationPosition.THIRD,
                CitationPosition.SECOND,
            ]
        )
        assert ordered == [
            CitationPosition.FIRST,
            CitationPosition.SECOND,
            CitationPosition.THIRD,
            CitationPosition.MENTIONED,
            CitationPosition.NOT_CITED,
        ]


# -- PromptTemplate tests ---------------------------------------------------


class TestPromptTemplate:
    def test_creation_with_valid_data(self) -> None:
        template = _make_prompt_template()
        assert template.text == "What is the best CRM?"
        assert template.category == "comparison"
        assert template.intent_tags == ("comparison", "crm")

    def test_creation_fails_with_empty_text(self) -> None:
        with pytest.raises(ValueError, match="text cannot be empty"):
            PromptTemplate(id="pt-1", text="", category="comparison")

    def test_creation_fails_with_empty_category(self) -> None:
        with pytest.raises(ValueError, match="category cannot be empty"):
            PromptTemplate(id="pt-1", text="some prompt", category="")


# -- CitationResult tests ---------------------------------------------------


class TestCitationResult:
    def test_creation_with_valid_data(self) -> None:
        result = _make_citation_result()
        assert result.engine == AIEngine.CLAUDE
        assert result.response_latency_ms == 320
        assert len(result.citations) == 1

    def test_creation_fails_with_negative_latency(self) -> None:
        with pytest.raises(ValueError, match="response_latency_ms"):
            CitationResult(
                id="cr-1",
                run_id="run-1",
                engine=AIEngine.CLAUDE,
                prompt_text="prompt",
                raw_response="response",
                citations=(),
                sentiment=Sentiment.NEUTRAL,
                accuracy_score=Score(value=50.0),
                response_latency_ms=-1,
            )
