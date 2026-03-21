"""
Named entity recognition for brand/product/person/organization detection.

Uses regex and heuristics (no spaCy dependency) to identify entities in text,
compute entity density scores, and support custom entity lists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class EntityType(str, Enum):
    """Classification of recognized entities."""

    BRAND = "brand"
    PRODUCT = "product"
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"


@dataclass(frozen=True)
class RecognizedEntity:
    """A single entity recognized in text."""

    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class EntityRecognizer:
    """Named entity recognizer using regex and heuristic patterns.

    Identifies brand names, product names, person names, and organization
    names in text. Supports custom entity lists for domain-specific recognition.

    Parameters
    ----------
    custom_brands:
        Additional brand names to detect.
    custom_products:
        Additional product names to detect.
    custom_entities:
        Arbitrary additional entities to detect, each as (name, EntityType).
    """

    custom_brands: list[str] = field(default_factory=list)
    custom_products: list[str] = field(default_factory=list)
    custom_entities: list[tuple[str, EntityType]] = field(default_factory=list)

    # -- Well-known patterns -------------------------------------------------

    # Capitalized multi-word names (e.g. "John Smith", "Acme Corporation")
    _PERSON_PATTERN: re.Pattern[str] = re.compile(
        r"\b(?:Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.)\s+"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b"
    )

    # Capitalized sequences that look like proper nouns (2+ words)
    _PROPER_NOUN_PATTERN: re.Pattern[str] = re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
    )

    # Organization suffixes
    _ORG_SUFFIXES: tuple[str, ...] = (
        "Inc", "Inc.", "Corp", "Corp.", "Corporation", "LLC", "Ltd", "Ltd.",
        "Company", "Co.", "Group", "Holdings", "Partners", "Foundation",
        "Institute", "Association", "University", "Technologies",
    )

    # Product-like patterns (brand + version/number)
    _PRODUCT_PATTERN: re.Pattern[str] = re.compile(
        r"\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*"
        r"\s+(?:Pro|Plus|Max|Ultra|Lite|Mini|Air|SE|XL|v\d+|\d+(?:\.\d+)*))\b"
    )

    def recognize(self, text: str) -> list[RecognizedEntity]:
        """Recognize all entities in the given text.

        Returns a deduplicated list of recognized entities ordered by
        their position in the text.
        """
        if not text or not text.strip():
            return []

        entities: list[RecognizedEntity] = []

        # 1. Custom brands (highest priority)
        for brand in self.custom_brands:
            entities.extend(self._find_custom(text, brand, EntityType.BRAND))

        # 2. Custom products
        for product in self.custom_products:
            entities.extend(
                self._find_custom(text, product, EntityType.PRODUCT)
            )

        # 3. Custom arbitrary entities
        for name, etype in self.custom_entities:
            entities.extend(self._find_custom(text, name, etype))

        # 4. Person patterns (titles + names)
        for match in self._PERSON_PATTERN.finditer(text):
            entities.append(
                RecognizedEntity(
                    text=match.group(0),
                    entity_type=EntityType.PERSON,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                )
            )

        # 5. Product patterns
        for match in self._PRODUCT_PATTERN.finditer(text):
            entities.append(
                RecognizedEntity(
                    text=match.group(0),
                    entity_type=EntityType.PRODUCT,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.7,
                )
            )

        # 6. Organization detection (proper nouns with org suffixes)
        for match in self._PROPER_NOUN_PATTERN.finditer(text):
            name = match.group(0)
            words = name.split()
            if any(w.rstrip(".") in [s.rstrip(".") for s in self._ORG_SUFFIXES]
                   for w in words):
                entities.append(
                    RecognizedEntity(
                        text=name,
                        entity_type=EntityType.ORGANIZATION,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.85,
                    )
                )

        # 7. Generic proper noun sequences not already captured
        covered_spans = {(e.start, e.end) for e in entities}
        for match in self._PROPER_NOUN_PATTERN.finditer(text):
            span = (match.start(), match.end())
            # Skip if this span overlaps any existing entity
            if any(
                not (span[1] <= cs[0] or span[0] >= cs[1])
                for cs in covered_spans
            ):
                continue
            name = match.group(0)
            # Skip if it looks like a sentence start (preceded by ". " or at pos 0)
            if match.start() == 0 or text[match.start() - 2: match.start()] == ". ":
                # Only skip two-word sequences at sentence starts
                if len(name.split()) <= 2:
                    continue
            entities.append(
                RecognizedEntity(
                    text=name,
                    entity_type=EntityType.ORGANIZATION,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.5,
                )
            )

        # Deduplicate by (text, start, end)
        seen: set[tuple[str, int, int]] = set()
        deduped: list[RecognizedEntity] = []
        for e in entities:
            key = (e.text, e.start, e.end)
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        # Sort by position
        deduped.sort(key=lambda e: e.start)
        return deduped

    def compute_entity_density(self, text: str) -> float:
        """Compute entity density score: entities per 100 words.

        Returns a float representing how many entities are present per
        100 words of content.
        """
        if not text or not text.strip():
            return 0.0

        entities = self.recognize(text)
        word_count = len(text.split())
        if word_count == 0:
            return 0.0

        return round(len(entities) / word_count * 100, 2)

    @staticmethod
    def _find_custom(
        text: str, name: str, entity_type: EntityType
    ) -> list[RecognizedEntity]:
        """Find all occurrences of a custom entity name in text."""
        results: list[RecognizedEntity] = []
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        for match in pattern.finditer(text):
            results.append(
                RecognizedEntity(
                    text=match.group(0),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0,
                )
            )
        return results
