"""
Hermes V3 — Enhanced Answer Generation State
═══════════════════════════════════════════════════════════════
Extended TypedDict for the V3 pipeline with:
- Multi-query retrieval
- Difficulty estimation
- Section-level drafting
- Multi-reviewer feedback
- Confidence estimation
- Citation tracking
- Reflection loop
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ReviewDimension(TypedDict):
    """Dimension-specific review scores."""
    accuracy: float
    structure: float
    coverage: float
    examples: float
    current_affairs: float
    constitutional_grounding: float
    flow: float
    grammar: float
    upsc_style: float
    originality: float


class EvidenceClaim(TypedDict):
    """A verified claim with evidence."""
    claim: str
    evidence_chunk_ids: List[str]
    confidence: float
    verified: bool


class AnswerGenerationStateV3(TypedDict):
    """Complete state for V3 answer-generation pipeline."""

    # ── Identity ─────────────────────────────────────────────
    session_id: str
    question: str
    question_metadata: Dict[str, Any]

    # ── Intent & Difficulty ──────────────────────────────────
    domain: Optional[str]
    question_type: Optional[str]
    detected_entities: List[str]
    constitutional_weight: Optional[str]
    sub_topics: List[str]
    topic_confidence: Optional[float]
    difficulty: Optional[str]                      # easy / medium / hard / very_hard
    marks: Optional[int]                            # 10 or 15
    confidence: Optional[float]                     # 0.0 – 1.0, estimated before answering

    # ── Multi-Query Retrieval ────────────────────────────────
    retrieval_strategy: Optional[str]
    search_queries: List[str]                       # rewritten queries
    retrieved_chunks: List[Dict[str, Any]]
    retrieval_latency_ms: Optional[float]
    retrieval_round: int                            # 1, 2, 3... for adaptive retrieval
    evidence_chunks: List[Dict[str, Any]]            # filtered relevant evidence

    # ── Planning ─────────────────────────────────────────────
    reasoning_plan: Optional[str]
    framework: Optional[str]
    examiner_persona: Optional[str]
    trap: Optional[str]
    differentiator: Optional[str]
    expected_dimensions: List[str]                  # what the answer should cover
    needs_diagram: bool
    needs_table: bool
    needs_current_affairs: bool
    planning_notes: Optional[str]

    # ── Section-Level Drafting ───────────────────────────────
    draft_answer: Optional[str]
    draft_sections: Dict[str, str]                  # intro, body, examples, conclusion
    draft_model: Optional[str]
    draft_tokens: Optional[int]
    draft_latency_ms: Optional[float]

    # ── Multi-Reviewer ───────────────────────────────────────
    review_scores: ReviewDimension
    overall_score: Optional[float]
    reviewer_feedback: List[Dict[str, Any]]          # per-reviewer feedback
    revision_iterations: int
    max_revisions: int

    # ── Evidence Verification ────────────────────────────────
    evidence_claims: List[EvidenceClaim]
    verification_passed: bool
    hallucination_flags: List[str]

    # ── Reflection Loop ──────────────────────────────────────
    reflection_round: int
    quality_threshold: float
    needs_reflection: bool

    # ── Citation Graph ───────────────────────────────────────
    citation_map: Dict[str, List[str]]            # paragraph → chunk IDs

    # ── Guardrails ───────────────────────────────────────────
    guardrails_passed: bool
    guardrails_notes: Optional[str]

    # ── Final Output ─────────────────────────────────────────
    final_answer: Optional[str]
    total_cost_usd: float
    total_latency_ms: float
    total_tokens: int
    models_used: List[str]

    # ── Training Data ────────────────────────────────────────
    cot_trace: List[Dict[str, Any]]
    quality_score: Optional[float]
    training_eligible: bool
    training_data_version: str                      # "3.0"

    # ── System ───────────────────────────────────────────────
    error: Optional[str]
    feedback: Dict[str, Any]
