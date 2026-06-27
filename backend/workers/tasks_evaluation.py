"""
Hermes V2 — Evaluation Tasks
═══════════════════════════════════════════════════════════════
Background tasks for running benchmarks and regression tests.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=3600)
def run_evaluation_benchmark(
    self, n_questions: int = 500, dataset_path: str = "dataset/mains_gs_all.jsonl"
) -> Dict[str, Any]:
    """Run the full evaluation benchmark suite."""
    try:
        logger.info("[EVAL] Starting benchmark: %d questions...", n_questions)
        from domain.evaluation.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        results = runner.run(n_questions=n_questions, dataset_path=dataset_path)
        logger.info("[EVAL] Benchmark complete: %s", results)
        return results
    except Exception as exc:
        logger.error("[EVAL] Benchmark failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800)
def run_v1_v2_regression(self) -> Dict[str, Any]:
    """Run V1 vs V2 regression comparison."""
    try:
        logger.info("[EVAL] Starting V1 vs V2 regression...")
        from domain.evaluation.regression import RegressionTester

        tester = RegressionTester()
        results = tester.compare()
        logger.info("[EVAL] Regression complete: %s", results)
        return results
    except Exception as exc:
        logger.error("[EVAL] Regression failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=600)
def evaluate_single_question(
    self, question: str, reference_answer: str = ""
) -> Dict[str, Any]:
    """Evaluate a single question's answer quality."""
    try:
        import asyncio
        from domain.evaluation.deepeval_metrics import evaluate_answer

        # Run async evaluate_answer in sync context
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                evaluate_answer(question, answer="", context=[], reference=reference_answer)
            )
        finally:
            loop.close()
        return result
    except Exception as exc:
        logger.error("[EVAL] Single question eval failed: %s", exc)
        raise self.retry(exc=exc, countdown=30)
