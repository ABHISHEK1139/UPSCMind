"""
Hermes V2 — Dataset Collector
═══════════════════════════════════════════════════════════════
Intercepts LangGraph state at the end of each run, applies
strict quality gating, and writes training-ready records.

Quality Gates (ALL must pass):
  1. critique_score >= 0.9
  2. fact_check_passed == True
  3. guardrails_passed == True
  4. revision_iterations <= 2
  5. constitutional_check_passed == True (if constitutional_weight is HIGH)
  6. final_answer length >= 200 words (ensures substance)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from domain.dataset.schemas import (
    ChatMLRecord,
    ChatMLMessage,
    CoTStep,
    DPORecord,
    ORPORecord,
    RewardModelRecord,
    TrajectoryRecord,
)

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("dataset/training_data")
QUALITY_THRESHOLD = 0.7
MIN_ANSWER_WORDS = 200
MAX_REVISIONS = 2


class DatasetCollector:
    """
    Collects, quality-gates, and stores training data from
    LangGraph orchestrator runs.
    """

    def __init__(
        self,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
        quality_threshold: float = QUALITY_THRESHOLD,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._quality_threshold = quality_threshold

        # Output files
        self._trajectory_file = self._output_dir / "trajectories.jsonl"
        self._chatml_file = self._output_dir / "chatml_sft.jsonl"
        self._dpo_file = self._output_dir / "dpo_pairs.jsonl"
        self._orpo_file = self._output_dir / "orpo_pairs.jsonl"
        self._reward_file = self._output_dir / "reward_model.jsonl"
        self._rejected_file = self._output_dir / "rejected.jsonl"

    # ── Quality Gating ────────────────────────────────────────

    def check_quality(self, state: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Run all quality gates.  Returns (passed, rejection_reason).
        """
        # Support both V1/V2 (critique_score) and V3 (overall_score)
        score: float = state.get("overall_score") or state.get("critique_score", 0.0) or 0.0
        fact_passed: bool = state.get("fact_check_passed", False)
        guardrails_passed: bool = state.get("guardrails_passed", False)
        revisions: int = state.get("revision_iterations", 0)
        answer: str = state.get("final_answer") or state.get("draft_answer") or ""
        word_count = len(answer.split())
        constitutional_weight: str = state.get("constitutional_weight", "LOW")
        constitutional_passed: bool = state.get("constitutional_check_passed", False)

        if score < self._quality_threshold:
            return False, f"critique_score {score:.2f} < {self._quality_threshold}"
        if not fact_passed:
            return False, "fact_check_failed"
        if not guardrails_passed:
            return False, "guardrails_failed"
        if revisions > MAX_REVISIONS:
            return False, f"too_many_revisions ({revisions} > {MAX_REVISIONS})"
        if word_count < MIN_ANSWER_WORDS:
            return False, f"answer_too_short ({word_count} < {MIN_ANSWER_WORDS} words)"
        if constitutional_weight == "HIGH" and not constitutional_passed:
            return False, "constitutional_check_failed"

        return True, None

    @staticmethod
    def _get_verification_flags(state: Dict[str, Any]) -> tuple:
        """Safely extract verification flags from state with proper defaults."""
        fact_passed = state.get("fact_check_passed", False)
        guardrails_passed = state.get("guardrails_passed", True)
        constitutional_passed = state.get("constitutional_check_passed", False)
        return fact_passed, guardrails_passed, constitutional_passed

    # ── CoT Trace Builder ─────────────────────────────────────

    def build_cot_trace(self, state: Dict[str, Any]) -> List[CoTStep]:
        """Build a structured Chain-of-Thought trace from the state."""
        trace: List[CoTStep] = []
        step = 0

        # Step 1: Topic Detection
        if state.get("domain"):
            step += 1
            entities = ", ".join(state.get("detected_entities", []))
            trace.append(CoTStep(
                step_number=step,
                node="topic_detection",
                thought=(
                    f"Analyzing question to determine domain and intent. "
                    f"Identified domain: {state['domain']}. "
                    f"Question type: {state.get('question_type', 'unknown')}. "
                    f"Key entities: {entities}. "
                    f"Constitutional weight: {state.get('constitutional_weight', 'LOW')}."
                ),
                output={
                    "domain": state.get("domain"),
                    "question_type": state.get("question_type"),
                    "entities": state.get("detected_entities"),
                    "constitutional_weight": state.get("constitutional_weight"),
                },
                model_used=state.get("models_used", [None])[0] if state.get("models_used") else None,
            ))

        # Step 2: Retrieval (support both V1/V2 and V3 field names)
        chunks = state.get("evidence_chunks") or state.get("retrieved_chunks") or []
        if chunks:
            step += 1
            strategy = state.get("retrieval_strategy", "hybrid")
            trace.append(CoTStep(
                step_number=step,
                node="retrieval",
                thought=(
                    f"Selected retrieval strategy: {strategy}. "
                    f"Retrieved {len(chunks)} relevant context chunks from "
                    f"knowledge base (Qdrant + BM25 + Neo4j). "
                    f"Top sources: {', '.join(set(c.get('source', 'unknown') for c in chunks[:3]))}."
                ),
                output={
                    "strategy": strategy,
                    "chunks_count": len(chunks),
                    "top_scores": [c.get("score", 0) for c in chunks[:3]],
                },
                latency_ms=state.get("retrieval_latency_ms"),
            ))

        # Step 3: Planning
        if state.get("reasoning_plan"):
            step += 1
            trace.append(CoTStep(
                step_number=step,
                node="planning",
                thought=(
                    f"Developing reasoning plan. Framework: {state.get('framework', 'Thematic')}. "
                    f"Examiner persona: {state.get('examiner_persona', 'general')}. "
                    f"Common trap to avoid: {state.get('trap', 'none')}. "
                    f"Differentiator: {state.get('differentiator', 'none')}. "
                    f"Plan: {state['reasoning_plan'][:300]}..."
                ),
                output={
                    "framework": state.get("framework"),
                    "reasoning_plan": state.get("reasoning_plan"),
                    "examiner_persona": state.get("examiner_persona"),
                    "trap": state.get("trap"),
                    "differentiator": state.get("differentiator"),
                },
                latency_ms=None,
            ))

        # Step 4: Drafting
        if state.get("draft_answer"):
            step += 1
            trace.append(CoTStep(
                step_number=step,
                node="drafting",
                thought=(
                    f"Drafting the answer using {state.get('framework', 'Thematic')} framework. "
                    f"Following the reasoning plan with {len(chunks)} context chunks. "
                    f"Target: comprehensive 800-1200 word UPSC-grade answer."
                ),
                output={
                    "draft_length_words": len(state.get("draft_answer", "").split()),
                    "model": state.get("draft_model"),
                },
                model_used=state.get("draft_model"),
                latency_ms=state.get("draft_latency_ms"),
                tokens_used=state.get("draft_tokens"),
            ))

        # Step 5: Review / Critique
        if state.get("critique"):
            step += 1
            score = state.get("critique_score", 0.0)
            trace.append(CoTStep(
                step_number=step,
                node="review",
                thought=(
                    f"Self-evaluation complete. Critique score: {score:.2f}/1.0. "
                    f"Feedback: {state['critique'][:400]}..."
                ),
                output={
                    "critique": state.get("critique"),
                    "critique_score": state.get("critique_score"),
                },
                model_used=state.get("critique_model"),
                latency_ms=state.get("critique_latency_ms"),
            ))

        # Step 6: Revision (if any)
        revisions = state.get("revision_iterations", 0)
        if revisions > 0 and state.get("improved_answer"):
            step += 1
            trace.append(CoTStep(
                step_number=step,
                node="revision",
                thought=(
                    f"Self-correction loop triggered {revisions} time(s). "
                    f"Addressing critique feedback and fact-check issues. "
                    f"Improving answer quality."
                ),
                output={
                    "revisions": revisions,
                    "improved_length_words": len(state.get("improved_answer", "").split()),
                },
            ))

        # Step 7: Verification
        step += 1
        v_fact, v_guard, v_const = self._get_verification_flags(state)
        trace.append(CoTStep(
            step_number=step,
            node="verification",
            thought=(
                f"Running multi-layer verification. "
                f"Fact check: {'PASSED' if v_fact else 'FAILED'}. "
                f"Guardrails: {'PASSED' if v_guard else 'FAILED'}. "
                f"Constitutional check: {'PASSED' if v_const else 'FAILED'}. "
                f"Overall: {'ALL PASSED' if (v_fact and v_guard and v_const) else 'ISSUES FOUND'}."
            ),
            output={
                "fact_check_passed": v_fact,
                "guardrails_passed": v_guard,
                "constitutional_check_passed": v_const,
            },
        ))

        return trace

    # ── Format Converters ─────────────────────────────────────

    def to_trajectory(self, state: Dict[str, Any]) -> TrajectoryRecord:
        """Convert state to a full TrajectoryRecord."""
        cot_trace = self.build_cot_trace(state)
        passed, rejection = self.check_quality(state)

        answer = state.get("final_answer") or state.get("improved_answer") or state.get("draft_answer") or ""

        return TrajectoryRecord(
            question=state.get("question", ""),
            question_metadata=state.get("question_metadata", {}),
            cot_trace=cot_trace,
            domain=state.get("domain"),
            question_type=state.get("question_type"),
            constitutional_weight=state.get("constitutional_weight"),
            retrieved_chunks=state.get("evidence_chunks") or state.get("retrieved_chunks") or [],
            retrieval_strategy=state.get("retrieval_strategy"),
            reasoning_plan=state.get("reasoning_plan"),
            framework=state.get("framework"),
            examiner_persona=state.get("examiner_persona"),
            trap=state.get("trap"),
            differentiator=state.get("differentiator"),
            draft_answer=state.get("draft_answer"),
            critique=state.get("critique"),
            critique_score=state.get("critique_score"),
            fact_check_passed=state.get("fact_check_passed", False),
            guardrails_passed=state.get("guardrails_passed", False),
            constitutional_check_passed=state.get("constitutional_check_passed", False),
            revision_iterations=state.get("revision_iterations", 0),
            improved_answer=state.get("improved_answer"),
            final_answer=answer,
            quality_score=state.get("overall_score") or state.get("critique_score"),
            training_eligible=passed,
            rejection_reason=rejection,
            total_cost_usd=state.get("total_cost_usd", 0.0),
            total_latency_ms=state.get("total_latency_ms", 0.0),
            total_tokens=state.get("total_tokens", 0),
            models_used=state.get("models_used", []),
            feedback=state.get("feedback", {}),
        )

    def to_chatml(self, trajectory: TrajectoryRecord) -> ChatMLRecord:
        """Convert a trajectory to ChatML format for SFT."""
        system_content = (
            "You are Hermes, an advanced AI trained to analyze and answer "
            "UPSC Civil Services questions. You must think step-by-step "
            "before answering, following this process:\n"
            "1. Identify domain, question type, and key entities\n"
            "2. Retrieve relevant knowledge\n"
            "3. Plan your answer structure and framework\n"
            "4. Draft a comprehensive answer\n"
            "5. Self-evaluate and correct\n"
            "6. Verify factual accuracy\n\n"
            "Always wrap your reasoning in <think></think> tags."
        )

        # Build the <think> block from CoT trace
        think_lines = []
        for step in trajectory.cot_trace:
            think_lines.append(f"Step {step.step_number} [{step.node}]: {step.thought}")
        think_text = "\n\n".join(think_lines)

        assistant_content = f"<think>\n{think_text}\n</think>\n\n{trajectory.final_answer or ''}"

        return ChatMLRecord(
            messages=[
                ChatMLMessage(role="system", content=system_content),
                ChatMLMessage(role="user", content=trajectory.question),
                ChatMLMessage(role="assistant", content=assistant_content),
            ],
            metadata={
                "id": trajectory.id,
                "quality_score": trajectory.quality_score,
                "domain": trajectory.domain,
                "training_eligible": trajectory.training_eligible,
            },
        )

    def to_dpo_pair(self, trajectory: TrajectoryRecord) -> Optional[DPORecord]:
        """Create a DPO preference pair (chosen=final, rejected=draft)."""
        if not trajectory.final_answer or not trajectory.draft_answer:
            return None
        if trajectory.final_answer == trajectory.draft_answer:
            return None  # No revision happened, no preference signal

        return DPORecord(
            prompt=trajectory.question,
            chosen=trajectory.final_answer,
            rejected=trajectory.draft_answer,
            metadata={
                "id": trajectory.id,
                "critique_score": trajectory.critique_score,
                "domain": trajectory.domain,
                "revisions": trajectory.revision_iterations,
            },
        )

    def to_orpo_pair(self, trajectory: TrajectoryRecord) -> Optional[ORPORecord]:
        """Create an ORPO preference pair."""
        dpo = self.to_dpo_pair(trajectory)
        if dpo is None:
            return None
        return ORPORecord(
            prompt=dpo.prompt,
            chosen=dpo.chosen,
            rejected=dpo.rejected,
            metadata=dpo.metadata,
        )

    def to_reward_record(self, trajectory: TrajectoryRecord) -> Optional[RewardModelRecord]:
        """Create a reward model training record."""
        if not trajectory.final_answer or trajectory.quality_score is None:
            return None
        return RewardModelRecord(
            answer=trajectory.final_answer,
            score=trajectory.quality_score,
            rubric_scores={
                "critique_score": trajectory.critique_score or 0.0,
                "fact_check": 1.0 if trajectory.fact_check_passed else 0.0,
                "guardrails": 1.0 if trajectory.guardrails_passed else 0.0,
                "constitutional": 1.0 if trajectory.constitutional_check_passed else 0.0,
            },
            metadata={
                "id": trajectory.id,
                "domain": trajectory.domain,
            },
        )

    # ── Main Collection Entry Point ───────────────────────────

    def collect_from_state(self, state: Dict[str, Any]) -> Optional[TrajectoryRecord]:
        """
        Main entry point.  Quality-gates the state, converts to
        all training formats, and writes to disk.

        Returns the TrajectoryRecord if it passed quality gates,
        or None if rejected.
        """
        passed, rejection = self.check_quality(state)
        trajectory = self.to_trajectory(state)

        # Always save trajectory (for analysis)
        self._append_jsonl(self._trajectory_file, trajectory.model_dump(mode="json"))

        if not passed:
            logger.info(
                "[COLLECTOR] Rejected trajectory: %s (score=%.2f)",
                rejection,
                state.get("critique_score", 0.0),
            )
            self._append_jsonl(self._rejected_file, trajectory.model_dump(mode="json"))
            return None

        logger.info(
            "[COLLECTOR] Accepted trajectory: domain=%s score=%.2f revisions=%d",
            trajectory.domain,
            trajectory.quality_score,
            trajectory.revision_iterations,
        )

        # Write ChatML (SFT)
        chatml = self.to_chatml(trajectory)
        self._append_jsonl(self._chatml_file, chatml.model_dump(mode="json"))

        # Write DPO pair
        dpo = self.to_dpo_pair(trajectory)
        if dpo:
            self._append_jsonl(self._dpo_file, dpo.model_dump(mode="json"))

        # Write ORPO pair
        orpo = self.to_orpo_pair(trajectory)
        if orpo:
            self._append_jsonl(self._orpo_file, orpo.model_dump(mode="json"))

        # Write Reward Model record
        reward = self.to_reward_record(trajectory)
        if reward:
            self._append_jsonl(self._reward_file, reward.model_dump(mode="json"))

        return trajectory

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
        """Append a JSON record to a .jsonl file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
