"""
Student Domain Models
═══════════════════════════════════════════════════════════════
Defines database schema for student profiles, preferences,
progress tracking, and topic mastery.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer,
    String, Table, Text, JSON, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

# Use the shared Base from core.database
from core.database import Base


# ── Association Table (with extra columns for learning state) ─────────────

student_topic_mastery = Table(
    "student_topic_mastery",
    Base.metadata,
    Column("student_id", UUID(as_uuid=True), ForeignKey("students.id"), primary_key=True),
    Column("topic_id", UUID(as_uuid=True), ForeignKey("topics.id"), primary_key=True),
    Column("mastery_score", Float, default=0.0),
    Column("revision_count", Integer, default=0),
    Column("last_revision_at", DateTime(timezone=True), nullable=True),
    Column("next_revision_at", DateTime(timezone=True), nullable=True),
    Column("questions_attempted", Integer, default=0),
    Column("average_score", Float, default=0.0),
    Column("state", String(20), default="NOT_STARTED"),  # NOT_STARTED/LEARNING/PRACTICED/MASTERED/REVISION_DUE
)


# ── StudentTopicMastery ORM class for state tracking ───────────────────────

class StudentTopicMastery(Base):
    """Tracks per-topic learning state for each student."""
    __tablename__ = "student_topic_mastery_orm"

    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), primary_key=True)
    topic_name = Column(String(255), primary_key=True, index=True)
    state = Column(String(20), default="NOT_STARTED")
    score = Column(Float, default=0.0)
    questions_attempted = Column(Integer, default=0)
    last_practiced = Column(DateTime(timezone=True), nullable=True)
    next_revision = Column(DateTime(timezone=True), nullable=True)
    total_revisions = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ── Student Table ──────────────────────────────────────────────────────────

class Student(Base):
    """Student profile and learning state."""
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Exam details
    exam_year = Column(Integer, nullable=True)
    optional_subject = Column(String(100), nullable=True)
    target_attempt = Column(Integer, default=1)
    daily_study_hours = Column(Float, default=6.0)
    current_level = Column(String(50), default="beginner")  # beginner/intermediate/advanced
    
    # Profile metadata
    phone = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    college = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    preferences = relationship("StudentPreference", back_populates="student", uselist=False)
    progress = relationship("StudentProgress", back_populates="student", uselist=False)
    study_plans = relationship("StudyPlan", back_populates="student")
    notes = relationship("Note", back_populates="student")
    mock_tests = relationship("MockTestAttempt", back_populates="student")
    revisions = relationship("RevisionRecord", back_populates="student")
    topic_mastery = relationship("Topic", secondary=student_topic_mastery, back_populates="students")


# ── Student Preferences ────────────────────────────────────────────────────

class StudentPreference(Base):
    """Student preferences for personalized experience."""
    __tablename__ = "student_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), unique=True, nullable=False)
    
    # Notification preferences
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    daily_reminder_time = Column(String(5), default="08:00")  # HH:MM format
    
    # Study preferences
    preferred_study_time = Column(String(20), default="morning")  # morning/afternoon/evening/night
    answer_language = Column(String(10), default="english")  # english/hindi
    difficulty_level = Column(String(20), default="adaptive")  # easy/medium/hard/adaptive
    
    # Display preferences
    theme = Column(String(20), default="dark")  # light/dark
    compact_view = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    student = relationship("Student", back_populates="preferences")


# ── Student Progress ───────────────────────────────────────────────────────

class StudentProgress(Base):
    """Overall progress tracking per subject."""
    __tablename__ = "student_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), unique=True, nullable=False)
    
    # Subject-wise scores (0-100)
    gs1_score = Column(Float, default=0.0)
    gs2_score = Column(Float, default=0.0)
    gs3_score = Column(Float, default=0.0)
    gs4_score = Column(Float, default=0.0)
    essay_score = Column(Float, default=0.0)
    interview_score = Column(Float, default=0.0)
    optional_score = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)
    
    # Statistics
    total_questions_attempted = Column(Integer, default=0)
    total_answers_written = Column(Integer, default=0)
    total_mock_tests = Column(Integer, default=0)
    total_revisions = Column(Integer, default=0)
    total_study_hours = Column(Float, default=0.0)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    
    # Timestamps
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    student = relationship("Student", back_populates="progress")


# ── Topic Table ────────────────────────────────────────────────────────────

class Topic(Base):
    """UPSC syllabus topics with metadata."""
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False)  # e.g., "GS2-POLITY-FEDERALISM"
    subject = Column(String(50), nullable=False)  # GS1/GS2/GS3/GS4/Essay/Optional
    sub_subject = Column(String(100), nullable=True)  # e.g., "Polity", "Economy"
    description = Column(Text, nullable=True)
    parent_topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True)
    
    # Difficulty and weightage
    difficulty_level = Column(String(20), default="medium")  # easy/medium/hard
    upsc_weightage = Column(Float, default=0.0)  # 0-100, how frequently asked
    avg_marks = Column(Float, default=0.0)  # Average marks in past years
    
    # Syllabus mapping
    syllabus_section = Column(String(255), nullable=True)
    pyq_frequency = Column(Integer, default=0)  # Number of times asked in last 10 years
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    students = relationship("Student", secondary=student_topic_mastery, back_populates="topic_mastery")
    notes = relationship("Note", back_populates="topic")
    revisions = relationship("RevisionRecord", back_populates="topic")


# ── Pydantic Schemas (API I/O) ──────────────────────────────────────────────

class StudentCreate(BaseModel):
    email: str
    name: str
    password: str
    exam_year: Optional[int] = None
    optional_subject: Optional[str] = None
    daily_study_hours: float = 6.0


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    exam_year: Optional[int] = None
    optional_subject: Optional[str] = None
    daily_study_hours: Optional[float] = None
    current_level: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


# ── Study Plan Table ───────────────────────────────────────────────────────

class StudyPlan(Base):
    """Daily study plan for a student."""
    __tablename__ = "study_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False)
    phase = Column(String(20), default="foundation")  # foundation/consolidation/revision
    tasks = Column(JSON, default=list)  # List of task objects
    total_minutes = Column(Integer, default=360)
    completed_minutes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="study_plans")


# ── Note Table ─────────────────────────────────────────────────────────────

class Note(Base):
    """Student notes for topics."""
    __tablename__ = "notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    note_type = Column(String(50), default="structured")  # structured/brief/comprehensive
    source = Column(String(50), default="answer")  # answer/study/manual
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="notes")
    topic = relationship("Topic", back_populates="notes")


# ── Mock Test Attempt Table ────────────────────────────────────────────────

class MockTestAttempt(Base):
    """Mock test attempt record."""
    __tablename__ = "mock_test_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    paper = Column(String(10), nullable=False)  # GS1/GS2/GS3/GS4/Essay
    score = Column(Float, default=0.0)
    max_score = Column(Float, default=0.0)
    duration_minutes = Column(Integer, default=0)
    answers = Column(JSON, default=list)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    student = relationship("Student", back_populates="mock_tests")


# ── Revision Record Table ──────────────────────────────────────────────────

class RevisionRecord(Base):
    """Revision session record."""
    __tablename__ = "revision_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id"), nullable=True)
    topic_name = Column(String(255), nullable=False)
    score_before = Column(Float, default=0.0)
    score_after = Column(Float, default=0.0)
    revision_type = Column(String(50), default="spaced")  # spaced/urgent/first
    duration_minutes = Column(Integer, default=30)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    student = relationship("Student", back_populates="revisions")
    topic = relationship("Topic", back_populates="revisions")


class StudentProfile(BaseModel):
    id: str
    email: str
    name: str
    exam_year: Optional[int]
    optional_subject: Optional[str]
    daily_study_hours: float
    current_level: str
    overall_score: float
    current_streak: int
    total_study_hours: float
    created_at: str
    
    class Config:
        from_attributes = True


class TopicMasteryOut(BaseModel):
    topic_id: str
    topic_name: str
    subject: str
    mastery_score: float
    revision_count: int
    last_revision_at: Optional[str]
    next_revision_at: Optional[str]
    questions_attempted: int
    average_score: float


class ProgressOut(BaseModel):
    gs1_score: float
    gs2_score: float
    gs3_score: float
    gs4_score: float
    essay_score: float
    overall_score: float
    total_questions_attempted: int
    total_answers_written: int
    current_streak: int
    longest_streak: int
    last_activity_at: Optional[str]
