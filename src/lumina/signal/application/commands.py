"""
SIGNAL Application Commands — Write-side use cases

Architectural Intent:
- Each command orchestrates a single use case
- Commands depend on domain ports (protocols), never on infrastructure
- After persisting aggregate state, commands publish collected domain events
- Commands are the only layer that coordinates domain services, repositories, and event bus
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import BrandId, Score
from lumina.shared.ports.event_bus import EventBusPort

from lumina.signal.domain.entities import (
    CitationSurface,
    DistributionAction,
    DistributionPlan,
    PRBrief,
)
from lumina.signal.domain.events import (
    DistributionPlanCreated,
    PRBriefGenerated,
    SurfaceGapIdentified,
)
from lumina.signal.domain.ports import (
    ContentSyndicationPort,
    SignalRepositoryPort,
    StructuredDataSubmissionPort,
    WikidataSubmissionPort,
)
from lumina.signal.domain.services import (
    CoverageCalculationService,
    PRBriefGenerationService,
    SurfaceMappingService,
    SurfacePrioritizationService,
)
from lumina.signal.domain.value_objects import (
    ActionStatus,
    ActionType,
    PresenceStatus,
)


@dataclass(frozen=True)
class CreateDistributionPlanCommand:
    """Creates a distribution plan for a brand based on surface gaps and entity data.

    Orchestrates: SurfacePrioritizationService, SignalRepositoryPort, EventBusPort.
    """

    repository: SignalRepositoryPort
    event_bus: EventBusPort
    prioritization_service: SurfacePrioritizationService
    coverage_service: CoverageCalculationService

    async def execute(
        self,
        brand_id: str,
        surfaces: list[CitationSurface],
        brand_gaps: list[str],
    ) -> DistributionPlan:
        """Create and persist a distribution plan targeting prioritized surfaces.

        Args:
            brand_id: The brand to create the plan for.
            surfaces: All candidate citation surfaces.
            brand_gaps: List of surface IDs where the brand is absent.

        Returns:
            The persisted DistributionPlan with generated actions.
        """
        prioritized = self.prioritization_service.prioritize_surfaces(surfaces, brand_gaps)

        plan_id = str(uuid4())
        bid = BrandId(brand_id)
        now = datetime.now(UTC)

        # Generate an action for each surface where the brand is not fully present
        actions: list[DistributionAction] = []
        for surface in prioritized:
            if surface.brand_presence in (PresenceStatus.ABSENT, PresenceStatus.UNKNOWN):
                action_type = _infer_action_type(surface)
                actions.append(
                    DistributionAction(
                        id=str(uuid4()),
                        plan_id=plan_id,
                        surface_id=surface.id,
                        action_type=action_type,
                        content=f"Distribute brand presence to {surface.name}",
                        status=ActionStatus.PLANNED,
                        scheduled_at=now,
                    )
                )

        plan = DistributionPlan(
            id=plan_id,
            brand_id=bid,
            target_surfaces=tuple(prioritized),
            actions=tuple(actions),
            coverage_score=Score(0.0),
            created_at=now,
            domain_events=(
                DistributionPlanCreated(
                    aggregate_id=plan_id,
                    brand_id=brand_id,
                    total_actions=len(actions),
                    target_surface_count=len(prioritized),
                ),
            ),
        )

        # Emit surface gap events for absent surfaces
        gap_events = []
        for surface in prioritized:
            if surface.brand_presence == PresenceStatus.ABSENT:
                gap_events.append(
                    SurfaceGapIdentified(
                        aggregate_id=plan_id,
                        brand_id=brand_id,
                        surface_name=surface.name,
                        category=surface.category.value,
                        estimated_impact=surface.estimated_llm_weight.value,
                    )
                )

        all_events = list(plan.domain_events) + gap_events

        await self.repository.save_plan(plan)
        await self.event_bus.publish(all_events)

        return plan.clear_events()


@dataclass(frozen=True)
class ExecuteDistributionActionCommand:
    """Executes a single distribution action, updates status, and publishes events.

    Routes the action to the appropriate infrastructure adapter based on action type.
    """

    repository: SignalRepositoryPort
    event_bus: EventBusPort
    structured_data_port: StructuredDataSubmissionPort
    syndication_port: ContentSyndicationPort
    wikidata_port: WikidataSubmissionPort

    async def execute(
        self,
        plan_id: str,
        action_id: str,
    ) -> DistributionPlan:
        """Execute an action within a plan and update the plan state.

        Args:
            plan_id: The distribution plan containing the action.
            action_id: The specific action to execute.

        Returns:
            The updated DistributionPlan.

        Raises:
            ValueError: If the plan or action is not found.
        """
        plan = await self.repository.get_plan(plan_id)
        if plan is None:
            raise ValueError(f"Distribution plan {plan_id} not found")

        # Find the action to execute
        target_action: DistributionAction | None = None
        for action in plan.actions:
            if action.id == action_id:
                target_action = action
                break

        if target_action is None:
            raise ValueError(f"Action {action_id} not found in plan {plan_id}")

        # Execute via the appropriate adapter
        result_url = await self._route_action(target_action)

        # Mark complete on the aggregate (collects SignalDistributed event)
        updated_plan = plan.mark_action_complete(action_id, result_url)

        # Recalculate coverage (may collect CoverageUpdated event)
        updated_plan = updated_plan.calculate_coverage()

        await self.repository.save_plan(updated_plan)
        await self.event_bus.publish(list(updated_plan.domain_events))

        return updated_plan.clear_events()

    async def _route_action(self, action: DistributionAction) -> str:
        """Route an action to the correct infrastructure adapter."""
        if action.action_type == ActionType.SUBMIT_STRUCTURED_DATA:
            success = await self.structured_data_port.submit_to_google_search_console(
                action.content
            )
            return "https://search.google.com/search-console" if success else ""

        elif action.action_type == ActionType.UPDATE_WIKIDATA:
            wikidata_id = await self.wikidata_port.create_entity(
                {"description": action.content}
            )
            return f"https://www.wikidata.org/wiki/{wikidata_id}"

        elif action.action_type == ActionType.SYNDICATE_ARTICLE:
            return await self.syndication_port.syndicate_to_platform(
                "news", action.content
            )

        elif action.action_type == ActionType.PUBLISH_CONTENT:
            return await self.syndication_port.syndicate_to_platform(
                "content", action.content
            )

        elif action.action_type == ActionType.ENGAGE_COMMUNITY:
            return await self.syndication_port.syndicate_to_platform(
                "community", action.content
            )

        elif action.action_type == ActionType.SUBMIT_PR_BRIEF:
            return await self.syndication_port.syndicate_to_platform(
                "pr", action.content
            )

        return ""


@dataclass(frozen=True)
class GeneratePRBriefCommand:
    """Generates a PR brief for a brand using entity profile data."""

    repository: SignalRepositoryPort
    event_bus: EventBusPort
    brief_service: PRBriefGenerationService

    async def execute(
        self,
        brand_name: str,
        entity_data: dict[str, str],
        target_narrative: str,
    ) -> PRBrief:
        """Generate, persist, and publish a PR brief.

        Args:
            brand_name: The brand's display name.
            entity_data: Key-value pairs from the entity profile.
            target_narrative: The desired narrative angle.

        Returns:
            The generated PRBrief.
        """
        brief = self.brief_service.generate_brief(brand_name, entity_data, target_narrative)

        await self.repository.save_pr_brief(brief)

        event = PRBriefGenerated(
            aggregate_id=brief.id,
            brand_id=brief.brand_id.value,
            headline=brief.headline,
            target_publication_count=len(brief.target_publications),
        )
        await self.event_bus.publish([event])

        return brief


@dataclass(frozen=True)
class MapSurfacesCommand:
    """Identifies and maps all relevant citation surfaces for a brand."""

    repository: SignalRepositoryPort
    mapping_service: SurfaceMappingService

    async def execute(
        self,
        brand_id: str,
        brand_vertical: str,
    ) -> list[CitationSurface]:
        """Map surfaces for a brand's vertical and persist them.

        Args:
            brand_id: The brand identifier.
            brand_vertical: The industry vertical (e.g. 'technology', 'healthcare').

        Returns:
            List of mapped CitationSurface objects.
        """
        surfaces = self.mapping_service.map_surfaces_for_brand(brand_vertical)

        for surface in surfaces:
            await self.repository.save_surface(surface)

        return surfaces


def _infer_action_type(surface: CitationSurface) -> ActionType:
    """Infer the most appropriate action type for a citation surface based on its category."""
    category_to_action: dict[str, ActionType] = {
        "structured_data": ActionType.SUBMIT_STRUCTURED_DATA,
        "authority_publications": ActionType.PUBLISH_CONTENT,
        "qa_platforms": ActionType.ENGAGE_COMMUNITY,
        "developer_communities": ActionType.ENGAGE_COMMUNITY,
        "academic_research": ActionType.PUBLISH_CONTENT,
        "business_directories": ActionType.SUBMIT_STRUCTURED_DATA,
        "news_syndication": ActionType.SYNDICATE_ARTICLE,
    }
    return category_to_action.get(surface.category.value, ActionType.PUBLISH_CONTENT)
