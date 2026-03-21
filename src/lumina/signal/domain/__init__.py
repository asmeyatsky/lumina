"""
SIGNAL Domain Layer — Distribution & Amplification Engine

Exports the core domain model: entities, value objects, events, and service interfaces.
"""

from lumina.signal.domain.entities import (
    CitationSurface,
    CommunityPlaybook,
    DistributionAction,
    DistributionPlan,
    PRBrief,
)
from lumina.signal.domain.events import (
    CoverageUpdated,
    DistributionPlanCreated,
    PRBriefGenerated,
    SignalDistributed,
    SurfaceGapIdentified,
)
from lumina.signal.domain.value_objects import (
    ActionStatus,
    ActionType,
    DistributionCoverage,
    PresenceStatus,
    SurfaceAffinity,
    SurfaceCategory,
)

__all__ = [
    "ActionStatus",
    "ActionType",
    "CitationSurface",
    "CommunityPlaybook",
    "CoverageUpdated",
    "DistributionAction",
    "DistributionCoverage",
    "DistributionPlan",
    "DistributionPlanCreated",
    "PRBrief",
    "PRBriefGenerated",
    "PresenceStatus",
    "SignalDistributed",
    "SurfaceAffinity",
    "SurfaceCategory",
    "SurfaceGapIdentified",
]
