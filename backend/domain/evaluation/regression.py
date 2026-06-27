"""
Hermes V2 — Regression Testing
═══════════════════════════════════════════════════════════════
Compares V1 vs V2 performance on the same set of questions
to ensure V2 is strictly better.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from domain.evaluation.metrics import MetricResult

logger = logging.getLogger(__name__)


class RegressionTester:
    """Compare V1 and V2 answer quality."""

    def __init__(self, v1_answers_path: str = "generated_answers") -> None:
        self._v1_path = Path(v1_answers_path)

    def compare(
        self,
        questions: list[str] = None,
        n_questions: int = 100,
    ) -> Dict[str, Any]:
        """
        Run V1 vs V2 comparison.

        Returns
        -------
        dict with keys: v1_avg, v2_avg, improvement, details
        """
        results = {
            "v1_avg_score": 0.0,
            "v2_avg_score": 0.0,
            "improvement_pct": 0.0,
            "questions_compared": 0,
            "v2_wins": 0,
            "v1_wins": 0,
            "ties": 0,
            "details": [],
        }

        try:
            from domain.evaluation.upsc_quality import UPSCQualityMetric
            metric = UPSCQualityMetric()

            # Load questions from dataset
            if questions is None:
                questions = self._load_questions(n_questions)

            for question in questions[:n_questions]:
                # Generate V2 answer
                try:
                    from domain.answer_generation.orchestrator import build_answer_graph
                    graph = build_answer_graph()
                    import asyncio
                    state = asyncio.run(
                        graph.ainvoke({
                            "session_id": "regression_test",
                            "question": question,
                            "revision_iterations": 0,
                        })
                    )
                    v2_answer = state.get("draft_answer", "")
                    v2_score = state.get("critique_score", 0.0) or 0.0
                except Exception as exc:
                    logger.warning("[REGRESSION] V2 generation failed: %s", exc)
                    v2_answer = ""
                    v2_score = 0.0

                # Load V1 answer (if available)
                v1_answer = self._load_v1_answer(question)
                v1_eval = metric.evaluate(question, v1_answer) if v1_answer else None
                v1_score = v1_eval.score if v1_eval else 0.0

                if v2_score > v1_score:
                    results["v2_wins"] += 1
                elif v1_score > v2_score:
                    results["v1_wins"] += 1
                else:
                    results["ties"] += 1

                results["details"].append({
                    "question": question[:100],
                    "v1_score": v1_score,
                    "v2_score": v2_score,
                })

            n = len(results["details"])
            if n > 0:
                results["v1_avg_score"] = sum(d["v1_score"] for d in results["details"]) / n
                results["v2_avg_score"] = sum(d["v2_score"] for d in results["details"]) / n
                results["questions_compared"] = n
                if results["v1_avg_score"] > 0:
                    results["improvement_pct"] = (
                        (results["v2_avg_score"] - results["v1_avg_score"])
                        / results["v1_avg_score"]
                        * 100
                    )

        except Exception as exc:
            logger.error("[REGRESSION] Comparison failed: %s", exc)
            results["error"] = str(exc)

        return results

    def _load_questions(self, n: int) -> list[str]:
        """Load questions from the dataset."""
        questions = []
        dataset_path = Path("dataset/mains_gs_all.jsonl")
        if dataset_path.exists():
            with open(dataset_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= n:
                        break
                    try:
                        record = json.loads(line)
                        q = record.get("question", "")
                        if q:
                            questions.append(q)
                    except json.JSONDecodeError:
                        continue
        return questions

    def _load_v1_answer(self, question: str) -> Optional[str]:
        """Try to find a V1 answer for the given question."""
        if not self._v1_path.exists():
            return None
        for f in self._v1_path.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if item.get("question", "") == question:
                            return item.get("answer", "")
            except (json.JSONDecodeError, KeyError):
                continue
        return None
