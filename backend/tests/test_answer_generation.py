"""
Answer Generation Test — Full V3 Pipeline
═══════════════════════════════════════════════════════════════
Tests the complete answer generation pipeline with real LLM calls.
Tracks every step, latency, and output quality.
"""

import asyncio
import json
import time
import sys

def log(msg):
    print(msg, flush=True)

async def run_answer_test():
    """Run the full V3 pipeline with real LLM calls."""
    from domain.answer_generation.orchestrator_v3 import build_answer_graph_v3

    results = {
        "questions": [],
        "total_time": 0,
        "total_cost_estimate": 0,
        "errors": [],
    }

    # Test questions covering all domains
    QUESTIONS = [
        {
            "q": "Discuss the significance of the 73rd and 74th Constitutional Amendments for local governance in India.",
            "domain": "Polity",
            "paper": "GS2",
            "year": 2020,
            "type": "analytical",
        },
        {
            "q": "What is fiscal deficit? Discuss its implications for the Indian economy.",
            "domain": "Economy",
            "paper": "GS3",
            "year": 2022,
            "type": "factual",
        },
        {
            "q": "Discuss the salient features of the Harappan architecture with suitable examples.",
            "domain": "History",
            "paper": "GS1",
            "year": 2018,
            "type": "factual",
        },
        {
            "q": "Discuss the role of monsoons in Indian agriculture and the economy.",
            "domain": "Geography",
            "paper": "GS1",
            "year": 2021,
            "type": "analytical",
        },
        {
            "q": "What is the difference between ethical governance and good governance? Discuss with examples.",
            "domain": "Ethics",
            "paper": "GS4",
            "year": 2022,
            "type": "analytical",
        },
    ]

    log("\n" + "=" * 70)
    log("  HERMES V2 — FULL ANSWER GENERATION TEST")
    log("=" * 70)
    log(f"  Questions: {len(QUESTIONS)}")
    log(f"  Model: openrouter/owl-alpha")
    log("=" * 70)

    total_start = time.monotonic()

    for i, item in enumerate(QUESTIONS):
        q_start = time.monotonic()
        log(f"\n{'─' * 70}")
        log(f"  Q{i+1}: {item['q'][:80]}...")
        log(f"  Expected: {item['domain']} | {item['paper']} | {item['year']}")
        log(f"{'─' * 70}")

        try:
            graph = build_answer_graph_v3()
            state = {
                "session_id": f"test-{i+1:03d}",
                "question": item["q"],
                "question_metadata": {
                    "expected_domain": item["domain"],
                    "paper": item["paper"],
                    "year": item["year"],
                    "type": item["type"],
                },
                "cot_trace": [],
                "revision_iterations": 0,
                "reflection_round": 0,
            }

            # Run the full pipeline
            result = await graph.ainvoke(state)
            q_elapsed = time.monotonic() - q_start

            # Extract results
            domain = result.get("domain", "?")
            score = result.get("overall_score", 0)
            confidence = result.get("confidence", 0)
            answer = result.get("draft_answer", "")
            answer_len = len(answer.split())
            cot_steps = len(result.get("cot_trace", []))
            verification = result.get("verification_passed", "?")
            revisions = result.get("revision_iterations", 0)

            # Log results
            log(f"\n  ✅ Q{i+1} COMPLETE in {q_elapsed:.0f}s")
            log(f"  ├─ Predicted Domain: {domain}")
            log(f"  ├─ Overall Score: {score:.2f}")
            log(f"  ├─ Confidence: {confidence:.2f}")
            log(f"  ├─ Answer Length: {answer_len} words")
            log(f"  ├─ CoT Steps: {cot_steps}")
            log(f"  ├─ Verification: {verification}")
            log(f"  ├─ Revisions: {revisions}")
            log(f"  └─ Pipeline Latency: {q_elapsed:.0f}s")

            # Log CoT trace
            cot_trace = result.get("cot_trace", [])
            if cot_trace:
                log(f"\n  Chain-of-Thought Trace ({len(cot_trace)} steps):")
                for step in cot_trace:
                    log(f"    Step {step['step_number']}: {step['node']} — {step['thought'][:80]}...")

            # Log review scores
            review_scores = result.get("review_scores", {})
            if review_scores:
                log(f"\n  Review Scores:")
                for dim, val in review_scores.items():
                    bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                    log(f"    {dim:25s} {bar} {val:.1f}")

            # Store result
            results["questions"].append({
                "id": i + 1,
                "question": item["q"],
                "expected_domain": item["domain"],
                "predicted_domain": domain,
                "score": score,
                "confidence": confidence,
                "answer_length": answer_len,
                "cot_steps": cot_steps,
                "verification": verification,
                "revisions": revisions,
                "latency_s": round(q_elapsed, 1),
                "answer_preview": answer[:200] + "..." if len(answer) > 200 else answer,
                "error": None,
            })

        except Exception as exc:
            q_elapsed = time.monotonic() - q_start
            log(f"\n  ❌ Q{i+1} FAILED after {q_elapsed:.0f}s")
            log(f"  Error: {type(exc).__name__}: {str(exc)[:200]}")
            results["questions"].append({
                "id": i + 1,
                "question": item["q"],
                "error": str(exc)[:200],
                "latency_s": round(q_elapsed, 1),
            })
            results["errors"].append(f"Q{i+1}: {exc}")

    # ── Summary ──────────────────────────────────────────────────
    total_elapsed = time.monotonic() - total_start
    results["total_time"] = round(total_elapsed, 1)

    log(f"\n{'=' * 70}")
    log(f"  RESULTS SUMMARY")
    log(f"{'=' * 70}")

    successful = [q for q in results["questions"] if q.get("error") is None]
    failed = [q for q in results["questions"] if q.get("error")]

    log(f"\n  Total Questions: {len(results['questions'])}")
    log(f"  Successful: {len(successful)}")
    log(f"  Failed: {len(failed)}")
    log(f"  Total Time: {total_elapsed:.0f}s")

    if successful:
        avg_score = sum(q["score"] for q in successful) / len(successful)
        avg_confidence = sum(q["confidence"] for q in successful) / len(successful)
        avg_length = sum(q["answer_length"] for q in successful) / len(successful)
        avg_latency = sum(q["latency_s"] for q in successful) / len(successful)
        avg_cot = sum(q["cot_steps"] for q in successful) / len(successful)

        log(f"\n  Average Score: {avg_score:.2f}")
        log(f"  Average Confidence: {avg_confidence:.2f}")
        log(f"  Average Answer Length: {avg_length:.0f} words")
        log(f"  Average Latency: {avg_latency:.0f}s")
        log(f"  Average CoT Steps: {avg_cot:.0f}")

        # Domain accuracy
        domain_correct = sum(
            1 for q in successful
            if q["predicted_domain"].lower() == q["expected_domain"].lower()
        )
        log(f"\n  Domain Accuracy: {domain_correct}/{len(successful)} ({100*domain_correct/len(successful):.0f}%)")

        # Score distribution
        log(f"\n  Score Distribution:")
        for threshold in [0.8, 0.7, 0.6, 0.5]:
            count = sum(1 for q in successful if q["score"] >= threshold)
            log(f"    >= {threshold:.1f}: {count}/{len(successful)} ({100*count/len(successful):.0f}%)")

    if failed:
        log(f"\n  Failed Questions:")
        for q in failed:
            log(f"    Q{q['id']}: {q['error'][:100]}")

    # Save results to JSON
    output_path = "/app/dataset/answer_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    log(f"\n  Results saved to: {output_path}")
    log(f"{'=' * 70}\n")

    return results

if __name__ == "__main__":
    results = asyncio.run(run_answer_test())
    sys.exit(0 if len(results["errors"]) == 0 else 1)
