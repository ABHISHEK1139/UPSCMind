"""
Hermes V2 — Improvement Node
═══════════════════════════════════════════════════════════════
Rewrites the current answer based on the critique produced by
the review node.  The orchestrator may invoke this node up to
``MAX_ITERATIONS`` times in a review → improve loop.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from domain.answer_generation.state import AnswerGenerationState
from domain.answer_generation.dspy_signatures import (
    ImprovementSignature,
    dspy_available,
)

logger = logging.getLogger(__name__)

# ── Fallback prompt ─────────────────────────────────────────

_FALLBACK_SYSTEM = """\
You are a UPSC answer improvement specialist.  You receive:
  • The original question
  • The current draft answer
  • A detailed critique with actionable suggestions

Rewrite the answer so that every weakness in the critique is
addressed while preserving existing strengths.  Maintain the
structural framework. Target 800-1200 words.

Return ONLY the improved answer text — no commentary.
"""


def _current_answer(state: AnswerGenerationState) -> str:
    """Return the latest answer version — improved if available."""
    return state.get("improved_answer") or state.get("draft_answer", "")


async def node_improvement(
    state: AnswerGenerationState,
) -> dict[str, Any]:
    """Improve the answer based on critique feedback.

    Parameters
    ----------
    state : AnswerGenerationState
        Must contain ``question``, ``domain``, ``critique``,
        ``framework``, and either ``draft_answer`` or
        ``improved_answer``.

    Returns
    -------
    dict
        Partial state update with ``improved_answer`` and
        incremented ``iterations``.
    """
    question: str = state["question"]
    domain: str = state.get("domain", "General Studies")
    critique: str = state.get("critique", "")
    framework: str = state.get("framework", "Thematic")
    answer = _current_answer(state)
    current_iterations: int = state.get("iterations", 0)

    t0 = time.monotonic()

    # ── DSPy path ───────────────────────────────────────────
    if dspy_available():
        import dspy

        predictor = dspy.Predict(ImprovementSignature)
        result = predictor(
            question=question,
            domain=domain,
            answer=answer,
            critique=critique,
            framework=framework,
        )

        improved = result.improved_answer
        latency = (time.monotonic() - t0) * 1000
        logger.info(
            "[IMPROVEMENT] DSPy path | iteration=%d | words=%d | %.0fms",
            current_iterations + 1,
            len(improved.split()),
            latency,
        )
        return {
            "improved_answer": improved,
            "iterations": current_iterations + 1,
        }

    # ── LLM gateway fallback ────────────────────────────────
    from core.llm_gateway import LLMGateway

    gateway = LLMGateway()
    user_content = (
        f"Question: {question}\n"
        f"Domain: {domain}\n"
        f"Framework: {framework}\n\n"
        f"Current Answer:\n{answer}\n\n"
        f"Critique:\n{critique}"
    )

    llm_response = await gateway.complete(
        messages=[
            {"role": "system", "content": _FALLBACK_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.35,
        max_tokens=4096,
    )

    improved = llm_response.content.strip()
    latency = (time.monotonic() - t0) * 1000
    logger.info(
        "[IMPROVEMENT] Gateway fallback | iteration=%d | words=%d | "
        "model=%s | %.0fms",
        current_iterations + 1,
        len(improved.split()),
        llm_response.model_used,
        latency,
    )

    return {
        "improved_answer": improved,
        "iterations": current_iterations + 1,
    }
