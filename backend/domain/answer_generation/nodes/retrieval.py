"""
Hermes V2 — Retrieval Node
═══════════════════════════════════════════════════════════════
Routes retrieval based on question type and domain, then fetches
the most relevant knowledge chunks.

Routing strategy
────────────────
• *factual / comparison* → ``hybrid_only``   (BM25 + semantic)
• *evolution / analytical* → ``hybrid_and_graph``  (hybrid + KG)
• *evaluative* → ``graph_only``   (knowledge graph for deep links)

The actual retrieval is delegated to ``domain.retrieval.router``
when it exists; otherwise a stub returns empty chunks so the
rest of the pipeline can still run during development.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from domain.answer_generation.state import AnswerGenerationState

logger = logging.getLogger(__name__)

# ── Strategy routing table ──────────────────────────────────

_STRATEGY_MAP: dict[str, str] = {
    "factual": "hybrid_only",
    "comparison": "hybrid_only",
    "evolution": "hybrid_and_graph",
    "analytical": "hybrid_and_graph",
    "evaluative": "graph_only",
}


async def node_retrieval(
    state: AnswerGenerationState,
) -> dict[str, Any]:
    """Retrieve relevant knowledge chunks for the question.

    Parameters
    ----------
    state : AnswerGenerationState
        Must contain ``question``, ``domain``, ``question_type``,
        and ``sub_topics``.

    Returns
    -------
    dict
        Partial state update with ``retrieval_strategy`` and
        ``retrieved_chunks``.
    """
    question: str = state["question"]
    question_type: str = state.get("question_type", "analytical")
    domain: str = state.get("domain", "General Studies")
    sub_topics: list[str] = state.get("sub_topics", [])

    strategy = _STRATEGY_MAP.get(question_type, "hybrid_and_graph")
    t0 = time.monotonic()

    # ── Try the real retrieval router ───────────────────────
    try:
        from domain.retrieval.router import RetrievalRouter  # type: ignore[import]

        router = RetrievalRouter()
        chunks = await router.retrieve(
            query=question,
            domain=domain,
            sub_topics=sub_topics,
            strategy=strategy,
        )
        retrieved = [
            {
                "text": c.text,
                "source": getattr(c, "source", "unknown"),
                "score": getattr(c, "score", 0.0),
                "metadata": getattr(c, "metadata", {}),
            }
            for c in chunks
        ]

    except (ImportError, ModuleNotFoundError):
        logger.warning(
            "[RETRIEVAL] domain.retrieval.router not available — "
            "returning empty chunks (dev mode)."
        )
        retrieved = []

    except Exception as exc:
        logger.error("[RETRIEVAL] Unexpected error: %s", exc, exc_info=True)
        retrieved = []

    latency = (time.monotonic() - t0) * 1000
    logger.info(
        "[RETRIEVAL] strategy=%s | chunks=%d | %.0fms",
        strategy,
        len(retrieved),
        latency,
    )

    return {
        "retrieval_strategy": strategy,
        "retrieved_chunks": retrieved,
    }
