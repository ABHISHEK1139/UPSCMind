"""
Hermes V2 — Benchmark Runner
═══════════════════════════════════════════════════════════════
Runs N questions through the orchestrator, evaluates each
answer, and produces a comprehensive benchmark report.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Run benchmark questions and collect metrics."""

    def __init__(self) -> None:
        self._results: List[Dict[str, Any]] = []

    def run(
        self,
        n_questions: int = 500,
        dataset_path: str = "dataset/mains_gs_all.jsonl",
    ) -> Dict[str, Any]:
        """
        Run the benchmark.

        Parameters
        ----------
        n_questions : int
            Number of questions to evaluate.
        dataset_path : str
            Path to the JSONL dataset file.

        Returns
        -------
        dict with aggregate metrics and per-question results.
        """
        t0 = time.monotonic()
        questions = self._load_questions(dataset_path, n_questions)
        logger.info("[BENCHMARK] Starting: %d questions from %s", len(questions), dataset_path)

        results = []
        for i, question in enumerate(questions):
            try:
                result = self._evaluate_question(question)
                results.append(result)
                if (i + 1) % 10 == 0:
                    logger.info("[BENCHMARK] Progress: %d/%d", i + 1, len(questions))
            except Exception as exc:
                logger.error("[BENCHMARK] Question %d failed: %s", i, exc)
                results.append({"question": question[:100], "error": str(exc)})

        elapsed = time.monotonic() - t0
        report = self._aggregate(results, elapsed)

        # Save report
        report_path = Path("dataset/training_data/benchmark_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(
            "[BENCHMARK] Complete: %d questions in %.1fs | avg_score=%.3f",
            len(questions), elapsed, report.get("avg_score", 0.0),
        )
        return report

    def _evaluate_question(self, question: str) -> Dict[str, Any]:
        """Run a single question through the pipeline and evaluate."""
        from domain.answer_generation.orchestrator import build_answer_graph
        import asyncio

        graph = build_answer_graph()
        state = asyncio.run(
            graph.ainvoke({
                "session_id": "benchmark",
                "question": question,
                "revision_iterations": 0,
            })
        )

        return {
            "question": question[:200],
            "domain": state.get("domain", "unknown"),
            "critique_score": state.get("critique_score", 0.0),
            "fact_check_passed": state.get("fact_check_passed", False),
            "guardrails_passed": state.get("guardrails_passed", False),
            "revision_iterations": state.get("revision_iterations", 0),
            "training_eligible": state.get("training_eligible", False),
            "total_latency_ms": state.get("total_latency_ms", 0.0),
            "total_tokens": state.get("total_tokens", 0),
        }

    def _aggregate(self, results: List[Dict], elapsed: float) -> Dict[str, Any]:
        """Compute aggregate statistics."""
        scores = [r.get("critique_score", 0.0) for r in results if "error" not in r]
        eligible = sum(1 for r in results if r.get("training_eligible", False))
        fact_passed = sum(1 for r in results if r.get("fact_check_passed", False))

        by_domain: Dict[str, list] = {}
        for r in results:
            if "error" not in r:
                d = r.get("domain", "unknown")
                by_domain.setdefault(d, []).append(r.get("critique_score", 0.0))

        return {
            "total_questions": len(results),
            "successful": len(scores),
            "failed": len(results) - len(scores),
            "avg_score": sum(scores) / len(scores) if scores else 0.0,
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0,
            "median_score": sorted(scores)[len(scores) // 2] if scores else 0.0,
            "training_eligible_count": eligible,
            "training_eligible_pct": eligible / len(results) * 100 if results else 0,
            "fact_check_pass_rate": fact_passed / len(results) * 100 if results else 0,
            "avg_latency_ms": sum(r.get("total_latency_ms", 0) for r in results) / len(results) if results else 0,
            "total_time_s": round(elapsed, 1),
            "by_domain": {d: sum(s) / len(s) for d, s in by_domain.items()},
        }

    @staticmethod
    def _load_questions(path: str, n: int) -> list[str]:
        """Load questions from a JSONL file."""
        questions = []
        p = Path(path)
        if not p.exists():
            logger.warning("[BENCHMARK] Dataset not found: %s", path)
            return questions
        with open(p, "r", encoding="utf-8") as f:
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
