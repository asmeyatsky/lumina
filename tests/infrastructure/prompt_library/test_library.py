"""
Tests for the Prompt Battery Library

Validates template loading, vertical coverage, placeholder substitution,
and category filtering across all verticals.
"""

from __future__ import annotations

import pytest

from lumina.infrastructure.prompt_library.library import PromptLibrary
from lumina.infrastructure.prompt_library.verticals.saas import SAAS_TEMPLATES
from lumina.infrastructure.prompt_library.verticals.fintech import FINTECH_TEMPLATES
from lumina.infrastructure.prompt_library.verticals.healthtech import HEALTHTECH_TEMPLATES
from lumina.infrastructure.prompt_library.verticals.ecommerce import ECOMMERCE_TEMPLATES
from lumina.infrastructure.prompt_library.verticals.cloud import CLOUD_TEMPLATES
from lumina.pulse.domain.entities import PromptBattery, PromptTemplate


@pytest.fixture
def library() -> PromptLibrary:
    return PromptLibrary()


# ---------------------------------------------------------------------- #
# get_battery_for_vertical
# ---------------------------------------------------------------------- #


@pytest.mark.parametrize("vertical", ["saas", "fintech", "healthtech", "ecommerce", "cloud"])
def test_get_battery_for_vertical_returns_battery(library: PromptLibrary, vertical: str) -> None:
    battery = library.get_battery_for_vertical(vertical, brand_name="Acme")
    assert isinstance(battery, PromptBattery)
    assert battery.vertical == vertical
    assert battery.is_active is True
    assert len(battery.prompts) > 0


def test_get_battery_for_unknown_vertical_raises(library: PromptLibrary) -> None:
    with pytest.raises(ValueError, match="Unknown vertical"):
        library.get_battery_for_vertical("automotive", brand_name="Acme")


def test_get_battery_substitutes_brand_name(library: PromptLibrary) -> None:
    battery = library.get_battery_for_vertical("saas", brand_name="Lumina")
    texts = [p.text for p in battery.prompts]
    # At least one prompt should now contain the brand name
    assert any("Lumina" in t for t in texts)
    # No leftover {brand} placeholders
    assert not any("{brand}" in t for t in texts)


# ---------------------------------------------------------------------- #
# get_all_verticals
# ---------------------------------------------------------------------- #


def test_get_all_verticals_returns_five(library: PromptLibrary) -> None:
    verticals = library.get_all_verticals()
    assert len(verticals) == 5
    assert set(verticals) == {"saas", "fintech", "healthtech", "ecommerce", "cloud"}


def test_get_all_verticals_sorted(library: PromptLibrary) -> None:
    verticals = library.get_all_verticals()
    assert verticals == sorted(verticals)


# ---------------------------------------------------------------------- #
# customize_battery
# ---------------------------------------------------------------------- #


def test_customize_battery_substitutes_brand_name(library: PromptLibrary) -> None:
    battery = library.get_battery_for_vertical("saas", brand_name="{brand}")
    customized = library.customize_battery(battery, brand_name="TestCo", competitors=["Rival1", "Rival2"])
    texts = [p.text for p in customized.prompts]
    assert not any("{brand}" in t for t in texts)
    assert any("TestCo" in t for t in texts)


def test_customize_battery_substitutes_competitor_names(library: PromptLibrary) -> None:
    battery = library.get_battery_for_vertical("saas", brand_name="{brand}")
    customized = library.customize_battery(battery, brand_name="TestCo", competitors=["AlphaInc", "BetaCorp"])
    texts = [p.text for p in customized.prompts]
    assert any("AlphaInc" in t for t in texts)
    assert any("BetaCorp" in t for t in texts)
    assert not any("{competitor_1}" in t for t in texts)
    assert not any("{competitor_2}" in t for t in texts)


def test_customize_battery_handles_missing_competitors_gracefully(library: PromptLibrary) -> None:
    battery = library.get_battery_for_vertical("saas", brand_name="{brand}")

    # No competitors at all
    customized = library.customize_battery(battery, brand_name="TestCo", competitors=[])
    texts = [p.text for p in customized.prompts]
    assert not any("{competitor_1}" in t for t in texts)
    assert not any("{competitor_2}" in t for t in texts)
    # Fallback text should be present instead
    assert any("leading alternative" in t for t in texts)


