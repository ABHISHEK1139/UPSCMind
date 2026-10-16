"""
Hermes V2 — Feedback Routes
═══════════════════════════════════════════════════════════════
API endpoints for collecting user feedback on generated answers.
Feedback is stored and used to improve the training data flywheel.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from core.database import get_db
from domain.feedback.models import Feedback

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request/Response Models ──────────────────────────────────────────

class FeedbackRequest(BaseModel):
    session_id: str = Field(..., description="The session ID of the answer")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 (poor) to 5 (excellent)")
    corrections: Optional[str] = Field(None, description="User-provided corrections")
    comments: Optional[str] = Field(None, description="Additional comments")
    domain: Optional[str] = Field(None, description="Domain of the question")


class FeedbackResponse(BaseModel):
    status: str
    message: str
    feedback_id: str


# ── In-memory store (fallback only if the database write fails) ─────────

_feedback_store: List[Dict[str, Any]] = []


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest, db=Depends(get_db)
) -> FeedbackResponse:
    """Submit feedback for a generated answer (persisted to the database)."""
    import uuid

    feedback_id = str(uuid.uuid4())
    record = {
        "id": feedback_id,
        "session_id": request.session_id,
        "rating": request.rating,
        "corrections": request.corrections,
        "comments": request.comments,
        "domain": request.domain,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist durably; keep the in-memory store only as a fallback
    try:
        db.add(Feedback(
            id=feedback_id,
            session_id=request.session_id,
            rating=request.rating,
            corrections=request.corrections,
            comments=request.comments,
            domain=request.domain,
        ))
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.warning("[FEEDBACK] DB write failed, using in-memory fallback: %s", exc)
        _feedback_store.append(record)

    # Also update the trajectory record if it exists
    try:
        _update_trajectory_feedback(request.session_id, request.rating, request.corrections)
    except Exception as exc:
        logger.warning("[FEEDBACK] Could not update trajectory: %s", exc)

    logger.info(
        "[FEEDBACK] Received: session=%s rating=%d",
        request.session_id,
        request.rating,
    )

    return FeedbackResponse(
        status="ok",
        message="Feedback recorded. Thank you!",
        feedback_id=feedback_id,
    )


@router.get("/feedback/{session_id}")
async def get_feedback(session_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get feedback for a specific session."""
    result = await db.execute(
        select(Feedback).where(Feedback.session_id == session_id)
    )
    feedbacks = [
        {
            "id": f.id,
            "session_id": f.session_id,
            "rating": f.rating,
            "corrections": f.corrections,
            "comments": f.comments,
            "domain": f.domain,
            "collected_at": f.collected_at.isoformat() if f.collected_at else None,
        }
        for f in result.scalars().all()
    ]
    # Include any records held in the in-memory fallback store
    feedbacks.extend(f for f in _feedback_store if f["session_id"] == session_id)
    return {"session_id": session_id, "feedbacks": feedbacks}


@router.get("/feedback/stats/summary")
async def feedback_summary(db=Depends(get_db)) -> Dict[str, Any]:
    """Get summary statistics of all feedback."""
    result = await db.execute(select(Feedback.rating, Feedback.domain))
    rows = result.all()
    records = [{"rating": r, "domain": d} for r, d in rows]
    records.extend(_feedback_store)

    if not records:
        return {"total": 0, "avg_rating": 0, "by_domain": {}}

    ratings = [f["rating"] for f in records]
    by_domain: Dict[str, int] = {}
    for f in records:
        domain = f.get("domain") or "unknown"
        by_domain[domain] = by_domain.get(domain, 0) + 1

    return {
        "total": len(records),
        "avg_rating": sum(ratings) / len(ratings),
        "rating_distribution": {str(i): ratings.count(i) for i in range(1, 6)},
        "by_domain": by_domain,
    }


def _update_trajectory_feedback(
    session_id: str, rating: int, corrections: Optional[str]
) -> None:
    """Update the trajectory record with user feedback."""
    import json
    from pathlib import Path

    trajectory_file = Path("dataset/training_data/trajectories.jsonl")
    if not trajectory_file.exists():
        return

    # Read all lines
    lines = trajectory_file.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []

    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if record.get("feedback", {}).get("session_id") == session_id:
                record["feedback"] = {
                    "rating": rating,
                    "corrections": corrections,
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                }
                updated = True
            new_lines.append(json.dumps(record, ensure_ascii=False, default=str))
        except json.JSONDecodeError:
            new_lines.append(line)

    if updated:
        trajectory_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
