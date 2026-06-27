"""
Student Intelligence Layer
═══════════════════════════════════════════════════════════════
Builds a comprehensive student profile that influences:
- Answer generation (difficulty, examples, current affairs)
- Study planning (weak topics, time allocation)
- Question selection (adaptive difficulty)
- Revision scheduling (personalized intervals)

This is the "brain" that knows the student.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StudentIntelligence:
    """
    Builds and maintains a student intelligence profile.

    The profile includes:
    - Weak areas (topics with low mastery)
    - Strong areas (topics with high mastery)
    - Learning style (based on performance patterns)
    - Study patterns (time of day, session length)
    - Exam readiness (overall score trajectory)
    - Personalized recommendations
    """

    def __init__(self, db):
        self.db = db

    async def get_intelligence_profile(self, student_id: str) -> Dict[str, Any]:
        """
        Build comprehensive student intelligence profile.

        Returns:
            Dict with weak_areas, strong_areas, learning_style,
            study_patterns, exam_readiness, recommendations
        """
        from domain.students.models import Student, StudentProgress, StudentTopicMastery
        from sqlalchemy import select

        # Get student
        result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            return self._default_profile()

        # Get progress
        progress_result = await self.db.execute(
            select(StudentProgress).where(StudentProgress.student_id == student_id)
        )
        progress = progress_result.scalar_one_or_none()

        # Get topic mastery
        mastery_result = await self.db.execute(
            select(StudentTopicMastery).where(
                StudentTopicMastery.student_id == student_id
            )
        )
        topics = mastery_result.scalars().all()

        # Build profile
        weak_areas = []
        strong_areas = []
        learning_gaps = []

        for topic in topics:
            topic_data = {
                "topic": topic.topic_name,
                "state": topic.state,
                "score": topic.score,
                "questions_attempted": topic.questions_attempted,
            }

            if topic.score < 40 or topic.state in ("NOT_STARTED", "LEARNING"):
                weak_areas.append(topic_data)
            elif topic.score >= 75 and topic.state in ("MASTERED", "PRACTICED"):
                strong_areas.append(topic_data)
            elif topic.state == "REVISION_DUE":
                learning_gaps.append(topic_data)

        # Calculate exam readiness
        exam_readiness = self._calculate_exam_readiness(progress, topics)

        # Determine learning style
        learning_style = self._determine_learning_style(topics)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            weak_areas, strong_areas, learning_gaps, exam_readiness, student
        )

        return {
            "student_id": student_id,
            "exam_year": student.exam_year,
            "current_level": student.current_level,
            "overall_score": progress.overall_score if progress else 0.0,
            "subject_scores": {
                "gs1": progress.gs1_score if progress else 0.0,
                "gs2": progress.gs2_score if progress else 0.0,
                "gs3": progress.gs3_score if progress else 0.0,
                "gs4": progress.gs4_score if progress else 0.0,
            },
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "learning_gaps": learning_gaps,
            "exam_readiness": exam_readiness,
            "learning_style": learning_style,
            "recommendations": recommendations,
            "total_questions_attempted": progress.total_questions_attempted if progress else 0,
            "current_streak": progress.current_streak if progress else 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _calculate_exam_readiness(
        self, progress: Any, topics: list
    ) -> Dict[str, Any]:
        """Calculate exam readiness score."""
        if not progress:
            return {"score": 0, "level": "not_started", "ready": False}

        overall = progress.overall_score or 0.0
        total_topics = len(topics)
        mastered = sum(1 for t in topics if t.state == "MASTERED")

        if overall >= 75 and mastered >= total_topics * 0.7:
            level = "exam_ready"
            ready = True
        elif overall >= 60 and mastered >= total_topics * 0.5:
            level = "approaching_ready"
            ready = False
        elif overall >= 40:
            level = "needs_work"
            ready = False
        else:
            level = "beginner"
            ready = False

        return {
            "score": round(overall, 1),
            "level": level,
            "ready": ready,
            "mastered_topics": mastered,
            "total_topics": total_topics,
            "mastery_percentage": round(mastered / max(total_topics, 1) * 100, 1),
        }

    def _determine_learning_style(self, topics: list) -> Dict[str, Any]:
        """Determine student's learning style from performance patterns."""
        if not topics:
            return {"style": "unknown", "confidence": 0}

        avg_score = sum(t.score for t in topics) / len(topics)
        score_variance = sum((t.score - avg_score) ** 2 for t in topics) / len(topics)

        # High variance = inconsistent learner
        # Low variance = consistent learner
        if score_variance > 400:
            style = "inconsistent"
            description = "Performance varies significantly across topics. Focus on weak areas."
        elif avg_score >= 70:
            style = "strong"
            description = "Consistently strong performance. Can handle higher difficulty."
        elif avg_score >= 50:
            style = "steady"
            description = "Steady progress. Regular revision recommended."
        else:
            style = "developing"
            description = "Building foundation. Start with easier topics."

        return {
            "style": style,
            "description": description,
            "avg_score": round(avg_score, 1),
            "variance": round(score_variance, 1),
            "confidence": min(len(topics) / 10, 1.0),
        }

    def _generate_recommendations(
        self,
        weak_areas: list,
        strong_areas: list,
        learning_gaps: list,
        exam_readiness: dict,
        student: Any,
    ) -> List[str]:
        """Generate personalized recommendations."""
        recommendations = []

        # Weak areas
        if weak_areas:
            topic_names = [a["topic"] for a in weak_areas[:3]]
            recommendations.append(
                f"Focus on weak topics: {', '.join(topic_names)}"
            )

        # Learning gaps (revision due)
        if learning_gaps:
            recommendations.append(
                f"Complete {len(learning_gaps)} overdue revisions"
            )

        # Exam readiness
        if exam_readiness["level"] == "beginner":
            recommendations.append(
                "Start with foundation topics. Aim for 2 hours daily study."
            )
        elif exam_readiness["level"] == "needs_work":
            recommendations.append(
                "Increase practice frequency. Focus on GS2 and GS3."
            )
        elif exam_readiness["level"] == "approaching_ready":
            recommendations.append(
                "Take more mock tests. Review weak areas weekly."
            )
        elif exam_readiness["level"] == "exam_ready":
            recommendations.append(
                "Maintain momentum. Focus on current affairs and essay practice."
            )

        # Study hours
        if student and student.daily_study_hours < 4:
            recommendations.append(
                f"Increase daily study hours from {student.daily_study_hours}h to 4h+"
            )

        return recommendations

    def _default_profile(self) -> Dict[str, Any]:
        """Return default profile for new students."""
        return {
            "student_id": None,
            "exam_year": None,
            "current_level": "beginner",
            "overall_score": 0.0,
            "subject_scores": {"gs1": 0, "gs2": 0, "gs3": 0, "gs4": 0},
            "weak_areas": [],
            "strong_areas": [],
            "learning_gaps": [],
            "exam_readiness": {"score": 0, "level": "not_started", "ready": False},
            "learning_style": {"style": "unknown", "confidence": 0},
            "recommendations": ["Complete your profile", "Take a diagnostic test"],
            "total_questions_attempted": 0,
            "current_streak": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
