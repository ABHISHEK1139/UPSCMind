"""
Hermes V2 — Continuous Evaluation Pipeline
═══════════════════════════════════════════════════════════════
Automatically runs quality checks after data ingestion events.
Monitors for quality regressions and alerts when thresholds are breached.

Triggered by:
  - Scraper runs (after new data is ingested)
  - Manual trigger via API
  - Scheduled weekly benchmark

Usage:
    from domain.evaluation.continuous import ContinuousEvaluator
    evaluator = ContinuousEvaluator()
    report = await evaluator.run_post_ingestion_check(source="pib", new_docs=50)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("data/evaluation_reports")
SAMPLE_SIZE = 20  # Questions to sample for quick evaluation
QUALITY_THRESHOLD = 0.85  # Minimum acceptable average score
LATENCY_THRESHOLD_MS = 15000  # Maximum acceptable latency


class ContinuousEvaluator:
    """
    Runs automatic quality checks after data ingestion or system changes.
    
    Produces a report with:
    - Average quality score
    - Average latency
    - Comparison with baseline
    - Regression alerts
    """
    
    def __init__(
        self,
        sample_size: int = SAMPLE_SIZE,
        quality_threshold: float = QUALITY_THRESHOLD,
        latency_threshold_ms: float = LATENCY_THRESHOLD_MS,
    ) -> None:
        self._sample_size = sample_size
        self._quality_threshold = quality_threshold
        self._latency_threshold_ms = latency_threshold_ms
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    async def run_post_ingestion_check(
        self,
        source: str,
        new_docs: int = 0,
    ) -> Dict[str, Any]:
        """
        Run evaluation after a scraper ingests new data.
        
        Parameters
        ----------
        source : str
            The data source that was updated (e.g., "pib", "prs")
        new_docs : int
            Number of new documents ingested
            
        Returns
        -------
        dict with evaluation results and regression alerts
        """
        t0 = time.monotonic()
        logger.info("[CONT_EVAL] Running post-ingestion check for %s (%d new docs)...", source, new_docs)
        
        # 1. Sample questions
        questions = self._sample_questions(source)
        if not questions:
            logger.warning("[CONT_EVAL] No questions available for sampling.")
            return {"status": "skipped", "reason": "no_questions_available"}
        
        # 2. Run through pipeline
        results = []
        for question in questions:
            try:
                result = await self._evaluate_question(question)
                results.append(result)
            except Exception as exc:
                logger.warning("[CONT_EVAL] Question failed: %s", exc)
                results.append({"question": question[:100], "error": str(exc)})
        
        # 3. Compute metrics
        successful = [r for r in results if "error" not in r]
        scores = [r.get("critique_score", 0.0) for r in successful]
        latencies = [r.get("latency_ms", 0.0) for r in successful]
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        # 4. Compare with baseline
        baseline = self._load_baseline(source)
        regression = False
        alerts = []
        
        if baseline:
            if avg_score < baseline.get("avg_score", 0.0) - 0.05:
                regression = True
                alerts.append(
                    f"Quality regression: {avg_score:.2f} vs baseline {baseline['avg_score']:.2f}"
                )
            if avg_latency > baseline.get("avg_latency_ms", 0) * 1.5:
                alerts.append(
                    f"Latency regression: {avg_latency:.0f}ms vs baseline {baseline['avg_latency_ms']:.0f}ms"
                )
        
        if avg_score < self._quality_threshold:
            alerts.append(f"Quality below threshold: {avg_score:.2f} < {self._quality_threshold}")
        
        if avg_latency > self._latency_threshold_ms:
            alerts.append(f"Latency above threshold: {avg_latency:.0f}ms > {self._latency_threshold_ms}ms")
        
        # 5. Build report
        elapsed = time.monotonic() - t0
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "new_docs": new_docs,
            "questions_evaluated": len(results),
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "avg_score": round(avg_score, 3),
            "avg_latency_ms": round(avg_latency, 1),
            "baseline_comparison": {
                "baseline_score": baseline.get("avg_score") if baseline else None,
                "baseline_latency_ms": baseline.get("avg_latency_ms") if baseline else None,
                "score_delta": round(avg_score - baseline.get("avg_score", avg_score), 3) if baseline else None,
            },
            "regression_detected": regression,
            "alerts": alerts,
            "evaluation_time_s": round(elapsed, 1),
        }
        
        # 6. Save report
        self._save_report(report, source)
        
        # 7. Update baseline (rolling average)
        self._update_baseline(source, avg_score, avg_latency)
        
        if regression:
            logger.warning("[CONT_EVAL] REGRESSION DETECTED: %s", alerts)
        else:
            logger.info("[CONT_EVAL] Check passed: score=%.2f latency=%.0fms", avg_score, avg_latency)
        
        return report
    
    def _sample_questions(self, source: str, n: Optional[int] = None) -> List[str]:
        """Sample questions from the dataset for evaluation."""
        n = n or self._sample_size
        
        # Load from the main dataset
        questions = []
        dataset_path = Path("dataset/mains_gs_all.jsonl")
        if dataset_path.exists():
            import random
            with open(dataset_path, "r", encoding="utf-8") as f:
                all_lines = [line for line in f if line.strip()]
            
            sample_lines = random.sample(all_lines, min(n, len(all_lines)))
            for line in sample_lines:
                try:
                    record = json.loads(line)
                    q = record.get("question", "")
                    if q:
                        questions.append(q)
                except json.JSONDecodeError:
                    continue
        
        return questions[:n]
    
    async def _evaluate_question(self, question: str) -> Dict[str, Any]:
        """Run a single question through the pipeline and collect metrics."""
        from domain.answer_generation.orchestrator import build_answer_graph
        
        t0 = time.monotonic()
        graph = build_answer_graph()
        
        state = {
            "session_id": "continuous_eval",
            "question": question,
            "domain": None, "question_type": None, "detected_entities": [],
            "constitutional_weight": None, "sub_topics": [],
            "retrieval_strategy": None, "retrieved_chunks": [],
            "reasoning_plan": None, "framework": None,
            "draft_answer": None, "critique": None, "critique_score": None,
            "fact_check_passed": False, "guardrails_passed": True,
            "revision_iterations": 0, "cot_trace": [],
            "training_eligible": False, "error": None,
        }
        
        result = await graph.ainvoke(state)
        latency_ms = (time.monotonic() - t0) * 1000
        
        return {
            "question": question[:200],
            "domain": result.get("domain"),
            "critique_score": result.get("critique_score", 0.0),
            "fact_check_passed": result.get("fact_check_passed", False),
            "revision_iterations": result.get("revision_iterations", 0),
            "latency_ms": latency_ms,
        }
    
    def _load_baseline(self, source: str) -> Optional[Dict[str, Any]]:
        """Load the baseline metrics for a source."""
        baseline_path = REPORTS_DIR / f"baseline_{source}.json"
        if baseline_path.exists():
            return json.loads(baseline_path.read_text())
        return None
    
    def _update_baseline(self, source: str, avg_score: float, avg_latency: float) -> None:
        """Update the baseline with a rolling average."""
        baseline = self._load_baseline(source)
        
        if baseline:
            # Rolling average (70% old, 30% new)
            old_weight = 0.7
            new_weight = 0.3
            updated = {
                "avg_score": round(baseline.get("avg_score", avg_score) * old_weight + avg_score * new_weight, 3),
                "avg_latency_ms": round(baseline.get("avg_latency_ms", avg_latency) * old_weight + avg_latency * new_weight, 1),
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "num_evaluations": baseline.get("num_evaluations", 0) + 1,
            }
        else:
            updated = {
                "avg_score": round(avg_score, 3),
                "avg_latency_ms": round(avg_latency, 1),
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "num_evaluations": 1,
            }
        
        baseline_path = REPORTS_DIR / f"baseline_{source}.json"
        baseline_path.write_text(json.dumps(updated, indent=2))
    
    def _save_report(self, report: Dict[str, Any], source: str) -> None:
        """Save an evaluation report."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"report_{source}_{timestamp}.json"
        report_path.write_text(json.dumps(report, indent=2, default=str))
    
    def get_latest_report(self, source: str) -> Optional[Dict[str, Any]]:
        """Get the latest evaluation report for a source."""
        reports = sorted(REPORTS_DIR.glob(f"report_{source}_*.json"))
        if reports:
            return json.loads(reports[-1].read_text())
        return None
    
    def get_all_reports(self, source: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent evaluation reports for a source."""
        reports = sorted(REPORTS_DIR.glob(f"report_{source}_*.json"), reverse=True)
        return [json.loads(r.read_text()) for r in reports[:limit]]
