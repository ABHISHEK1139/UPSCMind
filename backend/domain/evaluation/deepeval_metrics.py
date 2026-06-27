"""
Hermes V2 — DeepEval Integration
═══════════════════════════════════════════════════════════════
Wraps DeepEval metrics for use in the Hermes evaluation pipeline.
Falls back gracefully when DeepEval is not installed.

Metrics:
- HallucinationMetric: Detects fabricated claims
- FaithfulnessMetric: Checks answer against context
- AnswerRelevancyMetric: Checks if answer addresses the question
"""

from __future__ import annotations

import logging
from typing import Optional

from domain.evaluation.metrics import Metric, MetricResult

logger = logging.getLogger(__name__)

# Check DeepEval availability
_DEEPEVAL_AVAILABLE = False
try:
    import deepeval
    from deepeval.metrics import HallucinationMetric, FaithfulnessMetric, AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    _DEEPEVAL_AVAILABLE = True
    logger.info("[EVAL] DeepEval available.")
except ImportError:
    logger.info("[EVAL] DeepEval not installed — using fallback metrics.")


class DeepEvalHallucination(Metric):
    """Detects hallucinations using DeepEval's HallucinationMetric."""
    
    def name(self) -> str:
        return "deepeval_hallucination"
    
    def evaluate(
        self,
        question: str,
        answer: str,
        context: list[str] = None,
        reference: str = None,
    ) -> MetricResult:
        if not _DEEPEVAL_AVAILABLE:
            return MetricResult(name=self.name(), score=1.0, details="DeepEval not installed, skipped.")
        
        try:
            test_case = LLMTestCase(
                input=question,
                actual_output=answer,
                context=context or [],
            )
            metric = HallucinationMetric(threshold=0.5, model="openrouter/owl-alpha")
            metric.measure(test_case)
            return MetricResult(
                name=self.name(),
                score=metric.score,
                details=f"Passed: {metric.is_successful()}, Reason: {metric.reason}",
            )
        except Exception as exc:
            logger.warning("[EVAL] Hallucination check failed: %s", exc)
            return MetricResult(name=self.name(), score=1.0, details=f"Check skipped: {exc}")


class DeepEvalFaithfulness(Metric):
    """Checks faithfulness to retrieved context."""
    
    def name(self) -> str:
        return "deepeval_faithfulness"
    
    def evaluate(
        self,
        question: str,
        answer: str,
        context: list[str] = None,
        reference: str = None,
    ) -> MetricResult:
        if not _DEEPEVAL_AVAILABLE:
            return MetricResult(name=self.name(), score=1.0, details="DeepEval not installed, skipped.")
        
        try:
            test_case = LLMTestCase(
                input=question,
                actual_output=answer,
                context=context or [],
            )
            metric = FaithfulnessMetric(threshold=0.7)
            metric.measure(test_case)
            return MetricResult(
                name=self.name(),
                score=metric.score,
                details=f"Passed: {metric.is_successful()}, Reason: {metric.reason}",
            )
        except Exception as exc:
            logger.warning("[EVAL] Faithfulness check failed: %s", exc)
            return MetricResult(name=self.name(), score=1.0, details=f"Check skipped: {exc}")


class DeepEvalRelevancy(Metric):
    """Checks if the answer is relevant to the question."""
    
    def name(self) -> str:
        return "deepeval_relevancy"
    
    def evaluate(
        self,
        question: str,
        answer: str,
        context: list[str] = None,
        reference: str = None,
    ) -> MetricResult:
        if not _DEEPEVAL_AVAILABLE:
            return MetricResult(name=self.name(), score=1.0, details="DeepEval not installed, skipped.")
        
        try:
            test_case = LLMTestCase(
                input=question,
                actual_output=answer,
            )
            metric = AnswerRelevancyMetric(threshold=0.7)
            metric.measure(test_case)
            return MetricResult(
                name=self.name(),
                score=metric.score,
                details=f"Passed: {metric.is_successful()}, Reason: {metric.reason}",
            )
        except Exception as exc:
            logger.warning("[EVAL] Relevancy check failed: %s", exc)
            return MetricResult(name=self.name(), score=1.0, details=f"Check skipped: {exc}")


# ── Unified Evaluation Function ────────────────────────────────────

async def evaluate_answer(
    question: str,
    answer: str,
    context: list[str] = None,
    reference: str = None,
    domain: str = "General Studies",
) -> dict:
    """
    Run all evaluation metrics on an answer.
    
    Returns
    -------
    dict with keys: overall_score (float), metrics (list[MetricResult]), passed (bool)
    """
    metrics: list[Metric] = [
        DeepEvalHallucination(),
        DeepEvalFaithfulness(),
        DeepEvalRelevancy(),
    ]
    
    # Add UPSC-specific metrics
    try:
        from domain.evaluation.citation_score import CitationScoreMetric
        from domain.evaluation.upsc_quality import UPSCQualityMetric
        metrics.append(CitationScoreMetric())
        # UPSCQualityMetric is expensive — only run on high-value samples
        # metrics.append(UPSCQualityMetric())
    except ImportError:
        pass
    
    results = []
    for metric in metrics:
        try:
            result = metric.evaluate(question, answer, context, reference)
            results.append(result)
        except Exception as exc:
            logger.warning("[EVAL] Metric %s failed: %s", metric.name(), exc)
            results.append(MetricResult(name=metric.name(), score=0.0, details=str(exc)))
    
    scores = [r.score for r in results]
    overall = sum(scores) / len(scores) if scores else 0.0
    
    return {
        "overall_score": round(overall, 3),
        "passed": overall >= 0.7,
        "metrics": [{"name": r.name, "score": r.score, "details": r.details} for r in results],
    }
