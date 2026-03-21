"""
Shared Value Objects

Architectural Intent:
- Immutable, identity-less domain concepts shared across bounded contexts
- Enforce invariants at construction time
- Use ubiquitous language from the GEO domain
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AIEngine(str, Enum):
    """AI answer engines monitored by LUMINA."""

    CLAUDE = "claude"
    GPT4O = "gpt-4o"
    GEMINI = "gemini"
    PERPLEXITY = "perplexity"


@dataclass(frozen=True)
class BrandId:
    """Unique identifier for a monitored brand."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("BrandId cannot be empty")


@dataclass(frozen=True)
class TenantId:
    """Unique identifier for a tenant (organisation)."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("TenantId cannot be empty")


@dataclass(frozen=True)
class Score:
    """A normalised score between 0 and 100."""

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 100.0):
            raise ValueError(f"Score must be between 0 and 100, got {self.value}")

    def __float__(self) -> float:
        return self.value

    def __lt__(self, other: Score) -> bool:
        return self.value < other.value

    def __le__(self, other: Score) -> bool:
        return self.value <= other.value


@dataclass(frozen=True)
class Percentage:
    """A percentage value between 0 and 100."""

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 100.0):
            raise ValueError(f"Percentage must be between 0 and 100, got {self.value}")

    @property
    def as_fraction(self) -> float:
        return self.value / 100.0


@dataclass(frozen=True)
class URL:
    """A validated URL value object."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://, got {self.value}")
