"""
GRAPH Domain Layer — Entity Intelligence & Knowledge Architecture

Public API for the GRAPH bounded context domain.
"""

from lumina.graph.domain.value_objects import (
    DimensionType,
    GapSeverity,
    EntityHealth,
    SchemaOrgType,
    JsonLdDocument,
)
from lumina.graph.domain.entities import (
    EntityProfile,
    EntityDimension,
    KnowledgeGap,
    CompetitorEntityComparison,
)
from lumina.graph.domain.events import (
    EntityProfileCreated,
    EntityDimensionUpdated,
    KnowledgeGapIdentified,
    EntityHealthChanged,
)
from lumina.graph.domain.services import (
    GapAnalysisService,
    EntityScoringService,
    JsonLdGenerationService,
    CompetitorBenchmarkService,
)
from lumina.graph.domain.ports import (
    GraphRepositoryPort,
    WikidataPort,
    SchemaValidatorPort,
)

__all__ = [
    # Value objects & enums
    "DimensionType",
    "GapSeverity",
    "EntityHealth",
    "SchemaOrgType",
    "JsonLdDocument",
    # Entities
    "EntityProfile",
    "EntityDimension",
    "KnowledgeGap",
    "CompetitorEntityComparison",
    # Events
    "EntityProfileCreated",
    "EntityDimensionUpdated",
    "KnowledgeGapIdentified",
    "EntityHealthChanged",
    # Services
    "GapAnalysisService",
    "EntityScoringService",
    "JsonLdGenerationService",
    "CompetitorBenchmarkService",
    # Ports
    "GraphRepositoryPort",
    "WikidataPort",
    "SchemaValidatorPort",
]
