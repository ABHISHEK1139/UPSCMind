"""
Hermes V2 — Full Answer Generation Tracking & Testing
═══════════════════════════════════════════════════════════════
Generates answers for real UPSC questions, tracks every pipeline stage,
and verifies the complete flow from question to final answer.

Tests:
1. Question → Intent Classification (domain, type, difficulty)
2. Intent → Retrieval (evidence chunks)
3. Retrieval → Blueprint (UPSC structure)
4. Blueprint → Planning (framework, dimensions)
5. Planning → Drafting (full answer)
6. Drafting → Review (quality scores)
7. Review → Verification (fact-check, hallucination)
8. Verification → Confidence (final score)
9. Full pipeline → Final answer
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ── Test Questions ─────────────────────────────────────────────────────────

TEST_QUESTIONS = [
    {
        "id": "upsc-001",
        "question": "Discuss the significance of the 73rd and 74th Constitutional Amendments for local governance in India.",
        "expected_domain": "Polity",
        "paper": "GS2",
        "year": 2020,
        "type": "analytical",
    },
    {
        "id": "upsc-002",
        "question": "What is fiscal deficit? Discuss its implications for the Indian economy.",
        "expected_domain": "Economy",
        "paper": "GS3",
        "year": 2022,
        "type": "factual",
    },
    {
        "id": "upsc-003",
        "question": "Discuss the salient features of the Harappan architecture with suitable examples.",
        "expected_domain": "History",
        "paper": "GS1",
        "year": 2018,
        "type": "factual",
    },
]


async def run_single_question(q_data, question_num):
    """Run the full pipeline for a single question and track all stages."""
    from domain.answer_generation.orchestrator_v3 import build_answer_graph_v3

    print(f"\n{'='*70}")
    print(f"  QUESTION {question_num}: {q_data['question'][:80]}...")
    print(f"  Expected: {q_data['expected_domain']} | {q_data['paper']} | {q_data['year']}")
    print(f"{'='*70}")

    # Build the graph
    graph = build_answer_graph_v3()

    # Initial state
    state = {
        "session_id": q_data["id"],
        "question": q_data["question"],
        "question_metadata": {
            "expected_domain": q_data["expected_domain"],
            "paper": q_data["paper"],
            "year": q_data["year"],
            "type": q_data["type"],
        },
        "cot_trace": [],
        "revision_iterations": 0,
        "reflection_round": 0,
    }

    # Track timing
    stage_times = {}
    total_start = time.monotonic()

    try:
        # ── Stage 1: Intent Classification ─────────────────────────
        print("\n  [1/8] Intent Classification...")
        t0 = time.monotonic()
        from domain.answer_generation.nodes_v3 import node_intent_and_difficulty
        intent_result = await node_intent_and_difficulty(state)
        stage_times["intent"] = round(time.monotonic() - t0, 2)
        state.update(intent_result)
        print(f"    → Domain: {state.get('domain')} (expected: {q_data['expected_domain']})")
        print(f"    → Type: {state.get('question_type')}")
        print(f"    → Difficulty: {state.get('difficulty')}")
        print(f"    → Marks: {state.get('marks')}")
        print(f"    → Confidence: {state.get('topic_confidence')}")
        print(f"    → Time: {stage_times['intent']}s")

        # ── Stage 2: Multi-Query Retrieval ──────────────────────────
        print("\n  [2/8] Multi-Query Retrieval...")
        t0 = time.monotonic()
        from domain.answer_generation.nodes_v3 import node_multi_retrieval
        retrieval_result = await node_multi_retrieval(state)
        stage_times["retrieval"] = round(time.monotonic() - t0, 2)
        state.update(retrieval_result)
        chunks_count = len(state.get("evidence_chunks", []))
        print(f"    → Strategy: {state.get('retrieval_strategy')}")
        print(f"    → Chunks retrieved: {chunks_count}")
        print(f"    → Time: {stage_times['retrieval']}s")

        # ── Stage 3: UPSC Blueprint ────────────────────────────────
        print("\n  [3/8] UPSC Blueprint Generation...")
        t0 = time.monotonic()
        from domain.answer_generation.upsc_blueprint import node_upsc_blueprint
        blueprint_result = await node_upsc_blueprint(state)
        stage_times["blueprint"] = round(time.monotonic() - t0, 2)
        state.update(blueprint_result)
        blueprint = state.get("blueprint", {})
        sections = blueprint.get("sections", [])
        print(f"    → Target words: {blueprint.get('target_words', 'N/A')}")
        print(f"    → Sections: {len(sections)}")
        for i, s in enumerate(sections[:3]):
            print(f"      {i+1}. {s.get('name', '?')} ({s.get('words', '?')} words)")
        if len(sections) > 3:
            print(f"      ... and {len(sections)-3} more")
        print(f"    → Examples: {len(blueprint.get('examples', []))}")
        print(f"    → Must-include: {len(blueprint.get('must_include', []))}")
        print(f"    → Time: {stage_times['blueprint']}s")

        # ── Stage 4: Enhanced Planning ─────────────────────────────
        print("\n  [4/8] Enhanced Planning...")
        t0 = time.monotonic()
        from domain.answer_generation.nodes_v3 import node_enhanced_planner
        planner_result = await node_enhanced_planner(state)
        stage_times["planning"] = round(time.monotonic() - t0, 2)
        state.update(planner_result)
        print(f"    → Framework: {state.get('framework')}")
        print(f"    → Examiner persona: {state.get('examiner_persona', 'N/A')[:60]}")
        print(f"    → Trap: {state.get('trap', 'N/A')[:60]}")
        print(f"    → Differentiator: {state.get('differentiator', 'N/A')[:60]}")
        dimensions = state.get("expected_dimensions", [])
        print(f"    → Dimensions ({len(dimensions)}): {dimensions[:3]}")
        print(f"    → Needs diagram: {state.get('needs_diagram')}")
        print(f"    → Needs table: {state.get('needs_table')}")
        print(f"    → Time: {stage_times['planning']}s")

        # ── Stage 5: Section-Level Drafting ────────────────────────
        print("\n  [5/8] Section-Level Drafting (FULL ANSWER)...")
        t0 = time.monotonic()
        from domain.answer_generation.nodes_v3 import node_section_drafting
        drafting_result = await node_section_drafting(state)
        stage_times["drafting"] = round(time.monotonic() - t0, 2)
        state.update(drafting_result)
        answer = state.get("draft_answer", "")
        word_count = len(answer.split())
        print(f"    → Answer length: {word_count} words")
        print(f"    → Tokens used: {state.get('draft_tokens', 'N/A')}")
        print(f"    → Time: {stage_times['drafting']}s")
        # Show first 200 chars of answer
        print(f"    → Preview: {answer[:200]}...")

        # ── Stage 6: Multi-Reviewer ────────────────────────────────
        print("\n  [6/8] Multi-Reviewer Evaluation...")
        t0 = time.monotonic()
        from domain.answer_generation.nodes_v3 import node_multi_reviewer
        review_result = await node_multi_reviewer(state)
        stage_times["review"] = round(time.monotonic() - t0, 2)
        state.update(review_result)
        review_scores = state.get("review_scores", {})
        overall_score = state.get("overall_score", 0)
        print(f"    → Overall score: {overall_score:.3f}")
        print(f"    → Accuracy: {review_scores.get('accuracy', 'N/A')}")
        print(f"    → Structure: {review_scores.get('structure', 'N/A')}")
        print(f"    → Coverage: {review_scores.get('coverage', 'N/A')}")
        print(f"    → Examples: {review_scores.get('examples', 'N/A')}")
        print(f"    → Constitutional: {review_scores.get('constitutional_grounding', 'N/A')}")
        print(f"    → Flow: {review_scores.get('flow', 'N/A')}")
        print(f"    → Grammar: {review_scores.get('grammar', 'N/A')}")
        print(f"    → UPSC Style: {review_scores.get('upsc_style', 'N/A')}")
        print(f"    → Originality: {review_scores.get('originality', 'N/A')}")
        print(f"    → Time: {stage_times['review']}s")

        # ── Stage 7: Evidence Verification ────────────────────────
        print("\n  [7/8] Evidence Verification...")
        t0 = time.monotonic()
        from domain.answer_generation.nodes_v3 import node_evidence_verification
        verification_result = await node_evidence_verification(state)
        stage_times["verification"] = round(time.monotonic() - t0, 2)
        state.update(verification_result)
        print(f"    → Verification passed: {state.get('verification_passed')}")
        print(f"    → Hallucinations: {len(state.get('hallucination_flags', []))}")
        print(f"    → Claims verified: {len(state.get('evidence_claims', []))}")
        print(f"    → Guardrails passed: {state.get('guardrails_passed')}")
        print(f"    → Time: {stage_times['verification']}s")

        # ── Stage 8: Confidence Estimation ─────────────────────────
        print("\n  [8/8] Confidence Estimation...")
        t0 = time.monotonic()
        from domain.answer_generation.nodes_v3 import node_confidence_estimator
        confidence_result = await node_confidence_estimator(state)
        stage_times["confidence"] = round(time.monotonic() - t0, 2)
        state.update(confidence_result)
        print(f"    → Final confidence: {state.get('confidence')}")
        print(f"    → Time: {stage_times['confidence']}s")

        # ── Summary ────────────────────────────────────────────────
        total_time = round(time.monotonic() - total_start, 2)
        cot_steps = len(state.get("cot_trace", []))

        print(f"\n  {'─'*60}")
        print(f"  PIPELINE SUMMARY")
        print(f"  {'─'*60}")
        print(f"  Total time:        {total_time}s")
        print(f"  CoT steps:         {cot_steps}")
        print(f"  Domain:            {state.get('domain')} (expected: {q_data['expected_domain']})")
        print(f"  Answer length:     {word_count} words")
        print(f"  Overall score:     {overall_score:.3f}")
        print(f"  Confidence:        {state.get('confidence')}")
        print(f"  Verification:      {'PASS' if state.get('verification_passed') else 'FAIL'}")
        print(f"  Hallucinations:    {len(state.get('hallucination_flags', []))}")

        # Stage timing breakdown
        print(f"\n  STAGE TIMING:")
        for stage, t in stage_times.items():
            bar = "█" * min(int(t / 5), 20)
            print(f"    {stage:15s} {t:6.2f}s {bar}")

        # Save result
        result = {
            "question_id": q_data["id"],
            "question": q_data["question"],
            "expected_domain": q_data["expected_domain"],
            "predicted_domain": state.get("domain"),
            "domain_match": state.get("domain") == q_data["expected_domain"],
            "answer_length": word_count,
            "overall_score": overall_score,
            "confidence": state.get("confidence"),
            "verification_passed": state.get("verification_passed"),
            "hallucination_count": len(state.get("hallucination_flags", [])),
            "cot_steps": cot_steps,
            "total_time": total_time,
            "stage_times": stage_times,
            "review_scores": review_scores,
            "answer_preview": answer[:300],
        }

        return result

    except Exception as exc:
        total_time = round(time.monotonic() - total_start, 2)
        logger.error(f"Pipeline failed: {exc}", exc_info=True)
        return {
            "question_id": q_data["id"],
            "question": q_data["question"],
            "error": str(exc),
            "total_time": total_time,
            "stage_times": stage_times,
        }


async def run_all_questions():
    """Run all test questions and generate report."""
    print("\n" + "═" * 70)
    print("  HERMES V2 — FULL ANSWER GENERATION TRACKING & TESTING")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("═" * 70)

    results = []
    for i, q in enumerate(TEST_QUESTIONS, 1):
        result = await run_single_question(q, i)
        results.append(result)

    # ── Final Report ─────────────────────────────────────────────────
    print("\n\n" + "═" * 70)
    print("  FINAL REPORT")
    print("═" * 70)

    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    print(f"\n  Questions tested: {len(results)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")

    if successful:
        avg_time = sum(r["total_time"] for r in successful) / len(successful)
        avg_score = sum(r["overall_score"] for r in successful) / len(successful)
        avg_words = sum(r["answer_length"] for r in successful) / len(successful)
        avg_confidence = sum(r["confidence"] for r in successful) / len(successful)
        domain_matches = sum(1 for r in successful if r["domain_match"])

        print(f"\n  AVERAGES:")
        print(f"    Time per question:     {avg_time:.1f}s")
        print(f"    Answer length:         {avg_words:.0f} words")
        print(f"    Overall score:         {avg_score:.3f}")
        print(f"    Confidence:            {avg_confidence:.3f}")
        print(f"    Domain accuracy:       {domain_matches}/{len(successful)} ({100*domain_matches/len(successful):.0f}%)")

    if failed:
        print(f"\n  FAILURES:")
        for r in failed:
            print(f"    {r['question_id']}: {r['error'][:100]}")

    # Save results to file
    output_dir = Path("/app/dataset/human_test_upsc")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"tracking_results_{int(time.time())}.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_questions": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "results": results,
        }, f, indent=2, default=str)
    print(f"\n  Results saved to: {output_file}")

    return results


if __name__ == "__main__":
    results = asyncio.run(run_all_questions())
    sys.exit(0 if all("error" not in r for r in results) else 1)
