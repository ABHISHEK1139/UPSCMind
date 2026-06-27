"""Tests for all service modules."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestStudentService:
    def test_hash_password(self):
        from domain.students.service import hash_password, verify_password
        hashed = hash_password("TestPassword123")
        assert hashed != "TestPassword123"
        assert verify_password("TestPassword123", hashed)
        assert not verify_password("WrongPassword", hashed)


class TestStudyPlanner:
    @pytest.mark.asyncio
    async def test_foundation_phase(self):
        from domain.study_planner.service import StudyPlannerService
        db = MagicMock()
        service = StudyPlannerService(db)
        plan = await service.generate_daily_plan("test", available_hours=6.0, exam_date="2027-06-01")
        assert plan["phase"] == "foundation"
        assert plan["total_study_hours"] <= 6.0
        assert plan["total_study_hours"] >= 5.0
        assert len(plan["tasks"]) > 0

    @pytest.mark.asyncio
    async def test_revision_phase(self):
        from domain.study_planner.service import StudyPlannerService
        db = MagicMock()
        service = StudyPlannerService(db)
        plan = await service.generate_daily_plan("test", available_hours=6.0, exam_date="2026-07-15")
        assert plan["phase"] == "revision"
        assert plan["total_study_hours"] <= 6.0
        assert plan["total_study_hours"] >= 5.0

    @pytest.mark.asyncio
    async def test_time_allocation(self):
        from domain.study_planner.service import StudyPlannerService
        db = MagicMock()
        service = StudyPlannerService(db)
        plan = await service.generate_daily_plan("test", available_hours=6.0, exam_date="2027-01-01")
        total_task_minutes = sum(t["duration_minutes"] for t in plan["tasks"])
        assert total_task_minutes > 0
        assert total_task_minutes <= 6 * 60 + 5  # Allow 5 min tolerance


class TestLearningService:
    def test_topic_status_not_started(self):
        from domain.learning.service import LearningService
        db = MagicMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        service = LearningService(db)
        status = asyncio.run(service.get_topic_status("student-1", "Polity"))
        assert status["state"] == "NOT_STARTED"
        assert status["score"] == 0.0

    def test_mastery_thresholds(self):
        from domain.learning.service import MASTERED_THRESHOLD, PRACTICED_THRESHOLD
        assert MASTERED_THRESHOLD == 80
        assert PRACTICED_THRESHOLD == 60


class TestRevisionService:
    def test_revision_intervals(self):
        from domain.revision.service import REVISION_INTERVALS, MASTERY_THRESHOLD, FORGETTING_THRESHOLD
        assert REVISION_INTERVALS[0] == 1
        assert REVISION_INTERVALS[5] == 60
        assert MASTERY_THRESHOLD == 85
        assert FORGETTING_THRESHOLD == 40

    def test_calculate_next_revision_low_score(self):
        from domain.revision.service import RevisionService
        db = MagicMock()
        service = RevisionService(db)
        result = service.calculate_next_revision(30.0, 2, 35.0)
        assert result["status"] == "urgent"
        assert result["interval_days"] == 1

    def test_calculate_next_revision_mastered(self):
        from domain.revision.service import RevisionService
        db = MagicMock()
        service = RevisionService(db)
        result = service.calculate_next_revision(90.0, 3, 88.0)
        assert result["status"] == "mastered"


class TestNotesService:
    def test_fallback_key_points(self):
        from domain.notes.service import NotesService
        db = MagicMock()
        service = NotesService(db)
        content = "Fundamental Rights are in Part III.\nRight to Equality is Article 14.\nRight to Freedom is Article 19."
        points = service._fallback_key_points(content)
        assert len(points) > 0
        assert points[0]["category"] == "concept"

    def test_fallback_flashcards(self):
        from domain.notes.service import NotesService
        db = MagicMock()
        service = NotesService(db)
        cards = service._fallback_flashcards("Some content", "Polity")
        assert len(cards) == 2
        assert "Polity" in cards[0]["front"]

    def test_generate_mindmap(self):
        from domain.notes.service import NotesService
        db = MagicMock()
        service = NotesService(db)
        key_points = [
            {"point": "Right to Equality", "category": "concept"},
            {"point": "Article 14", "category": "article"},
        ]
        mindmap = service._generate_mindmap("Polity", "content", key_points)
        assert mindmap["central_node"] == "Polity"
        assert len(mindmap["all_nodes"]) == 2


class TestCurrentAffairs:
    def test_daily_digest_structure(self):
        from domain.current_affairs.service import CurrentAffairsService
        db = MagicMock()
        service = CurrentAffairsService(db)
        digest = asyncio.run(service.get_daily_digest())
        assert "date" in digest
        assert "items" in digest
        assert "upsc_relevance" in digest
        assert len(digest["items"]) > 0

    def test_monthly_compilation(self):
        from domain.current_affairs.service import CurrentAffairsService
        db = MagicMock()
        service = CurrentAffairsService(db)
        compilation = asyncio.run(service.get_monthly_compilation(2026, 6))
        assert compilation["month"] == "June 2026"
        assert "categories" in compilation


class TestMockTestService:
    def test_generate_mock_test(self):
        from domain.mock_tests.service import MockTestService
        db = MagicMock()
        service = MockTestService(db)
        test = asyncio.run(service.generate_mock_test("student-1", "GS2", 3))
        assert test["paper"] == "GS2"
        assert test["total_questions"] == 3
        assert test["status"] == "not_started"

    def test_evaluate_answer_short(self):
        from domain.mock_tests.service import MockTestService
        db = MagicMock()
        service = MockTestService(db)
        result = asyncio.run(service.evaluate_answer("t1", "q1", "Short answer.", 15))
        # Heuristic: < 50 words = 30% of max_marks
        assert result["score"] <= 15 * 0.4
        assert result["word_count"] <= 5

    def test_evaluate_answer_long(self):
        from domain.mock_tests.service import MockTestService
        db = MagicMock()
        service = MockTestService(db)
        long_answer = " ".join(["word"] * 250)
        result = asyncio.run(service.evaluate_answer("t1", "q1", long_answer, 15))
        # Heuristic: > 200 words = 85% of max_marks, or LLM may return different score
        assert result["score"] >= 15 * 0.5
        assert result["word_count"] == 250


class TestInterviewService:
    def test_generate_mock_interview(self):
        from domain.interview.service import InterviewService
        db = MagicMock()
        service = InterviewService(db)
        interview = asyncio.run(service.generate_mock_interview("student-1", ["Personality & Leadership"], 2))
        assert interview["total_questions"] == 2
        assert len(interview["questions"]) == 2

    def test_evaluate_interview_answer(self):
        from domain.interview.service import InterviewService
        db = MagicMock()
        service = InterviewService(db)
        result = asyncio.run(service.evaluate_interview_answer("q1", "I believe in ethical governance.", "Ethics"))
        assert "evaluation" in result
        assert "feedback" in result
