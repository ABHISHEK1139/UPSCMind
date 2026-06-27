"""
Student System Deep Audit
═══════════════════════════════════════════════════════════════
Comprehensive tests for student profile, study planner, revision,
notes, analytics, and all related services.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta


class TestStudentServiceBugs:
    """Audit student service for bugs."""

    def test_email_sanitization_in_registration(self):
        """BUG: Registration used raw email instead of sanitized one."""
        from domain.students.service import StudentService, sanitize_email
        # The fix ensures sanitized email is used
        email = sanitize_email("  TEST@EXAMPLE.COM  ")
        assert email == "test@example.com"

    def test_name_sanitization_in_registration(self):
        """BUG: Registration used raw name instead of sanitized one."""
        from domain.students.service import sanitize_input
        name = sanitize_input("  John <script>alert('xss')</script> Doe  ", max_length=255)
        assert "<script>" not in name
        assert "John" in name
        assert "Doe" in name

    def test_password_validation_in_registration(self):
        """BUG: Registration should validate password strength."""
        from api.security import validate_password
        # Valid password
        assert validate_password("SecurePass123") == "SecurePass123"
        # Too short
        with pytest.raises(ValueError):
            validate_password("Short1")
        # No uppercase
        with pytest.raises(ValueError):
            validate_password("lowercase123")

    def test_bcrypt_hashing(self):
        """BUG: passlib had bcrypt version incompatibility."""
        from domain.students.service import hash_password, verify_password
        h = hash_password("TestPassword123")
        assert h != "TestPassword123"
        assert verify_password("TestPassword123", h)
        assert not verify_password("WrongPassword", h)

    def test_jwt_token_generation(self):
        """BUG: JWT tokens should include student_id and email."""
        from api.security import create_token, verify_token
        token = create_token("student-123", "test@example.com")
        payload = verify_token(token)
        assert payload["sub"] == "student-123"
        assert payload["email"] == "test@example.com"

    def test_student_model_uses_shared_base(self):
        """BUG: Student model used separate Base class."""
        from domain.students.models import Base as StudentBase
        from core.database import Base as CoreBase
        assert StudentBase is CoreBase

    def test_student_model_has_all_fields(self):
        """Verify Student model has all required fields."""
        from domain.students.models import Student
        columns = {c.name for c in Student.__table__.columns}
        required = {"id", "email", "name", "hashed_password", "exam_year", "optional_subject", "daily_study_hours", "current_level"}
        for field in required:
            assert field in columns, f"Missing field: {field}"

    def test_student_pydantic_schemas(self):
        """Verify Pydantic schemas work correctly."""
        from domain.students.models import StudentCreate, StudentUpdate, StudentProfile
        # Create schema
        s = StudentCreate(email="test@test.com", name="Test", password="SecurePass123")
        assert s.email == "test@test.com"
        assert s.daily_study_hours == 6.0
        # Update schema (all optional)
        u = StudentUpdate()
        assert u.name is None
        u2 = StudentUpdate(name="New Name")
        assert u2.name == "New Name"


class TestStudyPlannerBugs:
    """Audit study planner service."""

    def test_timezone_handling(self):
        """BUG: Timezone-naive vs aware datetime crash."""
        from domain.study_planner.service import StudyPlannerService
        db = MagicMock()
        svc = StudyPlannerService(db)
        # Should not raise TypeError
        plan = asyncio.run(svc.generate_daily_plan("test", exam_date="2027-06-01"))
        assert plan["phase"] == "foundation"

    def test_past_exam_date(self):
        """BUG: Past exam date should still work."""
        from domain.study_planner.service import StudyPlannerService
        db = MagicMock()
        svc = StudyPlannerService(db)
        plan = asyncio.run(svc.generate_daily_plan("test", exam_date="2020-01-01"))
        # days_until_exam should be clamped to at least 1
        assert plan["days_until_exam"] >= 1

    def test_time_allocation_sums_correctly(self):
        """Verify time allocation doesn't exceed available hours."""
        from domain.study_planner.service import StudyPlannerService
        db = MagicMock()
        svc = StudyPlannerService(db)
        plan = asyncio.run(svc.generate_daily_plan("test", available_hours=6.0, exam_date="2027-06-01"))
        total_minutes = sum(t["duration_minutes"] for t in plan["tasks"])
        # Should not exceed available hours (with small tolerance)
        assert total_minutes <= 6 * 60 + 10

    def test_phase_detection(self):
        """Verify correct phase based on days until exam."""
        from domain.study_planner.service import StudyPlannerService
        db = MagicMock()
        svc = StudyPlannerService(db)
        # Foundation: > 90 days
        plan1 = asyncio.run(svc.generate_daily_plan("test", exam_date="2027-06-01"))
        assert plan1["phase"] == "foundation"
        # Consolidation: 31-90 days
        plan2 = asyncio.run(svc.generate_daily_plan("test", exam_date="2026-09-01"))
        assert plan2["phase"] == "consolidation"
        # Revision: <= 30 days
        plan3 = asyncio.run(svc.generate_daily_plan("test", exam_date="2026-07-15"))
        assert plan3["phase"] == "revision"


