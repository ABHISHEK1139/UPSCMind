"""
Hermes V2 — Answer Generation State
═══════════════════════════════════════════════════════════════
TypedDict representing the full state that flows through the
LangGraph orchestrator.  Every node reads from and writes to
this state.  The DatasetCollector intercepts it at the end
to produce training data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AnswerGenerationState(TypedDict):
    """Complete state for a single answer-generation run."""

    # ── Identity ─────────────────────────────────────────────
    session_id: str
    question: str

    # ── Topic Detection Node ─────────────────────────────────
    domain: Optional[str]
    question_type: Optional[str]
    detected_entities: List[str]
    constitutional_weight: Optional[str]          # HIGH / MEDIUM / LOW / VERY_LOW
    sub_topics: List[str]
    topic_confidence: Optional[float]             # 0.0 – 1.0

    # ── Retrieval Node ───────────────────────────────────────
    retrieval_strategy: Optional[str]
    retrieved_chunks: List[Dict[str, Any]]
    retrieval_latency_ms: Optional[float]
    retrieval_notes: Optional[str]                # why this strategy was chosen

    # ── Planning Node ────────────────────────────────────────
    reasoning_plan: Optional[str]
    framework: Optional[str]
    examiner_persona: Optional[str]
    trap: Optional[str]                           # common student mistake
    differentiator: Optional[str]                 # non-obvious insight
    planning_notes: Optional[str]                 # scratchpad

    # ── Drafting Node ────────────────────────────────────────
    draft_answer: Optional[str]
    draft_model: Optional[str]
    draft_tokens: Optional[int]
    draft_latency_ms: Optional[float]

    # ── Review Node ──────────────────────────────────────────
    critique: Optional[str]
    critique_score: Optional[float]               # 0.0 – 1.0
    critique_model: Optional[str]
    critique_latency_ms: Optional[float]

    # ── Fact Check Node ──────────────────────────────────────
    fact_check_passed: bool
    fact_check_issues: Optional[str]
    constitutional_check_passed: bool
    constitutional_check_notes: Optional[str]
    guardrails_passed: bool
    guardrails_notes: Optional[str]

    # ── Revision Node (looped) ───────────────────────────────
    revision_iterations: int
    improved_answer: Optional[str]
    revision_notes: Optional[str]                 # what changed and why

    # ── Verification Pipeline ────────────────────────────────
    verification_passed: bool
    verification_layers: Dict[str, bool]          # per-layer results

    # ── Final Output ─────────────────────────────────────────
    final_answer: Optional[str]
    total_cost_usd: float
    total_latency_ms: float
    total_tokens: int
    models_used: List[str]

    # ── Training Data Fields ─────────────────────────────────
    cot_trace: List[Dict[str, Any]]               # full chain-of-thought trace
    quality_score: Optional[float]                # aggregate quality metric
    training_eligible: bool                       # passes all quality gates

    # ── System ───────────────────────────────────────────────
    error: Optional[str]
