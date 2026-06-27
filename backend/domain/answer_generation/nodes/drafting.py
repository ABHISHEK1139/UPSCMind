"""
Hermes V2 — Drafting Node
═══════════════════════════════════════════════════════════════
Generates the first full-length draft answer (800-1200 words)
following the reasoning plan and structural framework produced
by the planning node.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from domain.answer_generation.state import AnswerGenerationState
from domain.answer_generation.dspy_signatures import (
    DraftAnswerSignature,
    dspy_available,
)

logger = logging.getLogger(__name__)

# ── Fallback prompt ─────────────────────────────────────────

_FALLBACK_SYSTEM = """\
You are an expert UPSC Mains answer writer.  Draft a complete,
well-structured answer of 800-1200 words.

Guidelines:
• Follow the structural framework and reasoning plan provided.
• Embed evidence from the retrieved context with brief citations.
• If constitutional_weight is HIGH, heavily reference Articles,
  Amendments, and judicial pronouncements.
• Include an engaging introduction, clearly delineated body
  paragraphs, and a forward-looking conclusion.
• Maintain an academic yet accessible tone.

Return ONLY the answer text — no metadata, no JSON wrapper.
"""


def _chunks_to_context(chunks: list[dict]) -> str:
    """Concatenate retrieved chunks into a single context string."""
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        source = c.get("source", "unknown")
        text = c.get("text", "")
        parts.append(f"[{i}] ({source}) {text}")
    return "\n\n".join(parts) if parts else "(no retrieved context)"


async def node_drafting(
    state: AnswerGenerationState,
) -> dict[str, Any]:
    """Draft the first complete answer.

    Parameters
    ----------
    state : AnswerGenerationState
        Must contain ``question``, ``domain``, ``reasoning_plan``,
        ``framework``, ``retrieved_chunks``, ``constitutional_weight``.

    Returns
    -------
    dict
        Partial state update with ``draft_answer`` and appended
        ``models_used``.
    """
    question: str = state["question"]
    domain: str = state.get("domain", "General Studies")
    reasoning_plan: str = state.get("reasoning_plan", "")
    framework: str = state.get("framework", "Thematic")
    constitutional_weight: str = state.get("constitutional_weight", "MEDIUM")
    chunks: list[dict] = state.get("retrieved_chunks", [])
    context = _chunks_to_context(chunks)

    existing_models: list[str] = list(state.get("models_used", []))
    t0 = time.monotonic()

    # ── DSPy path ───────────────────────────────────────────
    if dspy_available():
        import dspy

        predictor = dspy.Predict(DraftAnswerSignature)
        result = predictor(
            question=question,
            domain=domain,
            reasoning_plan=reasoning_plan,
            framework=framework,
            retrieved_context=context,
            constitutional_weight=constitutional_weight,
        )

        draft = result.answer
        model_tag = "dspy/default"
        existing_models.append(model_tag)

        latency = (time.monotonic() - t0) * 1000
        logger.info(
            "[DRAFTING] DSPy path | words=%d | %.0fms",
            len(draft.split()),
            latency,
        )
        return {
            "draft_answer": draft,
            "models_used": existing_models,
        }

    # ── LLM gateway fallback ────────────────────────────────
    from core.llm_gateway import LLMGateway

    gateway = LLMGateway()
    user_content = (
        f"Question: {question}\n"
        f"Domain: {domain}\n"
        f"Framework: {framework}\n"
        f"Constitutional Weight: {constitutional_weight}\n\n"
        f"Reasoning Plan:\n{reasoning_plan}\n\n"
        f"Retrieved Context:\n{context}"
    )

    llm_response = gateway.complete(
        messages=[
            {"role": "system", "content": _FALLBACK_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
        max_tokens=4096,
    )

    draft = llm_response.content.strip()
    existing_models.append(llm_response.model_used)

    latency = (time.monotonic() - t0) * 1000
    logger.info(
        "[DRAFTING] Gateway fallback | words=%d | model=%s | %.0fms",
        len(draft.split()),
        llm_response.model_used,
        latency,
    )

    return {
        "draft_answer": draft,
        "models_used": existing_models,
    }