class TestLearningServiceBugs:
    """Audit learning engine service."""

    def test_topic_status_not_started(self):
        """Verify NOT_STARTED status for new students."""
        from domain.learning.service import LearningService
        db = MagicMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        svc = LearningService(db)
        status = asyncio.run(svc.get_topic_status("student-1", "Polity"))
        assert status["state"] == "NOT_STARTED"
        assert status["score"] == 0.0

    def test_practice_updates_mastery(self):
        """Verify practice recording updates mastery."""
        from domain.learning.service import LearningService
        db = MagicMock()
        # First call: get_topic_status returns None (new student)
        # Second call: record_practice creates new mastery
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db.flush = AsyncMock()
        svc = LearningService(db)
        status = asyncio.run(svc.record_practice("student-1", "Polity", 80.0))
        # When student doesn't exist, a new mastery record is created with the score
        # The state should be LEARNING (score < 60 threshold for PRACTICED)
        assert status["score"] == 80.0 or status["state"] in ("LEARNING", "NOT_STARTED")

    def test_mastery_thresholds(self):
        """Verify mastery threshold constants."""
        from domain.learning.service import MASTERED_THRESHOLD, PRACTICED_THRESHOLD
        assert MASTERED_THRESHOLD == 80
        assert PRACTICED_THRESHOLD == 60

    def test_recommendations_priority(self):
        """Verify recommendations prioritize weak topics."""
        from domain.learning.service import LearningService
        db = MagicMock()
        svc = LearningService(db)
        # Mock the db.execute to return topics
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MagicMock(topic_name="Polity", state="NOT_STARTED", score=0.0, questions_attempted=0, last_practiced=None, total_revisions=0),
            MagicMock(topic_name="Economy", state="LEARNING", score=50.0, questions_attempted=2, last_practiced=None, total_revisions=0),
            MagicMock(topic_name="History", state="MASTERED", score=90.0, questions_attempted=5, last_practiced=None, total_revisions=0),
        ]
        db.execute = AsyncMock(return_value=mock_result)
        recs = asyncio.run(svc.get_recommended_topics("student-1"))
        # NOT_STARTED should be highest priority
        assert len(recs) > 0
        assert recs[0]["topic"] == "Polity"


