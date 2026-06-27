"""
Hermes V2 — UPSC Quality Rubric
═══════════════════════════════════════════════════════════════
UPSC-specific quality evaluation based on the official marking
scheme: structure, depth, examples, constitutional grounding,
and presentation.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from domain.evaluation.metrics import Metric, MetricResult

logger = logging.getLogger(__name__)

_UPSC_QUALITY_SYSTEM = """\
You are a UPSC Mains evaluator. Assess the answer on these
dimensions (each scored 0.0 to 1.0):

1. Structure — Does it have intro, body, conclusion? Proper headings?
2. Depth — Multi-dimensional analysis? Cause-effect? Critical thinking?
3. Examples — Relevant case studies, data, committee recommendations?
4. Constitutional Grounding — Articles, Amendments, Schedules cited correctly?
5. Presentation — Bullet points, diagrams, flow? Underline key terms?
6. Conclusion — Forward-looking? Balanced? Reform-oriented?

Return a JSON object with:
  dimension_scores — dict of dimension → score
  overall_score    — float 0.0 to 1.0
  strengths        — list of strings
  weaknesses       — list of strings

Return ONLY valid JSON.
"""


class UPSCQualityMetric(Metric):
    """UPSC-specific quality rubric."""

    def name(self) -> str:
        return "upsc_quality"

    def evaluate(
        self,
        question: str,
        answer: str,
        context: list[str] = None,
        reference: str = None,
    ) -> MetricResult:
        try:
            from core.llm_gateway import LLMGateway
            gateway = LLMGateway()
            import asyncio
            response = asyncio.run(
                gateway.complete(
                    messages=[
                        {"role": "system", "content": _UPSC_QUALITY_SYSTEM},
                        {"role": "user", "content": f"Question: {question}\n\nAnswer:\n{answer}"},
                    ],
                    temperature=0.1,
                    max_tokens=1024,
                )
            )
            result = json.loads(response.content)
            overall = result.get("overall_score", 0.5)
            dimensions = result.get("dimension_scores", {})
            details = f"Overall: {overall:.2f}. Dimensions: {json.dumps(dimensions, indent=2)}"
            return MetricResult(name=self.name(), score=float(overall), details=details)
        except Exception as exc:
            logger.warning("[UPSC_QUALITY] Evaluation failed: %s", exc)
            return MetricResult(name=self.name(), score=0.5, details=f"Check skipped: {exc}")
