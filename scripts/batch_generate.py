"""
Hermes V2 — Batch Training Data Generator
═══════════════════════════════════════════════════════════════
Processes UPSC questions from the dataset and generates training data.
Runs inside the Docker container.

Usage:
    python -m batch_generate --source mains --limit 100 --delay 2
    python -m batch_generate --source prelims --limit 50 --delay 3
    python -m batch_generate --source all --limit 200 --delay 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DELAY_SECONDS = 2  # Delay between questions to avoid rate limiting


def load_questions(source: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Load questions from dataset files."""
    questions = []
    dataset_dir = Path("dataset")

    files = []
    if source in ("all", "mains"):
        files.append(dataset_dir / "mains_gs_all.jsonl")
    if source in ("all", "prelims"):
        files.append(dataset_dir / "prelims_gs_all.jsonl")
    if source in ("all", "csat"):
        files.append(dataset_dir / "csat_dataset_all.jsonl")

    for filepath in files:
        if not filepath.exists():
            logger.warning("[BATCH] File not found: %s", filepath)
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    questions.append({
                        "question": record.get("question", ""),
                        "answer": record.get("answer", record.get("model_answer", "")),
                        "year": record.get("year"),
                        "paper": record.get("paper", "GS"),
                        "subject": record.get("subject", record.get("domain", "general")),
                        "source_file": filepath.name,
                        "metadata": {
                            k: v for k, v in record.items()
                            if k not in ("question", "answer", "model_answer")
                        },
                    })
                except json.JSONDecodeError:
                    continue

    logger.info("[BATCH] Loaded %d questions from %d file(s)", len(questions), len(files))
    return questions


async def generate_answer(question_text: str, session_id: str) -> Optional[Dict[str, Any]]:
    """Generate an answer through the LangGraph orchestrator."""
    try:
        from domain.answer_generation.orchestrator import build_answer_graph

        graph = build_answer_graph()

        state = {
            "session_id": session_id,
            "question": question_text,
            "domain": None, "question_type": None, "detected_entities": [],
            "constitutional_weight": None, "sub_topics": [], "topic_confidence": None,
            "retrieval_strategy": None, "retrieved_chunks": [],
            "retrieval_latency_ms": None, "retrieval_notes": None,
            "reasoning_plan": None, "framework": None, "examiner_persona": None,
            "trap": None, "differentiator": None, "planning_notes": None,
            "draft_answer": None, "draft_model": None, "draft_tokens": None, "draft_latency_ms": None,
            "critique": None, "critique_score": None, "critique_model": None, "critique_latency_ms": None,
            "fact_check_passed": False, "fact_check_issues": None,
            "constitutional_check_passed": True, "constitutional_check_notes": None,
            "guardrails_passed": True, "guardrails_notes": None,
            "revision_iterations": 0, "improved_answer": None, "revision_notes": None,
            "verification_passed": False, "verification_layers": {},
            "final_answer": None, "total_cost_usd": 0.0, "total_latency_ms": 0.0,
            "total_tokens": 0, "models_used": [],
            "cot_trace": [], "quality_score": None, "training_eligible": False,
            "question_metadata": {},
            "error": None, "feedback": {},
        }

        result = await graph.ainvoke(state)
        return result

    except Exception as exc:
        logger.error("[BATCH] Generation failed: %s", exc)
        return None


def run_batch(
    source: str = "mains",
    limit: int = 100,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
) -> Dict[str, Any]:
    """Run batch data generation."""
    t0 = time.monotonic()

    questions = load_questions(source, limit)
    if not questions:
        return {"status": "error", "reason": "no_questions_loaded"}

    results = {
        "total": len(questions),
        "successful": 0,
        "failed": 0,
        "quality_gated": 0,
        "by_domain": {},
        "by_score_range": {"0.0-0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0},
        "avg_score": 0.0,
        "avg_latency_ms": 0.0,
        "total_tokens": 0,
    }

    scores = []
    latencies = []

    for i, q in enumerate(questions):
        session_id = f"batch-{uuid.uuid4().hex[:8]}"
        logger.info("[BATCH] Processing %d/%d: %.60s...", i + 1, len(questions), q["question"])

        result = asyncio.run(generate_answer(q["question"], session_id))

        if result is None:
            results["failed"] += 1
            continue

        results["successful"] += 1

        score = result.get("critique_score", 0.0) or 0.0
        latency = result.get("total_latency_ms", 0.0) or 0.0
        tokens = result.get("total_tokens", 0) or 0
        domain = result.get("domain", "unknown")
        training_eligible = result.get("training_eligible", False)

        scores.append(score)
        latencies.append(latency)
        results["total_tokens"] += tokens

        if training_eligible:
            results["quality_gated"] += 1

        # Domain tracking
        results["by_domain"][domain] = results["by_domain"].get(domain, 0) + 1

        # Score range tracking
        if score < 0.5:
            results["by_score_range"]["0.0-0.5"] += 1
        elif score < 0.7:
            results["by_score_range"]["0.5-0.7"] += 1
        elif score < 0.9:
            results["by_score_range"]["0.7-0.9"] += 1
        else:
            results["by_score_range"]["0.9-1.0"] += 1

        # Delay between questions
        if i < len(questions) - 1:
            time.sleep(delay_seconds)

    # Compute averages
    if scores:
        results["avg_score"] = round(sum(scores) / len(scores), 3)
    if latencies:
        results["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1)

    elapsed = time.monotonic() - t0
    results["elapsed_seconds"] = round(elapsed, 1)
    results["questions_per_minute"] = round(len(questions) / (elapsed / 60), 1)

    logger.info("═" * 60)
    logger.info("  BATCH GENERATION COMPLETE")
    logger.info("═" * 60)
    logger.info("  Total questions: %d", results["total"])
    logger.info("  Successful: %d", results["successful"])
    logger.info("  Failed: %d", results["failed"])
    logger.info("  Quality-gated: %d", results["quality_gated"])
    logger.info("  Avg score: %.3f", results["avg_score"])
    logger.info("  Avg latency: %.0fms", results["avg_latency_ms"])
    logger.info("  Total tokens: %d", results["total_tokens"])
    logger.info("  Elapsed: %.1fs", results["elapsed_seconds"])
    logger.info("  Speed: %.1f questions/min", results["questions_per_minute"])
    logger.info("  By domain: %s", results["by_domain"])
    logger.info("  By score range: %s", results["by_score_range"])
    logger.info("═" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(description="Batch training data generator")
    parser.add_argument("--source", default="mains", choices=["all", "mains", "prelims", "csat"])
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    args = parser.parse_args()

    results = run_batch(source=args.source, limit=args.limit, delay_seconds=args.delay)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