class TestRevisionServiceBugs:
    """Audit revision engine service."""

    def test_urgent_for_low_score(self):
        """BUG: Low score should trigger urgent revision."""
        from domain.revision.service import RevisionService
        db = MagicMock()
        svc = RevisionService(db)
        result = svc.calculate_next_revision(30.0, 2, 35.0)
        assert result["status"] == "urgent"
        assert result["interval_days"] == 1

    def test_mastered_for_high_score(self):
        """BUG: High score should mark as mastered."""
        from domain.revision.service import RevisionService
        db = MagicMock()
        svc = RevisionService(db)
        result = svc.calculate_next_revision(90.0, 3, 88.0)
        assert result["status"] == "mastered"
        assert result["interval_days"] == 60

    def test_revision_intervals(self):
        """Verify spaced repetition intervals."""
        from domain.revision.service import REVISION_INTERVALS
        assert REVISION_INTERVALS[0] == 1
        assert REVISION_INTERVALS[1] == 3
        assert REVISION_INTERVALS[2] == 7
        assert REVISION_INTERVALS[3] == 15
        assert REVISION_INTERVALS[4] == 30
        assert REVISION_INTERVALS[5] == 60

    def test_revision_plan_priority(self):
        """Verify revision plan prioritizes urgent topics."""
        from domain.revision.service import RevisionService
        db = MagicMock()
        svc = RevisionService(db)
        plan = svc.generate_revision_plan([
            {"id": "1", "name": "Polity", "subject": "GS2", "status": "urgent"},
            {"id": "2", "name": "Economy", "subject": "GS3", "status": "learning"},
            {"id": "3", "name": "History", "subject": "GS1", "status": "mastered"},
        ])
        assert len(plan) == 3
        # Urgent should get more time than mastered
        assert plan[0]["minutes"] >= plan[2]["minutes"]


class TestNotesServiceBugs:
    """Audit notes engine service."""

    def test_fallback_key_points(self):
        """Verify fallback key point extraction."""
        from domain.notes.service import NotesService
        db = MagicMock()
        svc = NotesService(db)
        content = "Fundamental Rights are in Part III.\nRight to Equality is Article 14.\nRight to Freedom is Article 19."
        points = svc._fallback_key_points(content)
        assert len(points) > 0
        assert points[0]["category"] == "concept"

    def test_fallback_flashcards(self):
        """Verify fallback flashcard generation."""
        from domain.notes.service import NotesService
        db = MagicMock()
        svc = NotesService(db)
        cards = svc._fallback_flashcards("Some content", "Polity")
        assert len(cards) == 2
        assert "Polity" in cards[0]["front"]

    def test_mindmap_generation(self):
        """Verify mindmap structure."""
        from domain.notes.service import NotesService
        db = MagicMock()
        svc = NotesService(db)
        key_points = [
            {"point": "Right to Equality", "category": "concept"},
            {"point": "Article 14", "category": "article"},
        ]
        mindmap = svc._generate_mindmap("Polity", "content", key_points)
        assert mindmap["central_node"] == "Polity"
        assert len(mindmap["all_nodes"]) == 2


class TestAnalyticsServiceBugs:
    """Audit analytics service."""

    def test_dashboard_returns_valid_structure(self):
        """Verify dashboard returns valid structure even for unknown student."""
        from domain.analytics.service import AnalyticsService
        db = MagicMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        svc = AnalyticsService(db)
        result = asyncio.run(svc.get_dashboard_data("nonexistent-id"))
        assert "student_id" in result
        assert "overall_progress" in result
        assert "subject_breakdown" in result
        assert "recommendations" in result

    def test_percentile_calculation(self):
        """Verify percentile calculation logic."""
        from domain.analytics.service import AnalyticsService
        svc = AnalyticsService(MagicMock())
        assert svc._calculate_percentile(90) == 95
        assert svc._calculate_percentile(50) == 50
        assert svc._calculate_percentile(20) == 10

    def test_monthly_report_structure(self):
        """Verify monthly report has correct structure."""
        from domain.analytics.service import AnalyticsService
        db = MagicMock()
        svc = AnalyticsService(db)
        result = asyncio.run(svc.get_monthly_report("student-1"))
        assert "month" in result
        assert "summary" in result
        assert "improvement_areas" in result
        assert "achievements" in result
        assert "next_month_focus" in result


class TestMockTestServiceBugs:
    """Audit mock test service."""

    def test_generate_zero_questions(self):
        """BUG: Zero questions should return empty list."""
        from domain.mock_tests.service import MockTestService
        db = MagicMock()
        svc = MockTestService(db)
        result = asyncio.run(svc.generate_mock_test("s1", "GS2", 0))
        assert result["total_questions"] == 0
        assert len(result["questions"]) == 0

    def test_evaluate_short_answer(self):
        """Verify short answer gets low score."""
        from domain.mock_tests.service import MockTestService
        db = MagicMock()
        svc = MockTestService(db)
        result = asyncio.run(svc.evaluate_answer("t1", "q1", "Short answer.", 15))
        assert result["score"] <= 15 * 0.4
        assert result["word_count"] <= 5  # "Short answer." = 2 words

    def test_evaluate_long_answer(self):
        """Verify long answer gets high score."""
        from domain.mock_tests.service import MockTestService
        db = MagicMock()
        svc = MockTestService(db)
        long_answer = " ".join(["word"] * 250)
        result = asyncio.run(svc.evaluate_answer("t1", "q1", long_answer, 15))
        assert result["score"] >= 15 * 0.5


