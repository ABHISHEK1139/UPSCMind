"""
Hermes V2 — Topic Detection Node
═══════════════════════════════════════════════════════════════
First node in the answer-generation graph.  Classifies the
incoming UPSC question into domain, sub-topics, question type,
and constitutional weight.

Strategy
────────
1. **Primary path** — DSPy ``Predict(TopicDetectionSignature)``
   so the optimizer can later swap in compiled, few-shot prompts.
2. **Fallback path** — Raw LLM gateway call with a hand-crafted
   system prompt when DSPy is unavailable.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from domain.answer_generation.state import AnswerGenerationState
from domain.answer_generation.dspy_signatures import (
    TopicDetectionSignature,
    dspy_available,
)

logger = logging.getLogger(__name__)

# ── Fallback prompt (used when DSPy is not installed) ───────

_FALLBACK_SYSTEM_PROMPT = """\
You are a UPSC question classifier.  Given a question, return a
JSON object with EXACTLY these keys:

  domain             — one of: Polity, Economy, History, Geography,
                       Ethics, Science-Tech, Environment, IR, Society
  sub_topics         — list of relevant sub-topics (strings)
  question_type      — one of: factual, analytical, evaluative,
                       comparison, evolution
  constitutional_weight — one of: HIGH, MEDIUM, LOW, VERY_LOW

Return ONLY valid JSON, no markdown fences, no explanation.
"""


async def node_topic_detection(
    state: AnswerGenerationState,
) -> dict[str, Any]:
    """Detect the topic, type, and constitutional weight of a question.

    Parameters
    ----------
    state : AnswerGenerationState
        Must contain ``question``.

    Returns
    -------
    dict
        Partial state update with ``domain``, ``sub_topics``,
        ``question_type``, ``constitutional_weight``.
    """
    question: str = state["question"]
    t0 = time.monotonic()

    # ── DSPy path ───────────────────────────────────────────
    if dspy_available():
        import dspy

        predictor = dspy.Predict(TopicDetectionSignature)
        result = predictor(question=question)

        sub_topics_raw = getattr(result, "sub_topics", "")
        sub_topics = [
            s.strip() for s in sub_topics_raw.split(",") if s.strip()
        ]

        update = {
            "domain": result.domain,
            "sub_topics": sub_topics,
            "question_type": result.question_type,
            "constitutional_weight": result.constitutional_weight,
        }
        latency = (time.monotonic() - t0) * 1000
        logger.info(
            "[TOPIC_DETECTION] DSPy path | domain=%s | type=%s | %.0fms",
            update["domain"],
            update["question_type"],
            latency,
        )
        return update

    # ── LLM gateway fallback ────────────────────────────────
    from core.llm_gateway import LLMGateway

    gateway = LLMGateway()
    llm_response = gateway.complete(
        messages=[
            {"role": "system", "content": _FALLBACK_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.1,
        max_tokens=512,
    )

    try:
        parsed = json.loads(llm_response.content)
    except json.JSONDecodeError:
        logger.error(
            "[TOPIC_DETECTION] LLM returned invalid JSON: %s",
            llm_response.content[:300],
        )
        parsed = {
            "domain": "General Studies",
            "sub_topics": [],
            "question_type": "analytical",
            "constitutional_weight": "MEDIUM",
        }

    sub_topics = parsed.get("sub_topics", [])
    if isinstance(sub_topics, str):
        sub_topics = [s.strip() for s in sub_topics.split(",") if s.strip()]

    update = {
        "domain": parsed.get("domain", "General Studies"),
        "sub_topics": sub_topics,
        "question_type": parsed.get("question_type", "analytical"),
        "constitutional_weight": parsed.get("constitutional_weight", "MEDIUM"),
    }

    latency = (time.monotonic() - t0) * 1000
    logger.info(
        "[TOPIC_DETECTION] Gateway fallback | domain=%s | type=%s | "
        "model=%s | %.0fms",
        update["domain"],
        update["question_type"],
        llm_response.model_used,
        latency,
    )
    return update
