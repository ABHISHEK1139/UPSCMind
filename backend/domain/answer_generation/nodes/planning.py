"""
Hermes V2 — Planning Node
═══════════════════════════════════════════════════════════════
Selects the answer framework, examiner persona, trap, and
differentiator, then produces a numbered reasoning plan that
the drafting node will follow.

Two DSPy signatures fire sequentially:
    FrameworkSelectionSignature  →  AnswerPlanSignature
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from domain.answer_generation.state import AnswerGenerationState
from domain.answer_generation.dspy_signatures import (
    FrameworkSelectionSignature,
    AnswerPlanSignature,
    dspy_available,
)

logger = logging.getLogger(__name__)

# ── Fallback prompts ────────────────────────────────────────

_FRAMEWORK_SYSTEM = """\
You are a UPSC answer strategist.  Given a question, its domain,
and question type, return JSON with these keys:

  framework       — e.g. PESTLE, Timeline, Pro-Con, Institutional, Thematic
  examiner_persona — one-line persona of the likely evaluator
  trap            — the most common student mistake for this question
  differentiator  — a single non-obvious insight that elevates the answer

Return ONLY valid JSON, no markdown fences.
"""

_PLAN_SYSTEM = """\
You are a UPSC answer planner. Given a question, domain, framework,
and retrieved context, produce a numbered step-by-step reasoning plan.
Include intro strategy, body paragraph themes with evidence to cite,
and conclusion hook.

Return ONLY the numbered plan as plain text.
"""


def _chunks_to_context(chunks: list[dict]) -> str:
    """Concatenate retrieved chunks into a single context string."""
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        source = c.get("source", "unknown")
        text = c.get("text", "")
        parts.append(f"[{i}] ({source}) {text}")
    return "\n\n".join(parts) if parts else "(no retrieved context)"


async def node_planning(
    state: AnswerGenerationState,
) -> dict[str, Any]:
    """Select framework and produce a reasoning plan.

    Parameters
    ----------
    state : AnswerGenerationState
        Must contain ``question``, ``domain``, ``question_type``,
        ``retrieved_chunks``.

    Returns
    -------
    dict
        Partial state update with ``framework``, ``examiner_persona``,
        ``trap``, ``differentiator``, ``reasoning_plan``.
    """
    question: str = state["question"]
    domain: str = state.get("domain", "General Studies")
    question_type: str = state.get("question_type", "analytical")
    chunks: list[dict] = state.get("retrieved_chunks", [])
    context = _chunks_to_context(chunks)

    t0 = time.monotonic()

    # ── DSPy path ───────────────────────────────────────────
    if dspy_available():
        import dspy

        # Step 1 — Framework selection
        fw_pred = dspy.Predict(FrameworkSelectionSignature)
        fw_result = fw_pred(
            question=question,
            domain=domain,
            question_type=question_type,
        )

        framework = fw_result.framework
        examiner_persona = fw_result.examiner_persona
        trap = fw_result.trap
        differentiator = fw_result.differentiator

        # Step 2 — Reasoning plan
        plan_pred = dspy.Predict(AnswerPlanSignature)
        plan_result = plan_pred(
            question=question,
            domain=domain,
            framework=framework,
            retrieved_context=context,
        )

        update = {
            "framework": framework,
            "examiner_persona": examiner_persona,
            "trap": trap,
            "differentiator": differentiator,
            "reasoning_plan": plan_result.reasoning_plan,
        }
        latency = (time.monotonic() - t0) * 1000
        logger.info(
            "[PLANNING] DSPy path | framework=%s | %.0fms",
            framework,
            latency,
        )
        return update

    # ── LLM gateway fallback ────────────────────────────────
    from core.llm_gateway import LLMGateway

    gateway = LLMGateway()

    # Step 1 — Framework selection via gateway
    fw_response = gateway.complete(
        messages=[
            {"role": "system", "content": _FRAMEWORK_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"Domain: {domain}\n"
                    f"Question Type: {question_type}"
                ),
            },
        ],
        temperature=0.2,
        max_tokens=512,
    )

    try:
        fw_parsed = json.loads(fw_response.content)
    except json.JSONDecodeError:
        logger.error(
            "[PLANNING] Framework LLM returned invalid JSON: %s",
            fw_response.content[:300],
        )
        fw_parsed = {
            "framework": "Thematic",
            "examiner_persona": "Senior UPSC examiner with domain expertise",
            "trap": "Superficial treatment without evidence",
            "differentiator": "Link to recent policy developments",
        }

    framework = fw_parsed.get("framework", "Thematic")
    examiner_persona = fw_parsed.get("examiner_persona", "")
    trap = fw_parsed.get("trap", "")
    differentiator = fw_parsed.get("differentiator", "")

    # Step 2 — Reasoning plan via gateway
    plan_response = gateway.complete(
        messages=[
            {"role": "system", "content": _PLAN_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n"
                    f"Domain: {domain}\n"
                    f"Framework: {framework}\n\n"
                    f"Retrieved Context:\n{context}"
                ),
            },
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    update = {
        "framework": framework,
        "examiner_persona": examiner_persona,
        "trap": trap,
        "differentiator": differentiator,
        "reasoning_plan": plan_response.content.strip(),
    }

    latency = (time.monotonic() - t0) * 1000
    logger.info(
        "[PLANNING] Gateway fallback | framework=%s | model=%s | %.0fms",
        framework,
        fw_response.model_used,
        latency,
    )
    return update
