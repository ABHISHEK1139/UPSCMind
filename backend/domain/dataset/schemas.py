"""
Hermes V2 — Training Data Schemas
═══════════════════════════════════════════════════════════════
Pydantic models for every training data format produced by the
system.  All formats are designed for direct consumption by
Unsloth, Axolotl, LLaMA-Factory, or TRL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── CoT Step ──────────────────────────────────────────────────────────

class CoTStep(BaseModel):
    """A single step in the Chain-of-Thought trace."""

    step_number: int
    node: str                              # e.g. "topic_detection", "planning"
    thought: str                           # the internal reasoning
    output: Dict[str, Any]                 # the node's output
    model_used: Optional[str] = None
    latency_ms: Optional[float] = None
    tokens_used: Optional[int] = None


# ── Trajectory Record ─────────────────────────────────────────────────

class TrajectoryRecord(BaseModel):
    """Full agent trajectory — the core training data unit."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "2.0"

    # Question metadata
    question: str
    question_metadata: Dict[str, Any] = Field(default_factory=dict)
    # e.g. {"year": 2024, "paper": "GS2", "domain": "polity", "marks": 15}

    # Full CoT trace
    cot_trace: List[CoTStep] = Field(default_factory=list)

    # Node-level outputs (flat access)
    domain: Optional[str] = None
    question_type: Optional[str] = None
    constitutional_weight: Optional[str] = None
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    retrieval_strategy: Optional[str] = None
    reasoning_plan: Optional[str] = None
    framework: Optional[str] = None
    examiner_persona: Optional[str] = None
    trap: Optional[str] = None
    differentiator: Optional[str] = None
    draft_answer: Optional[str] = None
    critique: Optional[str] = None
    critique_score: Optional[float] = None
    fact_check_passed: bool = False
    guardrails_passed: bool = False
    constitutional_check_passed: bool = False
    revision_iterations: int = 0
    improved_answer: Optional[str] = None
    final_answer: Optional[str] = None

    # Quality metrics
    quality_score: Optional[float] = None
    training_eligible: bool = False
    rejection_reason: Optional[str] = None

    # Cost & performance
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    models_used: List[str] = Field(default_factory=list)

    # Feedback
    feedback: Dict[str, Any] = Field(default_factory=dict)
    # e.g. {"rating": 5, "corrections": null, "collected_at": "..."}


# ── ChatML Format ──────────────────────────────────────────────────────

class ChatMLMessage(BaseModel):
    role: str       # "system" | "user" | "assistant"
    content: str


class ChatMLRecord(BaseModel):
    """ChatML / ShareGPT format for SFT fine-tuning."""

    messages: List[ChatMLMessage]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── DPO Format ────────────────────────────────────────────────────────

class DPORecord(BaseModel):
    """Direct Preference Optimization record."""

    prompt: str
    chosen: str          # the high-quality answer
    rejected: str        # the lower-quality draft
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── ORPO Format ───────────────────────────────────────────────────────

class ORPORecord(BaseModel):
    """Odds Ratio Preference Optimization record."""

    prompt: str
    chosen: str
    rejected: str
    chosen_logps: Optional[float] = None
    rejected_logps: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Reward Model Format ───────────────────────────────────────────────

class RewardModelRecord(BaseModel):
    """Training data for reward model."""

    answer: str
    score: float                     # 0.0 – 1.0
    rubric_scores: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Export Manifest ───────────────────────────────────────────────────

class ExportFormat(str, Enum):
    CHATML = "chatml"
    SHAREGPT = "sharegpt"
    DPO = "dpo"
    ORPO = "orpo"
    REWARD_MODEL = "reward_model"
    TRAJECTORY = "trajectory"


class ExportManifest(BaseModel):
    """Manifest for an export batch."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    format: ExportFormat
    total_records: int
    quality_threshold: float
    output_path: str
    min_score: float = 0.0
    max_score: float = 1.0
    avg_score: float = 0.0
    domains: Dict[str, int] = Field(default_factory=dict)
    rejected_count: int = 0
