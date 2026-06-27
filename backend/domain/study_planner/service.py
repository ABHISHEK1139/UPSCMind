"""
Study Planner Service
═══════════════════════════════════════════════════════════════
Generates personalized daily study plans based on student profile,
weak topics, revision schedule, and available time.
"""

from __future__ import annotations

import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class StudyPlannerService:
    """Generates personalized UPSC study plans."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_daily_plan(
        self,
        student_id: str,
        available_hours: float = 6.0,
        exam_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate today's study plan for a student."""
        
        # Calculate days until exam
        days_until_exam = 180  # default
        if exam_date:
            try:
                exam_dt = datetime.fromisoformat(exam_date)
                if exam_dt.tzinfo is None:
                    exam_dt = exam_dt.replace(tzinfo=timezone.utc)
                days_until_exam = max(1, (exam_dt - datetime.now(timezone.utc)).days)
            except ValueError:
                pass

        # Determine phase based on days until exam
        if days_until_exam <= 30:
            phase = "revision"
            revision_pct = 0.5
            new_topic_pct = 0.2
            practice_pct = 0.3
        elif days_until_exam <= 90:
            phase = "consolidation"
            revision_pct = 0.3
            new_topic_pct = 0.4
            practice_pct = 0.3
        else:
            phase = "foundation"
            revision_pct = 0.15
            new_topic_pct = 0.55
            practice_pct = 0.3

        # Build time allocation
        revision_hours = round(available_hours * revision_pct, 1)
        new_topic_hours = round(available_hours * new_topic_pct, 1)
        practice_hours = round(available_hours * practice_pct, 1)

        # Generate tasks with deterministic IDs
        tasks = []
        task_num = 1
        
        # Morning: Current Affairs (always 30 min)
        tasks.append({
            "id": f"task-{task_num:04d}",
            "title": "Current Affairs",
            "description": "Read newspaper + PIB summaries",
            "subject": "Current Affairs",
            "duration_minutes": 30,
            "priority": "high",
            "type": "reading",
            "time_slot": "morning",
        })
        task_num += 1
        remaining_hours = available_hours - 0.5

        # Allocate revision time
        if revision_hours > 0:
            tasks.append({
                "id": f"task-{task_num:04d}",
                "title": "Revision Block",
                "description": "Revise weak topics (spaced repetition)",
                "subject": "Revision",
                "duration_minutes": int(revision_hours * 60),
                "priority": "high",
                "type": "revision",
                "time_slot": "morning" if remaining_hours > 4 else "afternoon",
            })
            task_num += 1

        # Allocate new topic time
        if new_topic_hours > 0:
            # Split into 2 subjects
            subject_time = int(new_topic_hours * 60 / 2)
            tasks.append({
                "id": f"task-{task_num:04d}",
                "title": "GS2 Study",
                "description": "New topic coverage - GS2",
                "subject": "GS2",
                "duration_minutes": subject_time,
                "priority": "medium",
                "type": "reading",
                "time_slot": "afternoon",
            })
            task_num += 1
            tasks.append({
                "id": f"task-{task_num:04d}",
                "title": "GS3 Study",
                "description": "New topic coverage - GS3",
                "subject": "GS3",
                "duration_minutes": subject_time,
                "priority": "medium",
                "type": "reading",
                "time_slot": "afternoon",
            })
            task_num += 1

        # Allocate practice time
        if practice_hours > 0:
            tasks.append({
                "id": f"task-{task_num:04d}",
                "title": "Answer Writing Practice",
                "description": "Write 1-2 answers and self-evaluate",
                "subject": "Practice",
                "duration_minutes": int(practice_hours * 60) if practice_hours < 1 else 30,
                "priority": "high",
                "type": "practice",
                "time_slot": "evening",
            })
            task_num += 1

        # Evening: Quick review (always 15 min)
        tasks.append({
            "id": f"task-{task_num:04d}",
            "title": "Evening Review",
            "description": "Quick review of today's study + flashcards",
            "subject": "Review",
            "duration_minutes": 15,
            "priority": "medium",
            "type": "review",
            "time_slot": "evening",
        })

        total_minutes = sum(t["duration_minutes"] for t in tasks)

        # Persist to database
        try:
            from domain.students.models import StudyPlan
            plan = StudyPlan(
                student_id=student_id,
                date=datetime.now(timezone.utc),
                phase=phase,
                tasks=tasks,
                total_minutes=total_minutes,
            )
            self.db.add(plan)
            await self.db.flush()
        except Exception as exc:
            logger.warning("[PLAN] Failed to persist plan: %s", exc)

        # Publish event
        try:
            from core.event_manager import publish, ANSWER_GENERATED
            await publish("hermes.study_plan_generated", {
                "student_id": student_id,
                "phase": phase,
                "total_minutes": total_minutes,
            })
        except Exception:
            pass

        return {
            "student_id": student_id,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "phase": phase,
            "days_until_exam": days_until_exam,
            "total_study_minutes": total_minutes,
            "total_study_hours": round(total_minutes / 60, 1),
            "available_hours": available_hours,
            "tasks": tasks,
            "summary": {
                "current_affairs": "30 min",
                "revision": f"{revision_hours}h",
                "new_topics": f"{new_topic_hours}h",
                "practice": f"{practice_hours}h",
                "review": "15 min",
            },
            "tips": self._get_daily_tips(phase),
        }

    def _get_daily_tips(self, phase: str) -> List[str]:
        """Get phase-specific study tips."""
        tips = {
            "foundation": [
                "Focus on understanding concepts, not memorizing",
                "Make concise notes for quick revision later",
                "Link current affairs to static topics",
                "Aim for 80% syllabus coverage by day 90",
            ],
            "consolidation": [
                "Start connecting GS papers (e.g., GS2 + GS3 overlap)",
                "Practice answer writing daily",
                "Revise weak topics identified in mocks",
                "Focus on PYQ patterns",
            ],
            "revision": [
                "No new topics — only revise what you've covered",
                "Take at least 1 full-length mock per week",
                "Focus on presentation and time management",
                "Review and improve your model answers",
            ],
        }
        return tips.get(phase, [])
