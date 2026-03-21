"""
Tests for entity recognition.

Tests cover brand name recognition, entity density computation,
custom entity lists, and empty content handling.
"""

from __future__ import annotations

import pytest

from lumina.infrastructure.nlp.entity_recognizer import (
    EntityRecognizer,
    EntityType,
)


class TestEntityRecognizer:
    """Tests for EntityRecognizer."""

    def test_recognizes_brand_names(self) -> None:
        """Custom brand names should be recognized in text."""
        recognizer = EntityRecognizer(custom_brands=["Acme", "TechCorp"])

        text = "Acme provides cloud services. TechCorp offers AI solutions."
        entities = recognizer.recognize(text)

        brand_entities = [e for e in entities if e.entity_type == EntityType.BRAND]
        brand_names = {e.text.lower() for e in brand_entities}

        assert "acme" in brand_names
        assert "techcorp" in brand_names

    def test_computes_entity_density(self) -> None:
        """Entity density should reflect entities per 100 words."""
        recognizer = EntityRecognizer(
            custom_brands=["Acme", "CloudBase"]
        )

        # 20 words, 2 brand mentions = density of ~10 per 100 words
        text = (
            "Acme and CloudBase are leading providers in the cloud "
            "computing market. They offer innovative solutions for "
            "enterprise customers."
        )
        density = recognizer.compute_entity_density(text)

        assert density > 0.0
        # With at least 2 entities in ~20 words, density should be notable
        assert density >= 5.0

    def test_handles_custom_entity_lists(self) -> None:
        """Custom entities of various types should be recognized."""
        recognizer = EntityRecognizer(
            custom_brands=["Acme"],
            custom_products=["AcmeCloud Pro"],
            custom_entities=[
                ("Jane Smith", EntityType.PERSON),
                ("Cloud Alliance", EntityType.ORGANIZATION),
            ],
        )

        text = (
            "Jane Smith announced that Acme is launching AcmeCloud Pro "
            "in partnership with the Cloud Alliance."
        )
        entities = recognizer.recognize(text)

        entity_texts = {e.text.lower() for e in entities}
        assert "acme" in entity_texts
        assert "acmecloud pro" in entity_texts
        assert "jane smith" in entity_texts
        assert "cloud alliance" in entity_texts

    def test_handles_empty_content(self) -> None:
        """Empty or whitespace content should return no entities."""
        recognizer = EntityRecognizer(custom_brands=["Acme"])

        assert recognizer.recognize("") == []
        assert recognizer.recognize("   ") == []
        assert recognizer.compute_entity_density("") == 0.0

    def test_recognizes_person_patterns(self) -> None:
        """Title + name patterns should be recognized as persons."""
        recognizer = EntityRecognizer()

        text = "Dr. Johnson presented the findings alongside Prof. Williams."
        entities = recognizer.recognize(text)

        person_entities = [e for e in entities if e.entity_type == EntityType.PERSON]
        person_texts = {e.text for e in person_entities}

        assert any("Johnson" in t for t in person_texts)

    def test_case_insensitive_brand_matching(self) -> None:
        """Brand matching should be case-insensitive."""
        recognizer = EntityRecognizer(custom_brands=["TechCorp"])

        text = "TECHCORP dominates the market. techcorp is also growing."
        entities = recognizer.recognize(text)

        brand_entities = [e for e in entities if e.entity_type == EntityType.BRAND]
        assert len(brand_entities) >= 2
