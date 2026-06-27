"""
Hermes V2 — Graph Retriever
═══════════════════════════════════════════════════════════════
Traverses the Neo4j knowledge graph for relationship, timeline,
and cross-entity queries that pure vector search cannot answer.

All Cypher queries use **parameterized** bindings ($entity, $year,
etc.) — *never* string interpolation — to prevent injection.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from domain.retrieval.hybrid_retriever import RetrievedChunk

logger = logging.getLogger(__name__)

try:
    from neo4j import AsyncSession
except ImportError:
    AsyncSession = None


class GraphRetriever:
    """Neo4j-backed graph traversal for UPSC knowledge retrieval."""

    def __init__(self, neo4j_driver: Optional[Any] = None) -> None:
        self._driver = neo4j_driver
        if self._driver is None:
            try:
                from core.db_neo4j import get_neo4j_driver
                self._driver = get_neo4j_driver()
                logger.info("[GRAPH_RETRIEVER] Neo4j driver acquired.")
            except Exception as exc:
                logger.warning("[GRAPH_RETRIEVER] Neo4j driver unavailable: %s", exc)

    def _available(self) -> bool:
        if self._driver is None:
            logger.warning("[GRAPH_RETRIEVER] Neo4j driver is not configured.")
            return False
        return True

    async def _run_query(
        self, cypher: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Execute a parameterized Cypher query and return records as dicts."""
        if not self._available():
            return []
        try:
            from core.db_neo4j import execute_cypher
            return await execute_cypher(cypher, params)
        except Exception as exc:
            logger.error("[GRAPH_RETRIEVER] Query failed: %s", exc)
            return []

    async def query_relationships(
        self, entity: str, max_depth: int = 2
    ) -> list[RetrievedChunk]:
        """Find relationships for a given entity."""
        cypher = """
        MATCH (e:Entity {name: $entity})-[r*1..$depth]-(related:Entity)
        RETURN e.name AS source, type(r[0]) AS relationship,
               related.name AS target, related.description AS description
        LIMIT 20
        """
        records = await self._run_query(
            cypher, {"entity": entity, "depth": max_depth}
        )
        return [
            RetrievedChunk(
                text=f"{r['source']} —[{r['relationship']}]→ {r['target']}: {r.get('description', '')}",
                source="neo4j",
                score=1.0,
                metadata={"type": "relationship"},
            )
            for r in records
        ]

    async def query_timeline(
        self, entity: str, start_year: int = 1947, end_year: int = 2025
    ) -> list[RetrievedChunk]:
        """Trace the evolution of an entity over time."""
        cypher = """
        MATCH (e:Entity {name: $entity})-[r]->(event:Event)
        WHERE event.year >= $start_year AND event.year <= $end_year
        RETURN event.year AS year, event.description AS description,
               type(r) AS relation
        ORDER BY event.year
        """
        records = await self._run_query(
            cypher,
            {"entity": entity, "start_year": start_year, "end_year": end_year},
        )
        return [
            RetrievedChunk(
                text=f"[{r['year']}] {r['description']}",
                source="neo4j_timeline",
                score=1.0,
                metadata={"type": "timeline", "year": r["year"]},
            )
            for r in records
        ]

    async def query_amendment_chain(
        self, article: str
    ) -> list[RetrievedChunk]:
        """Trace the amendment chain for a constitutional article."""
        cypher = """
        MATCH (a:Article {number: $article})-[:AMENDED_BY]->(amendment:Amendment)
        RETURN amendment.number AS amendment_no,
               amendment.year AS year,
               amendment.description AS description
        ORDER BY amendment.year
        """
        records = await self._run_query(cypher, {"article": article})
        return [
            RetrievedChunk(
                text=f"Amendment {r['amendment_no']} ({r['year']}): {r['description']}",
                source="neo4j_amendments",
                score=1.0,
                metadata={"type": "amendment_chain"},
            )
            for r in records
        ]

    async def query_institutional_interaction(
        self, entity: str
    ) -> list[RetrievedChunk]:
        """Find how an institution interacts with other entities."""
        cypher = """
        MATCH (e:Institution {name: $entity})-[r]->(other:Entity)
        WHERE type(r) IN ['oversees', 'advises', 'checks', 'balances', 'reports_to']
        RETURN type(r) AS interaction, other.name AS target,
               other.type AS target_type
        LIMIT 15
        """
        records = await self._run_query(cypher, {"entity": entity})
        return [
            RetrievedChunk(
                text=f"{entity} —[{r['interaction']}]→ {r['target']} ({r.get('target_type', 'unknown')})",
                source="neo4j_institutional",
                score=1.0,
                metadata={"type": "institutional_interaction"},
            )
            for r in records
        ]
