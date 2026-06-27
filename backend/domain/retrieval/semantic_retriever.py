"""
Semantic Retriever — Runtime embedding + Qdrant search
═══════════════════════════════════════════════════════════════
Replaces PrecomputedRetriever with actual runtime embedding generation.

Flow:
  Question → Embed (LLMGateway) → Qdrant Vector Search → Evidence Chunks

This is the PRIMARY retrieval path for the V3 pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.db_qdrant import get_qdrant_client

logger = logging.getLogger(__name__)

KNOWLEDGE_COLLECTION = "hermes_knowledge"


class SemanticRetriever:
    """Runtime semantic search using LLMGateway for embeddings."""

    def __init__(
        self,
        collection: str = KNOWLEDGE_COLLECTION,
    ):
        self._collection = collection
        self._client = None

    def _get_client(self):
        """Lazy-initialize Qdrant client."""
        if self._client is None:
            self._client = get_qdrant_client()
        return self._client

    async def search(
        self,
        query: str,
        top_k: int = 5,
        domain_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using runtime embedding.

        Args:
            query: The search query (question text)
            top_k: Number of results to return
            domain_filter: Optional domain to filter by

        Returns:
            List of knowledge chunks with text, score, source
        """
        if not query or not query.strip():
            logger.warning("[SEMANTIC] Empty query, returning empty results")
            return []

        try:
            # Step 1: Generate embedding for the query
            from core.llm_gateway import LLMGateway
            gateway = LLMGateway()
            embeddings = await gateway.embed([query])

            if not embeddings or not embeddings[0]:
                logger.warning("[SEMANTIC] Failed to generate embedding")
                return []

            query_vector = embeddings[0]

            # Step 2: Search Qdrant
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            search_filter = None
            if domain_filter:
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="domain",
                            match=MatchValue(value=domain_filter),
                        )
                    ]
                )

            # Use query_points for Qdrant 1.18+
            client = self._get_client()
            result_points = client.query_points(
                collection_name=self._collection,
                query=query_vector,
                limit=top_k,
                query_filter=search_filter,
                with_payload=True,
                score_threshold=0.15,  # Minimum relevance threshold
            )

            # Step 3: Format results
            chunks = []
            points = result_points.points if hasattr(result_points, 'points') else result_points
            for point in points:
                payload = point.payload or {}
                chunks.append({
                    "text": payload.get("text", ""),
                    "score": float(point.score),
                    "source": payload.get("source", "unknown"),
                    "domain": payload.get("domain", "general"),
                    "metadata": {k: v for k, v in payload.items()
                               if k not in ("text", "source", "domain")},
                })

            logger.info("[SEMANTIC] Query='%s...' Results=%d", query[:50], len(chunks))
            return chunks

        except Exception as exc:
            logger.error("[SEMANTIC] Search failed: %s", exc)
            return []


async def ingest_knowledge_chunks(
    chunks: List[Dict[str, Any]],
    collection: str = KNOWLEDGE_COLLECTION,
) -> int:
    """
    Ingest knowledge chunks into Qdrant.

    Args:
        chunks: List of dicts with 'text', 'source', 'domain', etc.
        collection: Qdrant collection name

    Returns:
        Number of chunks ingested
    """
    if not chunks:
        return 0

    try:
        from core.llm_gateway import LLMGateway
        from qdrant_client.models import PointStruct

        gateway = LLMGateway()
        client = get_qdrant_client()

        # Generate embeddings for all chunks
        texts = [c.get("text", "") for c in chunks]
        embeddings = await gateway.embed(texts)

        if not embeddings:
            logger.error("[INGEST] Failed to generate embeddings")
            return 0

        # Create points
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            if not embedding:
                continue
            payload = {
                "text": chunk.get("text", ""),
                "source": chunk.get("source", "unknown"),
                "domain": chunk.get("domain", "general"),
                **{k: v for k, v in chunk.items()
                   if k not in ("text", "source", "domain")},
            }
            points.append(PointStruct(
                id=i,
                vector=embedding,
                payload=payload,
            ))

        # Upsert to Qdrant
        client.upsert(
            collection_name=collection,
            points=points,
        )

        logger.info("[INGEST] Ingested %d chunks into %s", len(points), collection)
        return len(points)

    except Exception as exc:
        logger.error("[INGEST] Failed: %s", exc)
        return 0
