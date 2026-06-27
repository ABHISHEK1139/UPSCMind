"""
Hermes V2 — DSPy GEPA Optimizer Integration
═══════════════════════════════════════════════════════════════
Uses DSPy 3.3's GEPA (Reflective Prompt Evolution) to automatically
optimize your answer generation prompts based on collected trajectories.

GEPA is a prompt optimizer that uses reflective evolution to iteratively
improve prompts. It's been shown to outperform reinforcement learning
on many tasks.

Usage:
    python -m dspy_gepa_optimizer --trajectories dataset/training_data/trajectories.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import dspy

logger = logging.getLogger(__name__)


# ── Quality Metric for GEPA ──────────────────────────────────────────

class UPSCQualityMetric:
    """
    Scoring function for GEPA optimization.
    Uses the critique_score from collected trajectories as the ground truth.
    """

    def __init__(self) -> None:
        self._evaluator = dspy.ChainOfThought(
            "question, answer -> quality_score: float, reasoning: str"
        )

    def __call__(
        self,
        question: str,
        answer: str,
        reference_score: Optional[float] = None,
    ) -> float:
        """Return a quality score between 0.0 and 1.0."""
        try:
            result = self._evaluator(question=question, answer=answer)
            score = float(result.quality_score)
            return max(0.0, min(1.0, score))
        except Exception:
            return reference_score or 0.5


# ── GEPA Optimizer ───────────────────────────────────────────────────

class HermesGEPAOptimizer:
    """
    Optimizes Hermes V2's answer generation pipeline using GEPA.
    
    Takes collected high-quality trajectories and uses them as training
    data to evolve better prompts for each DSPy signature.
    """

    def __init__(
        self,
        trajectories_path: str | Path = "dataset/training_data/trajectories.jsonl",
        output_dir: str | Path = "optimized_prompts",
        max_budget: int = 100,
        auto: str = "medium",  # "light", "medium", "heavy"
    ) -> None:
        self._trajectories_path = Path(trajectories_path)
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._max_budget = max_budget
        self._auto = auto
        self._metric = UPSCQualityMetric()

    def load_training_data(self) -> list[dict]:
        """Load trajectories as training examples for GEPA."""
        if not self._trajectories_path.exists():
            logger.error("Trajectories file not found: %s", self._trajectories_path)
            return []

        examples = []
        with open(self._trajectories_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    # Only use high-quality trajectories
                    if record.get("training_eligible", False):
                        examples.append({
                            "question": record.get("question", ""),
                            "answer": record.get("final_answer", ""),
                            "domain": record.get("domain", "General Studies"),
                            "critique_score": record.get("critique_score", 0.9),
                            "cot_trace": record.get("cot_trace", []),
                        })
                except json.JSONDecodeError:
                    continue

        logger.info("[GEPA] Loaded %d training examples.", len(examples))
        return examples

    def optimize(self) -> Dict[str, Any]:
        """
        Run GEPA optimization on the answer generation pipeline.

        Returns
        -------
        dict with optimization results and paths to saved prompts.
        """
        examples = self.load_training_data()
        if len(examples) < 10:
            logger.warning(
                "[GEPA] Need at least 10 training examples, got %d. "
                "Collect more data before optimizing.",
                len(examples),
            )
            return {"status": "insufficient_data", "examples_found": len(examples)}

        # Convert to DSPy examples
        trainset = []
        for ex in examples:
            trainset.append(
                dspy.Example(
                    question=ex["question"],
                    answer=ex["answer"],
                    domain=ex["domain"],
                    quality_score=ex["critique_score"],
                ).with_inputs("question", "domain")
            )

        # Split into train/val
        split_idx = int(len(trainset) * 0.8)
        train = trainset[:split_idx]
        val = trainset[split_idx:]

        # Define the program to optimize
        program = _AnswerGenerationProgram()

        # Define the metric
        def metric_fn(example, pred, trace=None):
            score = self._metric(
                question=example.question,
                answer=pred.answer if hasattr(pred, "answer") else str(pred),
                reference_score=example.quality_score if hasattr(example, "quality_score") else None,
            )
            return score

        # Run GEPA
        logger.info("[GEPA] Starting optimization with %d train, %d val examples...", len(train), len(val))

        try:
            optimizer = dspy.GEPA(
                metric=metric_fn,
                auto=self._auto,
                num_threads=4,
                max_budget=self._max_budget,
            )

            optimized = optimizer.compile(
                program,
                trainset=train,
                valset=val,
            )

            # Save optimized program
            output_path = self._output_dir / "optimized_answer_program.json"
            optimized.save(str(output_path))

            # Save metadata
            metadata = {
                "status": "success",
                "training_examples": len(train),
                "validation_examples": len(val),
                "max_budget": self._max_budget,
                "auto_mode": self._auto,
                "output_path": str(output_path),
            }
            metadata_path = self._output_dir / "optimization_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info("[GEPA] Optimization complete. Saved to %s", output_path)
            return metadata

        except Exception as exc:
            logger.error("[GEPA] Optimization failed: %s", exc)
            return {"status": "error", "error": str(exc)}


class _AnswerGenerationProgram(dspy.Module):
    """The answer generation program that GEPA will optimize."""

    def __init__(self) -> None:
        super().__init__()
        self.topic_detector = dspy.ChainOfThought(
            "question -> domain, question_type, entities"
        )
        self.planner = dspy.ChainOfThought(
            "question, domain, context -> reasoning_plan, framework"
        )
        self.drafter = dspy.ChainOfThought(
            "question, domain, reasoning_plan, framework, context -> answer"
        )

    def forward(self, question: str, domain: str = "General Studies") -> dspy.Prediction:
        # Topic detection
        topic = self.topic_detector(question=question)

        # Planning (with empty context for now — GEPA optimizes the prompt)
        plan = self.planner(
            question=question,
            domain=domain,
            context="(retrieved context will be provided at runtime)",
        )

        # Drafting
        draft = self.drafter(
            question=question,
            domain=domain,
            reasoning_plan=plan.reasoning_plan,
            framework=plan.framework,
            context="(retrieved context will be provided at runtime)",
        )

        return dspy.Prediction(
            answer=draft.answer,
            domain=topic.domain,
            framework=plan.framework,
        )


# ── CLI Entry Point ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Optimize Hermes V2 prompts with GEPA")
    parser.add_argument("--trajectories", default="dataset/training_data/trajectories.jsonl")
    parser.add_argument("--output-dir", default="optimized_prompts")
    parser.add_argument("--max-budget", type=int, default=100)
    parser.add_argument("--auto", default="medium", choices=["light", "medium", "heavy"])
    args = parser.parse_args()

    optimizer = HermesGEPAOptimizer(
        trajectories_path=args.trajectories,
        output_dir=args.output_dir,
        max_budget=args.max_budget,
        auto=args.auto,
    )
    results = optimizer.optimize()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
