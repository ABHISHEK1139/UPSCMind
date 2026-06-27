"""
Hermes V2 — Review Node
═══════════════════════════════════════════════════════════════
Critiques the current best answer (either the initial draft or
the latest improved version) against UPSC evaluation standards.

Produces a detailed critique and a 0.0-1.0 quality score.
The orchestrator uses ``quality_score`` to decide whether to
loop through the improvement node or proceed to verification.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from domain.answer_generation.state import AnswerGenerationState
from domain.answer_generation.dspy_signatures import (
    CritiqueSignature,
    dspy_available,
)

logger = logging.getLogger(__name__)

# ── Fallback prompt ─────────────────────────────────────────

_FALLBACK_SYSTEM = """\
You are a strict UPSC Mains answer evaluator.  Critically assess
the given answer on these dimensions:

  1. Factual accuracy
  2. Structural coherence and framework adherence
  3. Depth of analysis and critical thinking
  4. Constitutional / statutory grounding (weighted by constitutional_weight)
  5. Use of examples, data, and case studies
  6. Conclusion quality and forward-looking perspective

Return a JSON object with EXACTLY two keys:
  critique       — detailed textual critique with actionable improvements
  quality_score  — float from 0.0 (unusable) to 1.0 (exceptional)

Return ONLY valid JSON, no markdown fences.
"""


def _current_answer(state: AnswerGenerationState) -> str:
    """Return the latest answer version — improved if available."""
    return state.get("improved_answer") or state.get("draft_answer", "")


async def node_review(
    state: AnswerGenerationState,
) -> dict[str, Any]:
    """Critique the current answer and assign a quality score.

    Parameters
    ----------
    state : AnswerGenerationState
        Must contain at least ``question``, ``domain``, and either
        ``draft_answer`` or ``improved_answer``.

    Returns
    -------
    dict
        Partial state update with ``critique`` and ``quality_score``.
    """
    question: str = state["question"]
    domain: str = state.get("domain", "General Studies")
    constitutional_weight: str = state.get("constitutional_weight", "MEDIUM")
    answer = _current_answer(state)

    t0 = time.monotonic()

    # ── DSPy path ───────────────────────────────────────────
    if dspy_available():
        import dspy

        predictor = dspy.Predict(CritiqueSignature)
        result = predictor(
            question=question,
            domain=domain,
            answer=answer,
            constitutional_weight=constitutional_weight,
        )

        try:
            score = float(result.quality_score)
        except (TypeError, ValueError):
            score = 0.5

        score = max(0.0, min(1.0, score))

        update = {
            "critique": result.critique,
            "quality_score": score,
        }
        latency = (time.monotonic() - t0) * 1000
        logger.info(
            "[REVIEW] DSPy path | score=%.2f | %.0fms",
            score,
            latency,
        )
        return update

    # ── LLM gateway fallback ────────────────────────────────
    from core.llm_gateway import LLMGateway

    gateway = LLMGateway()
    user_content = (
        f"Question: {question}\n"
        f"Domain: {domain}\n"
        f"Constitutional Weight: {constitutional_weight}\n\n"
        f"Answer to evaluate:\n{answer}"
    )

    llm_response = gateway.complete(
        messages=[
            {"role": "system", "content": _FALLBACK_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        max_tokens=2048,
    )

    try:
        parsed = json.loads(llm_response.content)
        critique = parsed.get("critique", llm_response.content)
        score = float(parsed.get("quality_score", 0.5))
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning(
            "[REVIEW] Failed to parse JSON critique — using raw text."
        )
        critique = llm_response.content.strip()
        score = 0.5

    score = max(0.0, min(1.0, score))

    latency = (time.monotonic() - t0) * 1000
    logger.info(
        "[REVIEW] Gateway fallback | score=%.2f | model=%s | %.0fms",
        score,
        llm_response.model_used,
        latency,
    )

    return {
        "critique": critique,
        "quality_score": score,
    }
