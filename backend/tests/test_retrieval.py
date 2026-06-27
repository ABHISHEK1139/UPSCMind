"""
Hermes V2 — Retrieval Tests
═══════════════════════════════════════════════════════════════
Tests for the hybrid retrieval pipeline.
"""

from __future__ import annotations

import pytest


class TestRetrievalRouter:
    """Test retrieval strategy routing."""

    def test_graph_strategy_for_relationship(self):
        from domain.retrieval.router import RetrievalRouter, RetrievalStrategy
        router = RetrievalRouter()
        strategy = router.select_strategy("relationship")
        assert strategy == RetrievalStrategy.GRAPH_ONLY

    def test_hybrid_strategy_for_factual(self):
        from domain.retrieval.router import RetrievalRouter, RetrievalStrategy
        router = RetrievalRouter()
        strategy = router.select_strategy("factual")
        assert strategy == RetrievalStrategy.HYBRID_ONLY

    def test_hybrid_and_graph_for_evolution(self):
        from domain.retrieval.router import RetrievalRouter, RetrievalStrategy
        router = RetrievalRouter()
        strategy = router.select_strategy("evolution")
        assert strategy == RetrievalStrategy.HYBRID_AND_GRAPH


class TestHybridRetriever:
    """Test hybrid retriever."""

    def test_rrf_fusion(self):
        from domain.retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk

        chunks_a = [
            RetrievedChunk(text="Chunk A", score=0.9),
            RetrievedChunk(text="Chunk B", score=0.8),
        ]
        chunks_b = [
            RetrievedChunk(text="Chunk B", score=0.85),
            RetrievedChunk(text="Chunk C", score=0.75),
        ]
        fused = HybridRetriever._reciprocal_rank_fusion(chunks_a, chunks_b, k=3)
        assert len(fused) == 3
        # Chunk B should be first (appears in both lists)
        assert fused[0].text == "Chunk B"


class TestReranker:
    """Test cross-encoder reranker."""

    def test_rerank_without_model(self):
        """Reranker should gracefully handle missing model."""
        from domain.retrieval.reranker import CrossEncoderReranker, RetrievedChunk

        reranker = CrossEncoderReranker()
        chunks = [
            RetrievedChunk(text="Chunk A", score=0.5),
            RetrievedChunk(text="Chunk B", score=0.3),
        ]
        result = reranker.rerank("test query", chunks, top_k=1)
        assert len(result) == 1