def test_customize_battery_handles_none_competitors(library: PromptLibrary) -> None:
    battery = library.get_battery_for_vertical("saas", brand_name="{brand}")
    customized = library.customize_battery(battery, brand_name="TestCo", competitors=None)
    texts = [p.text for p in customized.prompts]
    assert not any("{competitor_1}" in t for t in texts)
    assert not any("{competitor_2}" in t for t in texts)


def test_customize_battery_with_single_competitor(library: PromptLibrary) -> None:
    battery = library.get_battery_for_vertical("saas", brand_name="{brand}")
    customized = library.customize_battery(battery, brand_name="TestCo", competitors=["OnlyRival"])
    texts = [p.text for p in customized.prompts]
    assert any("OnlyRival" in t for t in texts)
    assert not any("{competitor_1}" in t for t in texts)
    # competitor_2 should get fallback
    assert any("another competitor" in t for t in texts)


def test_customize_battery_updates_brand_id(library: PromptLibrary) -> None:
    battery = library.get_battery_for_vertical("saas", brand_name="OldBrand")
    customized = library.customize_battery(battery, brand_name="NewBrand", competitors=[])
    assert customized.brand_id.value == "NewBrand"


# ---------------------------------------------------------------------- #
# get_templates_by_category
# ---------------------------------------------------------------------- #


def test_get_templates_by_category_filters_correctly(library: PromptLibrary) -> None:
    results = library.get_templates_by_category("competitive")
    assert len(results) > 0
    assert all(t.category == "competitive" for t in results)


def test_get_templates_by_category_returns_empty_for_unknown(library: PromptLibrary) -> None:
    results = library.get_templates_by_category("nonexistent_category")
    assert results == []


def test_get_templates_by_category_product_recommendation(library: PromptLibrary) -> None:
    results = library.get_templates_by_category("product_recommendation")
    assert len(results) > 0
    assert all(t.category == "product_recommendation" for t in results)


# ---------------------------------------------------------------------- #
# Vertical-specific content validation
# ---------------------------------------------------------------------- #


def test_saas_vertical_has_all_required_categories() -> None:
    categories = {t.category for t in SAAS_TEMPLATES}
    expected = {
        "product_recommendation",
        "buying_intent",
        "brand_knowledge",
        "technical",
        "competitive",
        "industry_authority",
    }
    assert expected.issubset(categories), f"Missing categories: {expected - categories}"


def test_saas_vertical_has_at_least_30_templates() -> None:
    assert len(SAAS_TEMPLATES) >= 30


def test_fintech_vertical_has_compliance_prompts() -> None:
    compliance = [t for t in FINTECH_TEMPLATES if t.category == "compliance"]
    assert len(compliance) >= 3
    compliance_texts = " ".join(t.text for t in compliance)
    assert "compliance" in compliance_texts.lower() or "SOC 2" in compliance_texts


def test_fintech_vertical_has_at_least_25_templates() -> None:
    assert len(FINTECH_TEMPLATES) >= 25


def test_healthtech_vertical_has_hipaa_prompts() -> None:
    all_texts = " ".join(t.text for t in HEALTHTECH_TEMPLATES)
    assert "HIPAA" in all_texts


def test_healthtech_vertical_has_compliance_category() -> None:
    compliance = [t for t in HEALTHTECH_TEMPLATES if t.category == "compliance"]
    assert len(compliance) >= 3


def test_healthtech_vertical_has_at_least_25_templates() -> None:
    assert len(HEALTHTECH_TEMPLATES) >= 25


def test_ecommerce_vertical_has_at_least_25_templates() -> None:
    assert len(ECOMMERCE_TEMPLATES) >= 25


def test_cloud_vertical_has_at_least_25_templates() -> None:
    assert len(CLOUD_TEMPLATES) >= 25


# ---------------------------------------------------------------------- #
# All templates quality checks
# ---------------------------------------------------------------------- #


_ALL_TEMPLATES = (
    SAAS_TEMPLATES + FINTECH_TEMPLATES + HEALTHTECH_TEMPLATES
    + ECOMMERCE_TEMPLATES + CLOUD_TEMPLATES
)


@pytest.mark.parametrize("template", _ALL_TEMPLATES, ids=lambda t: t.id)
def test_all_templates_have_non_empty_text_and_category(template: PromptTemplate) -> None:
    assert template.text.strip(), f"Template {template.id} has empty text"
    assert template.category.strip(), f"Template {template.id} has empty category"
    assert template.id.strip(), f"Template has empty id"


def test_all_template_ids_are_unique() -> None:
    ids = [t.id for t in _ALL_TEMPLATES]
    assert len(ids) == len(set(ids)), "Duplicate template IDs detected"
