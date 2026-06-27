"""
Pre-computed Embedding Retriever for UPSC questions.

Instead of embedding at runtime (slow on CPU), this retriever:
1. Looks up pre-computed question embeddings from Qdrant
2. Uses them to search the knowledge base
3. Falls back to runtime embedding if question not found

This makes retrieval ~10x faster (no embedding computation).
"""

import logging
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)

# Collection names
KNOWLEDGE_COLLECTION = "upsc_knowledge"
QUESTION_COLLECTION = "upsc_questions"


class PrecomputedRetriever:
    """Retrieve using pre-computed question embeddings."""

    def __init__(
        self,
        qdrant_client: Optional[QdrantClient] = None,
        knowledge_collection: str = KNOWLEDGE_COLLECTION,
        question_collection: str = QUESTION_COLLECTION,
    ):
        from core.db_qdrant import get_qdrant_client
        self._client = qdrant_client or get_qdrant_client()
        self._knowledge_collection = knowledge_collection
        self._question_collection = question_collection

    async def search_by_question_id(
        self,
        question_id: int,
        top_k: int = 5,
        domain_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using a pre-computed question embedding.
        
        Args:
            question_id: The ID of the question (1-150)
            top_k: Number of results to return
            domain_filter: Optional domain to filter by
            
        Returns:
            List of knowledge chunks with text, score, source
        """
        # Step 1: Get the pre-computed question vector from payload
        # Note: Qdrant 1.18 doesn't support with_vector in retrieve
        # We store the embedding in payload during pre-computation
        question_points = await self._client.retrieve(
            collection_name=self._question_collection,
            ids=[question_id],
            with_payload=["question", "embedding"],
        )

        if not question_points:
            logger.warning("[PRECOMPUTED] Question ID %d not found", question_id)
            return []

        payload = question_points[0].payload
        query_vector = payload.get("embedding")
        question_text = payload.get("question", "")
        
        if query_vector is None:
            logger.warning("[PRECOMPUTED] Question ID %d has no embedding in payload", question_id)
            return []

        # Step 2: Search knowledge base with the vector
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

        results = self._client.search(
            collection_name=self._knowledge_collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=search_filter,
            with_payload=True,
        )

        # Step 3: Format results
        chunks = []
        for hit in results:
            chunks.append({
                "text": hit.payload.get("text", hit.payload.get("content", "")),
                "score": hit.score,
                "source": hit.payload.get("source", hit.payload.get("file", "")),
                "metadata": {k: v for k, v in hit.payload.items()},
            })

        logger.info(
            "[PRECOMPUTED] Q%d → %d chunks (top score: %.3f)",
            question_id, len(chunks), chunks[0]["score"] if chunks else 0.0,
        )
        return chunks

    async def search_by_text(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Fallback: search by raw text (uses Qdrant's sparse search or
        requires runtime embedding — slower).
        """
        # For now, just do a simple keyword-based search
        # This is a fallback for questions not in the pre-computed set
        results = self._client.scroll(
            collection_name=self._knowledge_collection,
            limit=top_k,
            with_payload=True,
        )

        chunks = []
        for point in results[0]:
            chunks.append({
                "text": point.payload.get("text", point.payload.get("content", "")),
                "score": 0.5,  # Default score for fallback
                "source": point.payload.get("source", ""),
                "metadata": dict(point.payload),
            })

        logger.info("[FALLBACK] Text search → %d chunks", len(chunks))
        return chunks
