"""
Revision Engine Service
═══════════════════════════════════════════════════════════════
Spaced repetition system for UPSC topics.
Uses a simplified SM-2 algorithm for scheduling revisions.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Spaced Repetition Intervals (days) ──────────────────────────────────────

REVISION_INTERVALS = {
    0: 1,      # First revision: tomorrow
    1: 3,      # Second: 3 days
    2: 7,      # Third: 7 days
    3: 15,     # Fourth: 15 days
    4: 30,     # Fifth: 30 days
    5: 60,     # Sixth: 60 days (mastered)
}

# Mastery thresholds
MASTERY_THRESHOLD = 85  # Score above this = mastered
FORGETTING_THRESHOLD = 40  # Score below this = needs immediate revision


class RevisionService:
    """Manages spaced repetition scheduling for UPSC topics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_due_revisions(
        self, student_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get topics due for revision today."""
        now = datetime.now(timezone.utc)
        
        try:
            from domain.students.models import StudentTopicMastery, Topic
            result = await self.db.execute(
                select(Topic.name, Topic.subject, StudentTopicMastery.c.score)
                .join(StudentTopicMastery, Topic.id == StudentTopicMastery.c.topic_id)
                .where(StudentTopicMastery.c.student_id == student_id)
                .where(StudentTopicMastery.c.next_revision <= now)
                .where(StudentTopicMastery.c.state.in_(["REVISION_DUE", "MASTERED", "PRACTICED"]))
                .order_by(StudentTopicMastery.c.next_revision)
                .limit(limit)
            )
            return [
                {"topic": name, "subject": subject, "score": score}
                for name, subject, score in result.all()
            ]
        except Exception as exc:
            logger.warning("[REVISION] Failed to fetch due revisions: %s", exc)
            return []

    def calculate_next_revision(
        self,
        current_mastery: float,
        revision_count: int,
        last_score: float,
    ) -> Dict[str, Any]:
        """Calculate next revision date based on performance."""
        
        # If score is very low, schedule for tomorrow
        if last_score < FORGETTING_THRESHOLD:
            next_date = datetime.now(timezone.utc) + timedelta(days=1)
            interval = 1
            status = "urgent"
        # If mastered, use longest interval
        elif current_mastery >= MASTERY_THRESHOLD:
            interval = REVISION_INTERVALS.get(5, 60)
            next_date = datetime.now(timezone.utc) + timedelta(days=interval)
            status = "mastered"
        else:
            # Use revision count to determine interval
            interval = REVISION_INTERVALS.get(
                min(revision_count, 5),
                60
            )
            # Adjust based on score (lower score = shorter interval)
            if last_score < 60:
                interval = max(1, interval // 2)
            
            next_date = datetime.now(timezone.utc) + timedelta(days=interval)
            status = "learning"

        return {
            "next_revision_at": next_date.isoformat(),
            "interval_days": interval,
            "status": status,
            "mastery_score": current_mastery,
            "revision_count": revision_count,
        }

    async def get_revision_stats(self, student_id: str) -> Dict[str, Any]:
        """Get revision statistics for dashboard."""
        now = datetime.now(timezone.utc)
        week_from_now = now + timedelta(days=7)

        try:
            from domain.students.models import StudentTopicMastery
            from sqlalchemy import func

            result = await self.db.execute(
                select(
                    func.count().label("total"),
                    func.sum(func.case((StudentTopicMastery.c.state == "MASTERED", 1), else_=0)).label("mastered"),
                    func.sum(func.case((StudentTopicMastery.c.state == "LEARNING", 1), else_=0)).label("learning"),
                    func.sum(func.case((StudentTopicMastery.c.state == "NOT_STARTED", 1), else_=0)).label("not_started"),
                    func.sum(func.case((StudentTopicMastery.c.next_revision <= now, 1), else_=0)).label("due_today"),
                    func.sum(func.case((StudentTopicMastery.c.next_revision.between(now, week_from_now), 1), else_=0)).label("due_this_week"),
                    func.avg(StudentTopicMastery.c.score).label("avg_mastery"),
                ).where(StudentTopicMastery.c.student_id == student_id)
            )
            row = result.one()
            return {
                "due_today": row.due_today or 0,
                "due_this_week": row.due_this_week or 0,
                "overdue": row.due_today or 0,
                "mastered": row.mastered or 0,
                "learning": row.learning or 0,
                "not_started": row.not_started or 0,
                "total_topics": row.total or 0,
                "average_mastery": round(float(row.avg_mastery or 0), 2),
                "streak_days": 0,
                "last_revision_date": None,
            }
        except Exception as exc:
            logger.warning("[REVISION] Failed to fetch stats: %s", exc)
            return {
                "due_today": 0, "due_this_week": 0, "overdue": 0,
                "mastered": 0, "learning": 0, "not_started": 0,
                "total_topics": 0, "average_mastery": 0.0,
                "streak_days": 0, "last_revision_date": None,
            }

    def generate_revision_plan(
        self,
        topics: List[Dict[str, Any]],
        available_minutes: int = 60,
    ) -> List[Dict[str, Any]]:
        """Generate a revision session plan."""
        plan = []
        time_remaining = available_minutes

        # Sort by priority: urgent > learning > mastered
        priority_order = {"urgent": 0, "learning": 1, "mastered": 2}
        sorted_topics = sorted(
            topics,
            key=lambda t: priority_order.get(t.get("status", "learning"), 1)
        )

        for topic in sorted_topics:
            if time_remaining <= 0:
                break

            # Allocate time based on status
            if topic.get("status") == "urgent":
                minutes = min(15, time_remaining)
            elif topic.get("status") == "learning":
                minutes = min(10, time_remaining)
            else:
                minutes = min(5, time_remaining)

            plan.append({
                "topic_id": topic.get("id"),
                "topic_name": topic.get("name"),
                "subject": topic.get("subject"),
                "minutes": minutes,
                "status": topic.get("status"),
                "activity": self._get_activity(topic.get("status")),
            })

            time_remaining -= minutes

        return plan

    def _get_activity(self, status: str) -> str:
        """Get appropriate activity type based on status."""
        activities = {
            "urgent": "Quick review + 2 MCQs",
            "learning": "Read notes + 1 diagram",
            "mastered": "Flashcard review",
        }
        return activities.get(status, "Quick review")
