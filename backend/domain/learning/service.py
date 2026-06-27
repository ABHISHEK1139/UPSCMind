"""
Learning Engine Service
═══════════════════════════════════════════════════════════════
Manages the learning lifecycle for UPSC topics.
Handles topic mastery tracking, state transitions, and
personalized content recommendations.

State Machine:
  NOT_STARTED → LEARNING → PRACTICED → MASTERED → REVISION_DUE → MASTERED
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.event_bus import (
    EventBus, ANSWER_GENERATED, FEEDBACK_RECEIVED,
    TOPIC_DETECTED, RETRIEVAL_COMPLETED,
)

logger = logging.getLogger(__name__)

# ── Topic States ────────────────────────────────────────────────────────────

TOPIC_STATES = [
    "NOT_STARTED",
    "LEARNING",
    "PRACTICED",
    "MASTERED",
    "REVISION_DUE",
]

# State transitions
VALID_TRANSITIONS = {
    "NOT_STARTED": ["LEARNING"],
    "LEARNING": ["PRACTICED", "NOT_STARTED"],
    "PRACTICED": ["MASTERED", "LEARNING"],
    "MASTERED": ["REVISION_DUE"],
    "REVISION_DUE": ["MASTERED", "LEARNING"],
}

# Thresholds
MASTERED_THRESHOLD = 80.0
PRACTICED_THRESHOLD = 60.0


class LearningService:
    """Manages topic learning lifecycle and mastery tracking."""

    def __init__(self, db: AsyncSession, event_bus: Optional[EventBus] = None):
        self.db = db
        self.event_bus = event_bus

    async def get_topic_status(
        self, student_id: str, topic: str
    ) -> Dict[str, Any]:
        """Get current learning status of a topic for a student."""
        from domain.students.models import StudentTopicMastery

        result = await self.db.execute(
            select(StudentTopicMastery).where(
                and_(
                    StudentTopicMastery.student_id == student_id,
                    StudentTopicMastery.topic_name == topic,
                )
            )
        )
        mastery = result.scalar_one_or_none()

        if not mastery:
            return {
                "student_id": student_id,
                "topic": topic,
                "state": "NOT_STARTED",
                "score": 0.0,
                "questions_attempted": 0,
                "last_practiced": None,
                "next_revision": None,
                "total_revisions": 0,
            }

        return {
            "student_id": student_id,
            "topic": topic,
            "state": mastery.state,
            "score": mastery.score,
            "questions_attempted": mastery.questions_attempted,
            "last_practiced": mastery.last_practiced.isoformat() if mastery.last_practiced else None,
            "next_revision": mastery.next_revision.isoformat() if mastery.next_revision else None,
            "total_revisions": mastery.total_revisions,
        }

    async def start_learning(
        self, student_id: str, topic: str
    ) -> Dict[str, Any]:
        """Mark a topic as being actively learned."""
        from domain.students.models import StudentTopicMastery

        result = await self.db.execute(
            select(StudentTopicMastery).where(
                and_(
                    StudentTopicMastery.student_id == student_id,
                    StudentTopicMastery.topic_name == topic,
                )
            )
        )
        mastery = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if not mastery:
            mastery = StudentTopicMastery(
                student_id=student_id,
                topic_name=topic,
                state="LEARNING",
                score=0.0,
                questions_attempted=0,
                last_practiced=now,
                total_revisions=0,
            )
            self.db.add(mastery)
        elif mastery.state == "NOT_STARTED":
            mastery.state = "LEARNING"
            mastery.last_practiced = now

        await self.db.flush()

        if self.event_bus:
            await self.event_bus.publish(TOPIC_DETECTED, {
                "student_id": student_id,
                "topic": topic,
                "state": "LEARNING",
            })

        return await self.get_topic_status(student_id, topic)

    async def record_practice(
        self,
        student_id: str,
        topic: str,
        score: float,
        question_type: str = "analytical",
    ) -> Dict[str, Any]:
        """Record a practice attempt and update topic state."""
        from domain.students.models import StudentTopicMastery

        result = await self.db.execute(
            select(StudentTopicMastery).where(
                and_(
                    StudentTopicMastery.student_id == student_id,
                    StudentTopicMastery.topic_name == topic,
                )
            )
        )
        mastery = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if not mastery:
            mastery = StudentTopicMastery(
                student_id=student_id,
                topic_name=topic,
                state="LEARNING",
                score=score,
                questions_attempted=1,
                last_practiced=now,
                total_revisions=0,
            )
            self.db.add(mastery)
        else:
            # Update running average
            total_attempts = mastery.questions_attempted + 1
            mastery.score = round(
                (mastery.score * mastery.questions_attempted + score) / total_attempts, 2
            )
            mastery.questions_attempted = total_attempts
            mastery.last_practiced = now

            # State transition
            if mastery.score >= MASTERY_THRESHOLD and total_attempts >= 3:
                mastery.state = "MASTERED"
                mastery.next_revision = now + timedelta(days=7)
                mastery.total_revisions += 1
            elif mastery.score >= PRACTICED_THRESHOLD:
                mastery.state = "PRACTICED"
            elif mastery.state == "NOT_STARTED":
                mastery.state = "LEARNING"

        await self.db.flush()

        # Publish event
        if self.event_bus:
            await self.event_bus.publish(ANSWER_GENERATED, {
                "student_id": student_id,
                "topic": topic,
                "score": score,
                "question_type": question_type,
                "new_state": mastery.state,
            })

        return await self.get_topic_status(student_id, topic)

    async def get_learning_progress(
        self, student_id: str
    ) -> Dict[str, Any]:
        """Get overall learning progress across all topics."""
        from domain.students.models import StudentTopicMastery

        result = await self.db.execute(
            select(StudentTopicMastery).where(
                StudentTopicMastery.student_id == student_id
            )
        )
        topics = result.scalars().all()

        total = len(topics)
        by_state = {}
        total_score = 0.0
        total_questions = 0

        for t in topics:
            by_state[t.state] = by_state.get(t.state, 0) + 1
            total_score += t.score
            total_questions += t.questions_attempted

        return {
            "student_id": student_id,
            "total_topics": total,
            "by_state": by_state,
            "average_score": round(total_score / total, 2) if total > 0 else 0.0,
            "total_questions_attempted": total_questions,
            "mastered_count": by_state.get("MASTERED", 0),
            "learning_count": by_state.get("LEARNING", 0),
            "practiced_count": by_state.get("PRACTICED", 0),
            "not_started_count": by_state.get("NOT_STARTED", 0),
            "revision_due_count": by_state.get("REVISION_DUE", 0),
        }

    async def get_recommended_topics(
        self, student_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get topics recommended for study based on current state."""
        from domain.students.models import StudentTopicMastery

        # Get all topics for student
        result = await self.db.execute(
            select(StudentTopicMastery).where(
                StudentTopicMastery.student_id == student_id
            )
        )
        topics = result.scalars().all()

        # Priority: REVISION_DUE > NOT_STARTED > LEARNING > PRACTICED
        priority_order = {
            "REVISION_DUE": 0,
            "NOT_STARTED": 1,
            "LEARNING": 2,
            "PRACTICED": 3,
            "MASTERED": 4,
        }

        sorted_topics = sorted(
            topics,
            key=lambda t: (priority_order.get(t.state, 5), -t.score)
        )

        recommendations = []
        for t in sorted_topics[:limit]:
            recommendations.append({
                "topic": t.topic_name,
                "state": t.state,
                "score": t.score,
                "questions_attempted": t.questions_attempted,
                "priority": "high" if t.state in ("REVISION_DUE", "NOT_STARTED") else "medium",
                "reason": self._get_recommendation_reason(t),
            })

        return recommendations

    def _get_recommendation_reason(self, topic: Any) -> str:
        """Generate human-readable recommendation reason."""
        if topic.state == "REVISION_DUE":
            return "Due for revision — spaced repetition interval reached"
        elif topic.state == "NOT_STARTED":
            return "New topic — start building foundation"
        elif topic.state == "LEARNING":
            return f"In progress — current score: {topic.score:.0f}%"
        elif topic.state == "PRACTICED":
            return f"Practice more to master — current: {topic.score:.0f}%"
        else:
            return "Maintained mastery — periodic revision recommended"
