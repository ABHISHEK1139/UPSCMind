"""
Student API Routes (Enhanced)
═══════════════════════════════════════════════════════════════
REST APIs for student management, profile, progress, and analytics.
Uses real service layer with database integration.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.database import get_db

logger = __import__("logging").getLogger(__name__)

router = APIRouter()

# ── Request/Response Models ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    exam_year: Optional[int] = None
    optional_subject: Optional[str] = None
    daily_study_hours: float = 6.0


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    exam_year: Optional[int] = None
    optional_subject: Optional[str] = None
    daily_study_hours: Optional[float] = None
    current_level: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None


class AnswerSubmission(BaseModel):
    question_id: str
    question_text: str
    answer: str
    topic: str
    paper: str = "GS2"


class TopicUpdateRequest(BaseModel):
    topic: str
    score: float
    question_type: str = "analytical"


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db=Depends(get_db)) -> Dict[str, Any]:
    """Register a new student."""
    from domain.students.service import StudentService
    from domain.students.models import StudentCreate

    service = StudentService(db)
    try:
        student = await service.create_student(StudentCreate(
            email=data.email,
            name=data.name,
            password=data.password,
            exam_year=data.exam_year,
            optional_subject=data.optional_subject,
            daily_study_hours=data.daily_study_hours,
        ))
        return {
            "message": "Registration successful",
            "student_id": str(student.id),
            "next_steps": [
                "Complete your profile",
                "Take a diagnostic test",
                "Start your first study session",
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(data: LoginRequest, db=Depends(get_db)) -> Dict[str, Any]:
    """Authenticate student."""
    from domain.students.service import StudentService

    service = StudentService(db)
    result = await service.authenticate(data.email, data.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    student = result["student"]
    token = result["token"]
    return {
        "access_token": token,
        "token_type": "bearer",
        "student_id": str(student.id),
        "name": student.name,
    }


@router.get("/profile/{student_id}")
async def get_profile(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get student profile."""
    from domain.students.service import StudentService

    service = StudentService(db)
    profile = await service.get_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    return profile


