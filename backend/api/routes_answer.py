"""
Hermes V2 — Answer Generation Routes
═══════════════════════════════════════════════════════════════
API endpoints for generating UPSC answers through the LangGraph
orchestrator. Supports both synchronous and streaming responses.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Lazy graph initialization ───────────────────────────────────────

_graph: Any = None


def _get_graph():
    """Lazy-initialize the LangGraph (avoids import-time side effects)."""
    global _graph
    if _graph is None:
        from domain.answer_generation.orchestrator_v3 import build_answer_graph_v3
        _graph = build_answer_graph_v3()
        logger.info("[API] LangGraph V3 initialized.")
    return _graph


# ── Request/Response Models ──────────────────────────────────────────

class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    year: Optional[int] = None
    paper: Optional[str] = None
    marks: Optional[int] = None


class AnswerResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    domain: Optional[str] = None
    question_type: Optional[str] = None
    framework: Optional[str] = None
    critique_score: Optional[float] = None
    fact_check_passed: bool = False
    guardrails_passed: bool = True
    revision_iterations: int = 0
    training_eligible: bool = False
    cot_trace: list = []
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    models_used: list = []
    error: Optional[str] = None


def _build_initial_state(request: AnswerRequest) -> Dict[str, Any]:
    """Build the full initial state for the LangGraph orchestrator."""
    return {
        "session_id": request.session_id,
        "question": request.question,
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
        "question_metadata": {"year": request.year, "paper": request.paper, "marks": request.marks},
        "error": None, "feedback": {},
    }


@router.post("/answer", response_model=AnswerResponse)
async def generate_answer(request: AnswerRequest) -> AnswerResponse:
    """Generate a UPSC answer through the full LangGraph pipeline."""
    t0 = time.monotonic()
    try:
        state = _build_initial_state(request)
        result = await _get_graph().ainvoke(state)
        latency_ms = (time.monotonic() - t0) * 1000
        logger.info("[API] Answer: domain=%s score=%.2f rev=%d %.0fms",
                     result.get("domain"), result.get("critique_score", 0),
                     result.get("revision_iterations", 0), latency_ms)
        return AnswerResponse(
            session_id=request.session_id, question=request.question,
            answer=result.get("final_answer") or result.get("draft_answer") or "Failed.",
            domain=result.get("domain"), question_type=result.get("question_type"),
            framework=result.get("framework"),
            critique_score=result.get("overall_score") or result.get("critique_score"),
            fact_check_passed=result.get("verification_passed") or result.get("fact_check_passed", False),
            guardrails_passed=result.get("guardrails_passed", True),
            revision_iterations=result.get("revision_iterations", 0),
            training_eligible=result.get("training_eligible", False),
            cot_trace=result.get("cot_trace", []), total_latency_ms=latency_ms,
            total_tokens=result.get("total_tokens", 0),
            models_used=result.get("models_used", []), error=result.get("error"),
        )
    except Exception as exc:
        logger.error("[API] Failed: %s", exc, exc_info=True)
        return AnswerResponse(
            session_id=request.session_id, question=request.question,
            answer="Error generating answer.", error=str(exc),
            total_latency_ms=(time.monotonic() - t0) * 1000,
        )


@router.post("/answer/stream")
async def generate_answer_stream(request: AnswerRequest):
    """Stream answer generation via Server-Sent Events."""
    import json as _json
    
    async def event_generator():
        state = _build_initial_state(request)
        try:
            yield f"data: {_json.dumps({'event': 'started', 'session_id': request.session_id})}\n\n"
            async for chunk in _get_graph().astream(state):
                yield f"data: {_json.dumps({'event': 'node.update', 'data': str(chunk)})}\n\n"
            yield f"data: {_json.dumps({'event': 'completed'})}\n\n"
        except Exception as exc:
            yield f"data: {_json.dumps({'event': 'error', 'error': str(exc)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
