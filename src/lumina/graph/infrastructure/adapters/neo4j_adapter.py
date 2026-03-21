"""
Neo4j Adapter — Implements GraphRepositoryPort

Architectural Intent:
- Infrastructure adapter that maps domain entities to/from Neo4j graph nodes
- Uses the official neo4j async Python driver
- EntityProfile is a node, dimensions are related nodes, gaps are separate nodes
- All mapping logic is encapsulated here; the domain stays persistence-ignorant
"""

from __future__ import annotations

import json
from datetime import datetime, UTC

from neo4j import AsyncDriver, AsyncSession

from lumina.shared.domain.value_objects import BrandId, Score

from lumina.graph.domain.entities import EntityProfile, EntityDimension, KnowledgeGap
from lumina.graph.domain.value_objects import DimensionType, GapSeverity


class Neo4jGraphRepository:
    """Neo4j implementation of GraphRepositoryPort."""

    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    # ------------------------------------------------------------------
    # Profile persistence
    # ------------------------------------------------------------------

    async def save_profile(self, profile: EntityProfile) -> None:
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(self._save_profile_tx, profile)

    @staticmethod
    async def _save_profile_tx(tx: AsyncSession, profile: EntityProfile) -> None:
        # Upsert the profile node
        await tx.run(
            """
            MERGE (p:EntityProfile {id: $id})
            SET p.brand_id = $brand_id,
                p.name = $name,
                p.description = $description,
                p.health_score = $health_score,
                p.created_at = $created_at,
                p.updated_at = $updated_at
            """,
            id=profile.id,
            brand_id=profile.brand_id.value,
            name=profile.name,
            description=profile.description,
            health_score=profile.health_score.value,
            created_at=profile.created_at.isoformat(),
            updated_at=profile.updated_at.isoformat(),
        )

        # Remove existing dimension relationships and re-create
        await tx.run(
            """
            MATCH (p:EntityProfile {id: $id})-[r:HAS_DIMENSION]->(d:EntityDimension)
            DETACH DELETE d
            """,
            id=profile.id,
        )

        for dim in profile.dimensions:
            await tx.run(
                """
                MATCH (p:EntityProfile {id: $profile_id})
                CREATE (d:EntityDimension {
                    id: $dim_id,
                    dimension_type: $dimension_type,
                    data: $data,
                    completeness_score: $completeness_score,
                    sources: $sources,
                    last_verified_at: $last_verified_at
                })
                CREATE (p)-[:HAS_DIMENSION]->(d)
                """,
                profile_id=profile.id,
                dim_id=dim.id,
                dimension_type=dim.dimension_type.value,
                data=json.dumps(dict(dim.data)),
                completeness_score=dim.completeness_score.value,
                sources=json.dumps(list(dim.sources)),
                last_verified_at=dim.last_verified_at.isoformat(),
            )

    async def get_profile(self, profile_id: str) -> EntityProfile | None:
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(self._get_profile_tx, profile_id)

    @staticmethod
    async def _get_profile_tx(tx: AsyncSession, profile_id: str) -> EntityProfile | None:
        result = await tx.run(
            """
            MATCH (p:EntityProfile {id: $id})
            OPTIONAL MATCH (p)-[:HAS_DIMENSION]->(d:EntityDimension)
            RETURN p, collect(d) AS dimensions
            """,
            id=profile_id,
        )
        record = await result.single()
        if record is None:
            return None

        p = record["p"]
        dim_nodes = record["dimensions"]

        dimensions: list[EntityDimension] = []
        for d in dim_nodes:
            if d is None:
                continue
            data_dict: dict[str, str] = json.loads(d["data"])
            sources: list[str] = json.loads(d["sources"])
            dimensions.append(
                EntityDimension(
                    id=d["id"],
                    dimension_type=DimensionType(d["dimension_type"]),
                    data=tuple(sorted(data_dict.items())),
                    completeness_score=Score(d["completeness_score"]),
                    sources=tuple(sources),
                    last_verified_at=datetime.fromisoformat(d["last_verified_at"]),
                )
            )

        return EntityProfile(
            id=p["id"],
            brand_id=BrandId(p["brand_id"]),
            name=p["name"],
            description=p["description"],
            dimensions=tuple(dimensions),
            health_score=Score(p["health_score"]),
            created_at=datetime.fromisoformat(p["created_at"]),
            updated_at=datetime.fromisoformat(p["updated_at"]),
            domain_events=(),
        )

    async def list_profiles_for_brand(self, brand_id: str) -> list[EntityProfile]:
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(self._list_profiles_tx, brand_id)

    @staticmethod
    async def _list_profiles_tx(tx: AsyncSession, brand_id: str) -> list[EntityProfile]:
        result = await tx.run(
            """
            MATCH (p:EntityProfile {brand_id: $brand_id})
            OPTIONAL MATCH (p)-[:HAS_DIMENSION]->(d:EntityDimension)
            RETURN p, collect(d) AS dimensions
            ORDER BY p.created_at DESC
            """,
            brand_id=brand_id,
        )

        profiles: list[EntityProfile] = []
        async for record in result:
            p = record["p"]
            dim_nodes = record["dimensions"]

            dimensions: list[EntityDimension] = []
            for d in dim_nodes:
                if d is None:
                    continue
                data_dict: dict[str, str] = json.loads(d["data"])
                sources: list[str] = json.loads(d["sources"])
                dimensions.append(
                    EntityDimension(
                        id=d["id"],
                        dimension_type=DimensionType(d["dimension_type"]),
                        data=tuple(sorted(data_dict.items())),
                        completeness_score=Score(d["completeness_score"]),
                        sources=tuple(sources),
                        last_verified_at=datetime.fromisoformat(d["last_verified_at"]),
                    )
                )

            profiles.append(
                EntityProfile(
                    id=p["id"],
                    brand_id=BrandId(p["brand_id"]),
                    name=p["name"],
                    description=p["description"],
                    dimensions=tuple(dimensions),
                    health_score=Score(p["health_score"]),
                    created_at=datetime.fromisoformat(p["created_at"]),
                    updated_at=datetime.fromisoformat(p["updated_at"]),
                    domain_events=(),
                )
            )

        return profiles

    # ------------------------------------------------------------------
    # Gap persistence
    # ------------------------------------------------------------------

    async def save_gap(self, gap: KnowledgeGap) -> None:
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(self._save_gap_tx, gap)

    @staticmethod
    async def _save_gap_tx(tx: AsyncSession, gap: KnowledgeGap) -> None:
        await tx.run(
            """
            MERGE (g:KnowledgeGap {id: $id})
            SET g.brand_id = $brand_id,
                g.dimension_type = $dimension_type,
                g.description = $description,
                g.severity = $severity,
                g.identified_from = $identified_from,
                g.recommended_action = $recommended_action
            """,
            id=gap.id,
            brand_id=gap.brand_id.value,
            dimension_type=gap.dimension_type.value,
            description=gap.description,
            severity=gap.severity.value,
            identified_from=gap.identified_from.value if gap.identified_from else None,
            recommended_action=gap.recommended_action,
        )

    async def get_gaps_for_brand(self, brand_id: str) -> list[KnowledgeGap]:
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(self._get_gaps_tx, brand_id)

    @staticmethod
    async def _get_gaps_tx(tx: AsyncSession, brand_id: str) -> list[KnowledgeGap]:
        from lumina.shared.domain.value_objects import AIEngine

        result = await tx.run(
            """
            MATCH (g:KnowledgeGap {brand_id: $brand_id})
            RETURN g
            ORDER BY
                CASE g.severity
                    WHEN 'critical' THEN 0
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END
            """,
            brand_id=brand_id,
        )

        gaps: list[KnowledgeGap] = []
        async for record in result:
            g = record["g"]
            identified_from = None
            if g["identified_from"] is not None:
                identified_from = AIEngine(g["identified_from"])

            gaps.append(
                KnowledgeGap(
                    id=g["id"],
                    brand_id=BrandId(g["brand_id"]),
                    dimension_type=DimensionType(g["dimension_type"]),
                    description=g["description"],
                    severity=GapSeverity(g["severity"]),
                    identified_from=identified_from,
                    recommended_action=g["recommended_action"],
                )
            )

        return gaps