@router.put("/profile/{student_id}")
async def update_profile(
    student_id: str, data: UpdateProfileRequest, db=Depends(get_db)
) -> Dict[str, Any]:
    """Update student profile."""
    from domain.students.service import StudentService
    from domain.students.models import StudentUpdate

    service = StudentService(db)
    try:
        student = await service.update_profile(
            student_id, StudentUpdate(**data.model_dump(exclude_unset=True))
        )
        return {"message": "Profile updated", "student_id": str(student.id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/progress/{student_id}")
async def get_progress(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get student progress."""
    from domain.analytics.service import AnalyticsService

    service = AnalyticsService(db)
    return await service.get_student_progress(student_id)


@router.get("/topic-mastery/{student_id}")
async def get_topic_mastery(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get topic-wise mastery."""
    from domain.students.service import StudentService

    service = StudentService(db)
    topics = await service.get_topic_mastery(student_id)
    return {"student_id": student_id, "topics": topics}


@router.post("/record-practice")
async def record_practice(data: TopicUpdateRequest, db=Depends(get_db)) -> Dict[str, Any]:
    """Record a practice attempt and update topic mastery."""
    from domain.learning.service import LearningService
    from core.event_manager import get_event_bus

    service = LearningService(db, event_bus=get_event_bus())
    student_id = "demo-student-id"
    result = await service.record_practice(
        student_id, data.topic, data.score, data.question_type
    )
    return result


@router.get("/dashboard/{student_id}")
async def get_dashboard(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get complete dashboard data."""
    from domain.analytics.service import AnalyticsService

    service = AnalyticsService(db)
    return await service.get_dashboard_data(student_id)


@router.get("/study-plan/{student_id}")
async def get_study_plan(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get today's study plan."""
    from domain.study_planner.service import StudyPlannerService

    service = StudyPlannerService(db)
    return await service.generate_daily_plan(student_id)


@router.get("/revision-due/{student_id}")
async def get_revision_due(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get topics due for revision."""
    from domain.revision.service import RevisionService

    service = RevisionService(db)
    revisions = await service.get_due_revisions(student_id)
    stats = await service.get_revision_stats(student_id)
    return {"student_id": student_id, "due_revisions": revisions, "stats": stats}


@router.post("/notes/generate")
async def generate_notes(data: dict, db=Depends(get_db)) -> Dict[str, Any]:
    """Generate notes from content."""
    from domain.notes.service import NotesService

    service = NotesService(db)
    return await service.generate_notes(
        student_id=data.get("student_id", "demo"),
        topic=data.get("topic", "General"),
        content=data.get("content", ""),
        source=data.get("source", "answer"),
    )


@router.get("/mock-tests/generate")
async def generate_mock_test(
    student_id: str, paper: str = "GS2", num_questions: int = 10, db=Depends(get_db)
) -> Dict[str, Any]:
    """Generate a mock test."""
    from domain.mock_tests.service import MockTestService

    service = MockTestService(db)
    return await service.generate_mock_test(student_id, paper, num_questions)


@router.post("/mock-tests/evaluate")
async def evaluate_answer(data: dict, db=Depends(get_db)) -> Dict[str, Any]:
    """Evaluate a mock test answer."""
    from domain.mock_tests.service import MockTestService

    service = MockTestService(db)
    return await service.evaluate_answer(
        test_id=data.get("test_id", ""),
        question_id=data.get("question_id", ""),
        student_answer=data.get("answer", ""),
        max_marks=data.get("max_marks", 15),
        question_text=data.get("question_text", ""),
        topic=data.get("topic", ""),
    )


@router.get("/current-affairs/daily")
async def get_daily_current_affairs(date: Optional[str] = None) -> Dict[str, Any]:
    """Get daily current affairs digest."""
    from domain.current_affairs.service import CurrentAffairsService

    service = CurrentAffairsService(None)  # type: ignore
    return await service.get_daily_digest(date)


@router.get("/interview/mock")
async def get_mock_interview(
    student_id: str, categories: Optional[str] = None, db=Depends(get_db)
) -> Dict[str, Any]:
    """Generate a mock interview session."""
    from domain.interview.service import InterviewService

    service = InterviewService(db)
    cat_list = categories.split(",") if categories else None
    return await service.generate_mock_interview(student_id, cat_list)


@router.get("/analytics/monthly-report/{student_id}")
async def get_monthly_report(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get monthly progress report."""
    from domain.analytics.service import AnalyticsService

    service = AnalyticsService(db)
    return await service.get_monthly_report(student_id)


@router.delete("/account/{student_id}")
async def delete_account(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Delete student account and all associated data."""
    from domain.students.service import StudentService
    from domain.students.models import Student

    service = StudentService(db)
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    await db.delete(student)
    await db.flush()
    return {"message": "Account deleted successfully"}


@router.post("/quiz/generate")
async def generate_quiz(data: dict, db=Depends(get_db)) -> Dict[str, Any]:
    """Generate a quiz for a topic."""
    from domain.learning.service import LearningService

    service = LearningService(db)
    topic = data.get("topic", "General")
    num_questions = data.get("num_questions", 5)

    questions = []
    for i in range(num_questions):
        questions.append({
            "id": f"quiz-q-{i+1}",
            "question": f"Question {i+1} about {topic}?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": i % 4,
            "explanation": f"Explanation for question {i+1} on {topic}.",
            "difficulty": ["easy", "medium", "hard"][i % 3],
            "topic": topic,
        })

    return {
        "id": f"quiz-{int(time.time())}",
        "topic": topic,
        "questions": questions,
        "total_questions": len(questions),
        "estimated_time_min": len(questions) * 2,
    }


@router.get("/recommendations/{student_id}")
async def get_recommendations(student_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Get personalized topic recommendations."""
    from domain.learning.service import LearningService

    service = LearningService(db)
    recommendations = await service.get_recommended_topics(student_id)
    progress = await service.get_learning_progress(student_id)
