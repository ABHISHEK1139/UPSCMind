"""
Hermes V2 — Cross-Encoder Reranker
═══════════════════════════════════════════════════════════════
Second-stage reranker using a cross-encoder model to rescore
retrieved chunks against the original query.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from domain.retrieval.hybrid_retriever import RetrievedChunk

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """Reranks RetrievedChunk lists using a cross-encoder."""

    def __init__(
        self,
        model_name: str = CROSS_ENCODER_MODEL,
        *,
        device: Optional[str] = None,
    ) -> None:
        self._model: Any = None

        if CrossEncoder is None:
            logger.warning(
                "[RERANKER] sentence-transformers not installed — "
                "reranking disabled; results will be truncated only."
            )
            return

        try:
            kwargs: dict[str, Any] = {}
            if device is not None:
                kwargs["device"] = device
            self._model = CrossEncoder(model_name, **kwargs)
            logger.info("[RERANKER] Cross-encoder loaded: %s", model_name)
        except Exception as exc:
            logger.warning("[RERANKER] Failed to load cross-encoder: %s", exc)

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """
        Rerank chunks by cross-encoder score and return the top_k.

        Parameters
        ----------
        query : str
            The original question.
        chunks : list[RetrievedChunk]
            Candidate chunks from the first-stage retriever.
        top_k : int
            Number of chunks to return.

        Returns
        -------
        list[RetrievedChunk]
            Reranked chunks (highest score first).
        """
        if self._model is None or not chunks:
            return chunks[:top_k]

        try:
            pairs = [(query, chunk.text) for chunk in chunks]
            scores = self._model.predict(pairs)

            for chunk, score in zip(chunks, scores):
                chunk.score = float(score)

            chunks.sort(key=lambda c: c.score, reverse=True)
            return chunks[:top_k]
        except Exception as exc:
            logger.warning("[RERANKER] Reranking failed: %s", exc)
            return chunks[:top_k]
