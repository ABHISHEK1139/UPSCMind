"""
Hermes V2 — L4 Knowledge Memory
═══════════════════════════════════════════════════════════════
Read-only layer over the permanent UPSC syllabus knowledge base.
Queries two complementary stores:

  • **Qdrant** for dense-vector semantic search over chunked documents.
  • **Neo4j**  for graph traversal (entity → relations → concepts).
"""

import logging
from typing import Any

from core.db_qdrant import get_qdrant_client
from core.db_neo4j import get_neo4j_driver

logger = logging.getLogger(__name__)

_DEFAULT_COLLECTION = "hermes_knowledge"


class KnowledgeMemory:
    """L4 — permanent syllabus knowledge backed by Qdrant + Neo4j."""

    def __init__(
        self,
        collection: str = _DEFAULT_COLLECTION,
        embedding_dim: int = 384,
    ) -> None:
        self._collection = collection
        self._embedding_dim = embedding_dim
        self._qdrant = get_qdrant_client()
        self._neo4j = get_neo4j_driver()

    async def search_semantic(self, query: str, top_k: int = 5) -> list[dict]:
        """Vector-similarity search over syllabus chunks.

        Note: The caller must embed the query before calling.
        """
        try:
            from qdrant_client.http.models import models as qmodels

            # TODO: replace with real embedding call via LLMGateway
            query_vector = [0.0] * self._embedding_dim

            from qdrant_client.models import models as qmodels
            try:
                result_points = self._qdrant.query_points(
                    collection_name=self._collection,
                    query=query_vector,
                    limit=top_k,
                    with_payload=True,
                )
                points = result_points.points
            except (AttributeError, TypeError):
                points = self._qdrant.search(
                    collection_name=self._collection,
                    query_vector=query_vector,
                    limit=top_k,
                    with_payload=True,
                )
            return [
                {
                    "text": r.payload.get("text", ""),
                    "score": float(r.score),
                    "metadata": dict(r.payload),
                }
                for r in points
            ]
        except Exception as exc:
            logger.error("[KNOWLEDGE] Semantic search failed: %s", exc)
            return []

    async def search_graph(self, entity: str, max_depth: int = 2) -> list[dict]:
        """Graph traversal for entity relationships."""
        try:
            from core.db_neo4j import execute_cypher
            cypher = """
            MATCH (e:Entity {name: $entity})-[r*1..$depth]-(related:Entity)
            RETURN e.name AS source, type(r[0]) AS rel, related.name AS target
            LIMIT 20
            """
            return await execute_cypher(cypher, {"entity": entity, "depth": max_depth})
        except Exception as exc:
            logger.error("[KNOWLEDGE] Graph search failed: %s", exc)
            return []
