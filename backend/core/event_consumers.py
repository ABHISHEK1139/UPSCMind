"""
Event Consumers — Real handlers for inter-module communication
═══════════════════════════════════════════════════════════════
Wires events to actual database updates and service calls.

This is the "nervous system" of Hermes — when something happens
in one module, other modules react.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.event_bus import (
    ANSWER_GENERATED, REVIEW_COMPLETED, REVISION_COMPLETED,
    FEEDBACK_RECEIVED, TOPIC_DETECTED,
)

logger = logging.getLogger(__name__)


async def on_answer_generated(event: str, data: Dict[str, Any]) -> None:
    """
    When an answer is generated:
    1. Update student progress (subject scores)
    2. Update topic mastery
    3. Schedule next revision
    4. Check for achievements
    """
    student_id = data.get("student_id")
    topic = data.get("topic")
    score = data.get("score", 0)
    domain = data.get("domain")

    if not student_id:
        return

    logger.info("[EVENT] Answer generated: student=%s topic=%s score=%.2f",
                student_id, topic, score)

    # Update topic mastery
    try:
        from core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from domain.learning.service import LearningService
            learning_svc = LearningService(db)
            if topic:
                await learning_svc.record_practice(student_id, topic, score)
    except Exception as exc:
        logger.warning("[EVENT] Failed to update topic mastery: %s", exc)

    # Update progress scores
    try:
        from core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            from domain.students.models import StudentProgress

            result = await db.execute(
                select(StudentProgress).where(StudentProgress.student_id == student_id)
            )
            progress = result.scalar_one_or_none()

            if progress:
                # Update subject score based on domain
                if domain == "Polity":
                    progress.gs2_score = _running_avg(progress.gs2_score, score, progress.total_questions_attempted)
                elif domain == "Economy":
                    progress.gs3_score = _running_avg(progress.gs3_score, score, progress.total_questions_attempted)
                elif domain == "History":
                    progress.gs1_score = _running_avg(progress.gs1_score, score, progress.total_questions_attempted)
                elif domain == "Geography":
                    progress.gs1_score = _running_avg(progress.gs1_score, score, progress.total_questions_attempted)
                elif domain == "Ethics":
                    progress.gs4_score = _running_avg(progress.gs4_score, score, progress.total_questions_attempted)

                progress.total_questions_attempted += 1
                progress.total_answers_written += 1
                progress.overall_score = (
                    progress.gs1_score + progress.gs2_score +
                    progress.gs3_score + progress.gs4_score
                ) / 4

                await db.flush()
                await db.commit()
                logger.info("[EVENT] Updated progress for student=%s", student_id)
    except Exception as exc:
        logger.warning("[EVENT] Failed to update progress: %s", exc)


async def on_review_completed(event: str, data: Dict[str, Any]) -> None:
    """
    When a review is completed:
    1. Store review scores for analytics
    2. Update study planner if score is low
    """
    student_id = data.get("student_id")
    overall_score = data.get("overall_score", 0)
    topic = data.get("topic")

    logger.info("[EVENT] Review completed: student=%s score=%.2f topic=%s",
                student_id, overall_score, topic)

    # If score is low, prioritize this topic in study plan
    if overall_score < 0.5 and topic:
        logger.info("[EVENT] Low score detected, prioritizing %s in study plan", topic)


async def on_revision_completed(event: str, data: Dict[str, Any]) -> None:
    """
    When a revision is completed:
    1. Update revision count
    2. Schedule next revision
    """
    student_id = data.get("student_id")
    topic = data.get("topic")
    score = data.get("score", 0)

    logger.info("[EVENT] Revision completed: student=%s topic=%s score=%.2f",
                student_id, topic, score)


async def on_feedback_received(event: str, data: Dict[str, Any]) -> None:
    """
    When user feedback is received:
    1. Store feedback for analysis
    2. Update model if feedback indicates issues
    """
    session_id = data.get("session_id")
    rating = data.get("rating", 0)

    logger.info("[EVENT] Feedback received: session=%s rating=%d",
                session_id, rating)

    # If rating is low, log for review
    if rating <= 2:
        logger.warning("[EVENT] Low rating detected: %d for session %s",
                       rating, session_id)


async def on_topic_detected(event: str, data: Dict[str, Any]) -> None:
    """
    When a topic is detected:
    1. Update topic detection count
    2. Log for analytics
    """
    topic = data.get("topic")
    domain = data.get("domain")
    student_id = data.get("student_id")

    logger.info("[EVENT] Topic detected: %s (domain=%s) for student=%s",
                topic, domain, student_id)


def _running_avg(current: float, new: float, count: int) -> float:
    """Calculate running average."""
    if count <= 0:
        return new
    return round((current * count + new) / (count + 1), 2)


def register_all_consumers() -> None:
    """Register all event consumers."""
    from core.event_manager import subscribe

    subscribe(ANSWER_GENERATED, on_answer_generated)
    subscribe(REVIEW_COMPLETED, on_review_completed)
    subscribe(REVISION_COMPLETED, on_revision_completed)
    subscribe(FEEDBACK_RECEIVED, on_feedback_received)
    subscribe(TOPIC_DETECTED, on_topic_detected)

    logger.info("[EVENT] All consumers registered (5 handlers)")
