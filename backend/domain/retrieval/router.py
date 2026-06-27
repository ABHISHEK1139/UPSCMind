"""
Hermes V2 — Retrieval Router
═══════════════════════════════════════════════════════════════
Decides which retrieval strategy to use for a given question
and dispatches to the correct backend(s).

Strategy selection:
    GRAPH_ONLY          → relationship / timeline / evolution questions
    HYBRID_ONLY         → factual / descriptive / conceptual questions
    HYBRID_AND_GRAPH    → complex questions needing both
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from domain.retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk
from domain.retrieval.graph_retriever import GraphRetriever
from domain.retrieval.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)

_GRAPH_TOPIC_TYPES: frozenset[str] = frozenset(
    {
        "relationship",
        "timeline",
        "comparison",
        "constitutional_amendment_chain",
        "evolution",
        "institutional_interaction",
    }
)


class RetrievalStrategy(str, Enum):
    """Which retrieval backend(s) to activate."""

    HYBRID_ONLY = "hybrid_only"
    GRAPH_ONLY = "graph_only"
    HYBRID_AND_GRAPH = "hybrid_and_graph"


class RetrievalRouter:
    """Routes a question to the appropriate retriever(s)."""

    def __init__(
        self,
        hybrid_retriever: Optional[HybridRetriever] = None,
        graph_retriever: Optional[GraphRetriever] = None,
        reranker: Optional[CrossEncoderReranker] = None,
    ) -> None:
        self._hybrid = hybrid_retriever or HybridRetriever()
        self._graph = graph_retriever or GraphRetriever()
        self._reranker = reranker or CrossEncoderReranker()

    def select_strategy(self, question_type: str) -> RetrievalStrategy:
        """Select retrieval strategy based on question type."""
        # Graph-only types need knowledge graph traversal
        if question_type in ("relationship", "timeline", "constitutional_amendment_chain", "institutional_interaction"):
            return RetrievalStrategy.GRAPH_ONLY
        # Comparison and evolution need both semantic search and graph
        if question_type in ("evolution", "comparison"):
            return RetrievalStrategy.HYBRID_AND_GRAPH
        # Everything else uses hybrid (dense + sparse)
        return RetrievalStrategy.HYBRID_ONLY

    async def retrieve(
        self,
        question: str,
        question_type: str = "analytical",
        domain: str = "General Studies",
        top_k: int = 5,
    ) -> tuple[list[RetrievedChunk], RetrievalStrategy]:
        """
        Full retrieval pipeline: route → retrieve → rerank.

        Returns
        -------
        tuple[list[RetrievedChunk], RetrievalStrategy]
            The reranked chunks and the strategy used.
        """
        strategy = self.select_strategy(question_type)
        chunks: list[RetrievedChunk] = []

        if strategy == RetrievalStrategy.HYBRID_ONLY:
            chunks = await self._hybrid.search(question, top_k=top_k * 2)
        elif strategy == RetrievalStrategy.GRAPH_ONLY:
            chunks = await self._graph.query_relationships(question)
        elif strategy == RetrievalStrategy.HYBRID_AND_GRAPH:
            hybrid_chunks, graph_chunks = await asyncio.gather(
                self._hybrid.search(question, top_k=top_k * 2),
                self._graph.query_relationships(question),
            )
            chunks = hybrid_chunks + graph_chunks

        # Rerank
        if chunks:
            chunks = self._reranker.rerank(question, chunks, top_k=top_k)

        logger.info(
            "[ROUTER] strategy=%s question_type=%s chunks=%d",
            strategy.value, question_type, len(chunks),
        )
        return chunks, strategy


import asyncio  # needed for gather in HYBRID_AND_GRAPH
