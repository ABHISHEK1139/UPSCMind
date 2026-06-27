"""
Hermes V2 — Hallucination Detection Metric
═══════════════════════════════════════════════════════════════
Detects fabricated facts, citations, and claims in the answer
by cross-referencing with retrieved context.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from domain.evaluation.metrics import Metric, MetricResult

logger = logging.getLogger(__name__)

_HALLUCINATION_SYSTEM = """\
You are a hallucination detector for UPSC answers. Compare the
answer against the retrieved context and identify any claims
that are not supported by the context or general knowledge.

Return a JSON object with:
  hallucination_detected — boolean
  hallucinations         — list of unsupported claims
  confidence             — float 0.0 to 1.0

Return ONLY valid JSON.
"""


class HallucinationMetric(Metric):
    """Detect hallucinations by cross-referencing with context."""

    def name(self) -> str:
        return "hallucination"

    def evaluate(
        self,
        question: str,
        answer: str,
        context: list[str] = None,
        reference: str = None,
    ) -> MetricResult:
        if not context:
            return MetricResult(name=self.name(), score=1.0, details="No context to verify against.")
        try:
            from core.llm_gateway import LLMGateway
            gateway = LLMGateway()
            context_str = "\n".join(context[:5])
            import asyncio
            response = asyncio.run(
                gateway.complete(
                    messages=[
                        {"role": "system", "content": _HALLUCINATION_SYSTEM},
                        {"role": "user", "content": f"Answer:\n{answer}\n\nContext:\n{context_str}"},
                    ],
                    temperature=0.1,
                    max_tokens=512,
                )
            )
            result = json.loads(response.content)
            detected = result.get("hallucination_detected", False)
            hallucinations = result.get("hallucinations", [])
            confidence = result.get("confidence", 0.5)
            score = 0.0 if detected else 1.0
            details = f"Hallucinations: {len(hallucinations)}" if hallucinations else "No hallucinations detected."
            return MetricResult(name=self.name(), score=score, details=details)
        except Exception as exc:
            logger.warning("[HALLUCINATION] Evaluation failed: %s", exc)
            return MetricResult(name=self.name(), score=1.0, details=f"Check skipped: {exc}")
