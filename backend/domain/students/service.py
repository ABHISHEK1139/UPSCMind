"""
Student Service
═══════════════════════════════════════════════════════════════
Handles student registration, authentication, profile management,
progress tracking, and topic mastery.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import bcrypt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.students.models import (
    Base, Student, StudentPreference, StudentProgress, Topic,
    StudentCreate, StudentUpdate, StudentProfile, TopicMasteryOut, ProgressOut,
)
from api.security import create_token, sanitize_input, sanitize_email, validate_password

logger = logging.getLogger(__name__)

# ── Password Hashing ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


# ── Student Service ─────────────────────────────────────────────────────────

class StudentService:
    """Service layer for student operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Registration ──────────────────────────────────────────────────────

    async def create_student(self, data: StudentCreate) -> Student:
        """Register a new student."""
        # Sanitize and validate
        email = sanitize_email(data.email)
        name = sanitize_input(data.name, max_length=255)
        validate_password(data.password)

        # Check if email exists
        existing = await self.db.execute(
            select(Student).where(Student.email == email)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        student = Student(
            id=uuid.uuid4(),
            email=email,
            name=name,
            hashed_password=hash_password(data.password),
            exam_year=data.exam_year,
            optional_subject=data.optional_subject,
            daily_study_hours=data.daily_study_hours,
        )
        self.db.add(student)

        # Create default preferences
        preferences = StudentPreference(
            student_id=student.id,
        )
        self.db.add(preferences)

        # Create initial progress
        progress = StudentProgress(
            student_id=student.id,
        )
        self.db.add(progress)

        await self.db.flush()
        logger.info(f"[STUDENT] Created student: {student.email}")
        return student

    # ── Authentication ────────────────────────────────────────────────────

    async def authenticate(self, email: str, password: str) -> Optional[dict]:
        """Authenticate student and return student + JWT token."""
        email = sanitize_email(email)
        result = await self.db.execute(
            select(Student).where(Student.email == email)
        )
        student = result.scalar_one_or_none()

        if not student or not verify_password(password, student.hashed_password):
            return None

        # Update last login
        student.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Generate JWT token
        token = create_token(str(student.id), student.email)
        return {
            "student": student,
            "token": token,
        }

    # ── Profile ───────────────────────────────────────────────────────────

    async def get_profile(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Get complete student profile with progress."""
        result = await self.db.execute(
            select(Student)
            .options(selectinload(Student.preferences).selectinload(Student.progress))
            .where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            return None

        progress_data = {}
        if student.progress:
            p = student.progress
            progress_data = {
                "gs1_score": p.gs1_score,
                "gs2_score": p.gs2_score,
                "gs3_score": p.gs3_score,
                "gs4_score": p.gs4_score,
                "essay_score": p.essay_score,
                "overall_score": p.overall_score,
                "total_questions_attempted": p.total_questions_attempted,
                "total_answers_written": p.total_answers_written,
                "current_streak": p.current_streak,
                "longest_streak": p.longest_streak,
                "total_study_hours": p.total_study_hours,
            }

        return {
            "id": str(student.id),
            "email": student.email,
            "name": student.name,
            "exam_year": student.exam_year,
            "optional_subject": student.optional_subject,
            "daily_study_hours": student.daily_study_hours,
            "current_level": student.current_level,
            "created_at": student.created_at.isoformat() if student.created_at else None,
            "progress": progress_data,
        }

    async def update_profile(self, student_id: str, data: StudentUpdate) -> Optional[Student]:
        """Update student profile."""
        result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")

        update_data = data.model_dump(exclude_unset=True)
        # Sanitize string fields
        if "name" in update_data and update_data["name"]:
            update_data["name"] = sanitize_input(update_data["name"], max_length=255)
        for field, value in update_data.items():
            setattr(student, field, value)

        student.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return student

    # ── Topic Mastery ─────────────────────────────────────────────────────

    async def get_topic_mastery(self, student_id: str) -> List[Dict[str, Any]]:
        """Get topic mastery for a student."""
        result = await self.db.execute(
            select(Topic, student_topic_mastery.c.mastery_score)
            .outerjoin(
                student_topic_mastery,
                (Topic.id == student_topic_mastery.c.topic_id) &
                (student_topic_mastery.c.student_id == student_id)
            )
            .order_by(Topic.subject, Topic.name)
        )

        topics = []
        for topic, mastery in result.all():
            topics.append({
                "topic_id": str(topic.id),
                "topic_name": topic.name,
                "subject": topic.subject,
                "sub_subject": topic.sub_subject,
                "mastery_score": mastery or 0.0,
                "difficulty_level": topic.difficulty_level,
                "upsc_weightage": topic.upsc_weightage,
            })

        return topics

    async def update_topic_mastery(
        self, student_id: str, topic_id: str, score: float
    ) -> None:
        """Update topic mastery after answer evaluation."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(student_topic_mastery).values(
            student_id=student_id,
            topic_id=topic_id,
            mastery_score=score,
            questions_attempted=1,
            average_score=score,
            last_revision_at=datetime.now(timezone.utc),
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["student_id", "topic_id"],
            set_={
                "mastery_score": stmt.excluded.mastery_score,
                "questions_attempted": student_topic_mastery.c.questions_attempted + 1,
                "average_score": (
                    (student_topic_mastery.c.average_score * student_topic_mastery.c.questions_attempted + score)
                    / (student_topic_mastery.c.questions_attempted + 1)
                ),
                "last_revision_at": datetime.now(timezone.utc),
            }
        )

        await self.db.execute(stmt)

    # ── Progress ──────────────────────────────────────────────────────────

    async def get_progress(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Get student progress."""
        result = await self.db.execute(
            select(StudentProgress).where(StudentProgress.student_id == student_id)
        )
        progress = result.scalar_one_or_none()
        if not progress:
            return None

        return {
            "gs1_score": progress.gs1_score,
            "gs2_score": progress.gs2_score,
            "gs3_score": progress.gs3_score,
            "gs4_score": progress.gs4_score,
            "essay_score": progress.essay_score,
            "overall_score": progress.overall_score,
            "total_questions_attempted": progress.total_questions_attempted,
            "total_answers_written": progress.total_answers_written,
            "total_mock_tests": progress.total_mock_tests,
            "total_revisions": progress.total_revisions,
            "total_study_hours": progress.total_study_hours,
            "current_streak": progress.current_streak,
            "longest_streak": progress.longest_streak,
            "last_activity_at": progress.last_activity_at.isoformat() if progress.last_activity_at else None,
        }

    async def update_progress(self, student_id: str, subject: str, score: float) -> None:
        """Update progress after evaluation."""
        result = await self.db.execute(
            select(StudentProgress).where(StudentProgress.student_id == student_id)
        )
        progress = result.scalar_one_or_none()

        if not progress:
            progress = StudentProgress(student_id=student_id)
            self.db.add(progress)

        # Update subject score
        subject_field = f"{subject.lower()}_score"
        if hasattr(progress, subject_field):
            current = getattr(progress, subject_field) or 0.0
            # Weighted average (70% historical, 30% new)
            setattr(progress, subject_field, current * 0.7 + score * 0.3)

        # Update overall score
        scores = [
            progress.gs1_score, progress.gs2_score,
            progress.gs3_score, progress.gs4_score
        ]
        valid_scores = [s for s in scores if s > 0]
        if valid_scores:
            progress.overall_score = sum(valid_scores) / len(valid_scores)

        progress.total_answers_written += 1
        progress.last_activity_at = datetime.now(timezone.utc)
        await self.db.flush()