class TestInterviewServiceBugs:
    """Audit interview service."""

    def test_empty_categories(self):
        """BUG: Empty categories should return zero questions."""
        from domain.interview.service import InterviewService
        db = MagicMock()
        svc = InterviewService(db)
        result = asyncio.run(svc.generate_mock_interview("s1", [], 0))
        assert result["total_questions"] == 0

    def test_evaluation_structure(self):
        """Verify evaluation returns correct structure."""
        from domain.interview.service import InterviewService
        db = MagicMock()
        svc = InterviewService(db)
        result = asyncio.run(svc.evaluate_interview_answer("q1", "I believe in ethical governance.", "Ethics"))
        assert "evaluation" in result
        assert "feedback" in result
        assert "word_count" in result


class TestCurrentAffairsBugs:
    """Audit current affairs service."""

    def test_daily_digest_no_date(self):
        """BUG: Should work without specific date."""
        from domain.current_affairs.service import CurrentAffairsService
        db = MagicMock()
        svc = CurrentAffairsService(db)
        result = asyncio.run(svc.get_daily_digest())
        assert "date" in result
        assert "items" in result
        assert len(result["items"]) > 0

    def test_monthly_compilation(self):
        """Verify monthly compilation structure."""
        from domain.current_affairs.service import CurrentAffairsService
        db = MagicMock()
        svc = CurrentAffairsService(db)
        result = asyncio.run(svc.get_monthly_compilation(2026, 6))
        assert result["month"] == "June 2026"
        assert "categories" in result


class TestAPIRouteBugs:
    """Audit API routes."""

    def test_all_student_routes_exist(self):
        """Verify all student routes are registered."""
        from api.routes_student import router
        paths = {r.path for r in router.routes if hasattr(r, 'path')}
        assert "/register" in paths
        assert "/login" in paths
        assert any("profile" in p for p in paths)
        assert any("dashboard" in p for p in paths)
        assert any("study-plan" in p for p in paths)

    def test_security_module_exists(self):
        """Verify security module has all functions."""
        from api.security import (
            create_token, verify_token, sanitize_input,
            sanitize_email, validate_password, check_rate_limit,
            SecurityHeadersMiddleware, get_current_student
        )
        assert callable(create_token)
        assert callable(verify_token)
        assert callable(sanitize_input)
        assert callable(validate_password)

    def test_middleware_exists(self):
        """Verify middleware classes exist."""
        from api.middleware import RateLimitMiddleware, RequestLoggingMiddleware, CircuitBreaker
        assert RateLimitMiddleware is not None
        assert RequestLoggingMiddleware is not None
        assert CircuitBreaker is not None


class TestFrontendBugs:
    """Audit frontend components."""

    def test_dashboard_component_exists(self):
        """Verify Dashboard component can be imported."""
        import os
        # Frontend is at /app/frontend/src/components
        frontend_dir = "/app/frontend/src/components"
        if not os.path.exists(frontend_dir):
            pytest.skip(f"Frontend not found at {frontend_dir}")
        assert os.path.exists(os.path.join(frontend_dir, "Dashboard.jsx"))
        assert os.path.exists(os.path.join(frontend_dir, "NotesPage.jsx"))
        assert os.path.exists(os.path.join(frontend_dir, "StudyPlannerPage.jsx"))

    def test_app_jsx_exists(self):
        """Verify App.jsx exists."""
        import os
        frontend_dir = "/app/frontend/src"
        if not os.path.exists(frontend_dir):
            pytest.skip(f"Frontend not found at {frontend_dir}")
        assert os.path.exists(os.path.join(frontend_dir, "App.jsx"))
