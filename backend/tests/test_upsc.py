"""
UPSC Hermes V3 — Production Test Suite
═══════════════════════════════════════════════════════════════
Tests the complete answer generation pipeline across all domains.
Results saved to: dataset/human_test_upsc/results.jsonl
"""

import asyncio
import json
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

# ═══════════════════════════════════════════════════════════════
# TEST QUESTIONS — 10 DOMAINS
# ═══════════════════════════════════════════════════════════════

QUESTIONS = [
    {"q": "Discuss the significance of the 73rd and 74th Constitutional Amendments for local governance.", "domain": "Polity", "paper": "GS2", "year": 2020, "type": "analytical"},
    {"q": "What is fiscal deficit? Discuss its implications for the Indian economy.", "domain": "Economy", "paper": "GS3", "year": 2022, "type": "factual"},
    {"q": "Discuss the salient features of the Harappan architecture with suitable examples.", "domain": "History", "paper": "GS1", "year": 2018, "type": "factual"},
    {"q": "Discuss the role of monsoons in Indian agriculture and the economy.", "domain": "Geography", "paper": "GS1", "year": 2021, "type": "analytical"},
    {"q": "Discuss the impact of climate change on India's agriculture and food security.", "domain": "Environment", "paper": "GS3", "year": 2023, "type": "analytical"},
    {"q": "Discuss the evolution of India's foreign policy since independence with reference to non-alignment.", "domain": "IR", "paper": "GS2", "year": 2023, "type": "evolution"},
    {"q": "What is the role of ISRO in India's space programme? Discuss its recent achievements.", "domain": "Science-Tech", "paper": "GS3", "year": 2023, "type": "factual"},
    {"q": "What is the difference between ethical governance and good governance? Discuss with examples.", "domain": "Ethics", "paper": "GS4", "year": 2022, "type": "analytical"},
    {"q": "Discuss the impact of globalization on Indian society and culture.", "domain": "Society", "paper": "GS1", "year": 2019, "type": "analytical"},
    {"q": "What is the significance of the Right to Information Act for transparency and accountability?", "domain": "Governance", "paper": "GS2", "year": 2022, "type": "analytical"},
]


async def run_test():
    from domain.answer_generation.orchestrator_v3 import build_answer_graph_v3

    graph = build_answer_graph_v3()
    output_dir = Path("/app/dataset/human_test_upsc")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "results.jsonl"
    output_file.write_text("")

    total_start = time.monotonic()

    for i, item in enumerate(QUESTIONS):
        session_id = f"upsc-{i+1:03d}"
        state = {
            "session_id": session_id,
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
        t0 = time.monotonic()
        try:
            result = await graph.ainvoke(state)
            elapsed = time.monotonic() - t0
            record = {
                "id": session_id,
                "question": item["q"],
                "expected_domain": item["domain"],
                "paper": item["paper"],
                "year": item["year"],
                "type": item["type"],
                "predicted_domain": result.get("domain"),
                "question_type": result.get("question_type"),
                "difficulty": result.get("difficulty"),
                "score": result.get("overall_score"),
                "confidence": result.get("confidence"),
                "verification": result.get("verification_passed"),
                "cot_steps": len(result.get("cot_trace", [])),
                "answer_length": len(result.get("draft_answer", "")),
                "latency_s": round(elapsed, 1),
                "answer": result.get("draft_answer", ""),
                "blueprint": result.get("blueprint", {}),
                "review_scores": result.get("review_scores", {}),
                "error": None,
            }
        except Exception as e:
            elapsed = time.monotonic() - t0
            record = {
                "id": session_id,
                "question": item["q"],
                "expected_domain": item["domain"],
                "paper": item["paper"],
                "year": item["year"],
                "type": item["type"],
                "error": str(e)[:200],
                "latency_s": round(elapsed, 1),
            }

        with open(output_file, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

        status = "OK" if not record.get("error") else "ERR"
        score_str = f"{record['score']:.3f}" if record.get("score") is not None else "-"
        print(f"[{i+1:02d}/{len(QUESTIONS)}] {status} score={score_str} lat={elapsed:.0f}s | {item['q'][:60]}")

    total_elapsed = time.monotonic() - total_start
    print(f"\nDone! {len(QUESTIONS)} questions in {total_elapsed:.0f}s")
    print(f"Results: {output_file}")


if __name__ == "__main__":
    asyncio.run(run_test())
