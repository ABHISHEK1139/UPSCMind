"""
Hermes V2 — Answer Similarity Metric
═══════════════════════════════════════════════════════════════
Embedding-based similarity between generated answer and
reference answer.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from domain.evaluation.metrics import Metric, MetricResult

logger = logging.getLogger(__name__)


class AnswerSimilarityMetric(Metric):
    """Cosine similarity between answer embeddings."""

    def name(self) -> str:
        return "answer_similarity"

    def evaluate(
        self,
        question: str,
        answer: str,
        context: list[str] = None,
        reference: str = None,
    ) -> MetricResult:
        if not reference:
            return MetricResult(name=self.name(), score=0.0, details="No reference answer provided.")
        try:
            from core.llm_gateway import LLMGateway
            gateway = LLMGateway()
            import asyncio
            embeddings = asyncio.run(
                gateway.embed([answer, reference])
            )
            emb_a = np.array(embeddings[0])
            emb_r = np.array(embeddings[1])
            similarity = float(np.dot(emb_a, emb_r) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_r)))
            return MetricResult(name=self.name(), score=similarity, details=f"Cosine similarity: {similarity:.4f}")
        except Exception as exc:
            logger.warning("[SIMILARITY] Evaluation failed: %s", exc)
            return MetricResult(name=self.name(), score=0.0, details=str(exc))
