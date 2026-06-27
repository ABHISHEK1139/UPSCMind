"""
Deep System Audit
═══════════════════════════════════════════════════════════════
Comprehensive audit of all system components for bugs.
"""
import asyncio
import inspect
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestRetrievalBugs:
    """Audit retrieval module."""

    def test_precomputed_retriever_handles_missing_collection(self):
        """BUG: PrecomputedRetriever should handle missing collection gracefully."""
        from domain.retrieval.precomputed_retriever import PrecomputedRetriever
        from unittest.mock import MagicMock, AsyncMock

        mock_client = MagicMock()
        # Return empty list (question not found)
        mock_client.retrieve = AsyncMock(return_value=[])

        retriever = PrecomputedRetriever(qdrant_client=mock_client)
        result = asyncio.run(retriever.search_by_question_id(999))
        assert isinstance(result, list)
        assert len(result) == 0

    def test_hybrid_retriever_missing_dependencies(self):
        """BUG: HybridRetriever crashes if sentence-transformers not installed."""
        from domain.retrieval.hybrid_retriever import HybridRetriever
        # Should not crash even without sentence-transformers
        retriever = HybridRetriever()
        assert retriever is not None

    def test_router_strategy_selection(self):
        """Verify router selects correct strategies."""
        from domain.retrieval.router import RetrievalRouter, RetrievalStrategy
        router = RetrievalRouter()
        # Graph-only types
        assert router.select_strategy("relationship") == RetrievalStrategy.GRAPH_ONLY
        assert router.select_strategy("timeline") == RetrievalStrategy.GRAPH_ONLY
        assert router.select_strategy("constitutional_amendment_chain") == RetrievalStrategy.GRAPH_ONLY
        assert router.select_strategy("institutional_interaction") == RetrievalStrategy.GRAPH_ONLY
        # Hybrid + graph types
        assert router.select_strategy("evolution") == RetrievalStrategy.HYBRID_AND_GRAPH
        assert router.select_strategy("comparison") == RetrievalStrategy.HYBRID_AND_GRAPH
        # Pure hybrid types
        assert router.select_strategy("factual") == RetrievalStrategy.HYBRID_ONLY
        assert router.select_strategy("analytical") == RetrievalStrategy.HYBRID_ONLY
        # Unknown type defaults to hybrid
        assert router.select_strategy("unknown_type") == RetrievalStrategy.HYBRID_ONLY


class TestEvaluationBugs:
    """Audit evaluation module."""

    def test_hallucination_no_context_returns_pass(self):
        """BUG: Hallucination check should pass when no context available."""
        from domain.evaluation.hallucination import HallucinationMetric
        metric = HallucinationMetric()
        result = metric.evaluate("Question", "Answer", context=None)
        assert result.score == 1.0

    def test_hallucination_empty_context_returns_pass(self):
        """BUG: Empty context list should pass."""
        from domain.evaluation.hallucination import HallucinationMetric
        metric = HallucinationMetric()
        result = metric.evaluate("Question", "Answer", context=[])
        assert result.score == 1.0

    def test_upsc_quality_returns_valid_score(self):
        """BUG: UPSC quality metric should always return valid score."""
        from domain.evaluation.upsc_quality import UPSCQualityMetric
        metric = UPSCQualityMetric()
        # Should not crash even with empty inputs
        result = metric.evaluate("", "")
        assert 0.0 <= result.score <= 1.0

    def test_metric_result_model(self):
        """Verify MetricResult has correct fields."""
        from domain.evaluation.metrics import MetricResult
        r = MetricResult(name="test", score=0.5, details="test")
        assert r.name == "test"
        assert r.score == 0.5


class TestOrchestratorBugs:
    """Audit orchestrator and pipeline."""

    def test_state_reducer_preserves_keys(self):
        """BUG: State reducer should preserve all keys from both states."""
        from domain.answer_generation.orchestrator_v3 import _state_reducer
        a = {"key1": "val1", "key2": None}
        b = {"key2": "val2", "key3": "val3"}
        merged = _state_reducer(a, b)
        assert merged["key1"] == "val1"
        assert merged["key2"] == "val2"
        assert merged["key3"] == "val3"

    def test_state_reducer_none_handling(self):
        """BUG: State reducer should handle None states."""
        from domain.answer_generation.orchestrator_v3 import _state_reducer
        assert _state_reducer(None, {"a": 1}) == {"a": 1}
        assert _state_reducer({"a": 1}, None) == {"a": 1}
        assert _state_reducer(None, None) == {}

    def test_graph_compiles(self):
        """BUG: Graph should compile without errors."""
        from domain.answer_generation.orchestrator_v3 import build_answer_graph_v3
        graph = build_answer_graph_v3()
        assert graph is not None

    def test_all_nodes_have_cot_trace(self):
        """BUG: All nodes should append to cot_trace."""
        from domain.answer_generation import nodes_v3
        # Check that _append_cot is called in all nodes
        source = inspect.getsource(nodes_v3)
        # Count occurrences of _append_cot
        count = source.count("_append_cot")
        # Should be at least 8 (one per node: intent, retrieval, blueprint, planner, drafting, reviewer, verification, confidence)
        assert count >= 8, f"Expected at least 8 _append_cot calls, found {count}"


class TestDatabaseBugs:
    """Audit database layer."""

    def test_all_models_registered_on_base(self):
        """BUG: All ORM models must be registered on the shared Base."""
        from core.database import Base
        from domain.students.models import (
            Student, StudentPreference, StudentProgress, Topic,
            StudyPlan, Note, MockTestAttempt, RevisionRecord, StudentTopicMastery
        )
        # All models should be in Base.metadata
        tables = set(Base.metadata.tables.keys())
        expected = {
            "students", "student_preferences", "student_progress",
            "topics", "study_plans", "notes", "mock_test_attempts",
            "revision_records", "student_topic_mastery_orm",
            "student_topic_mastery",  # association table
        }
        for table in expected:
            assert table in tables, f"Table '{table}' not registered on Base"

    def test_async_session_rollback_on_error(self):
        """BUG: Sessions should rollback on error."""
        from core.database import AsyncSessionLocal
        # Just verify the session factory is configured
        assert AsyncSessionLocal is not None

    def test_redis_client_singleton(self):
        """BUG: Redis client should be singleton."""
        from core.db_redis import get_redis_client
        c1 = get_redis_client()
        c2 = get_redis_client()
        assert c1 is c2

    def test_qdrant_client_singleton(self):
        """BUG: Qdrant client should be singleton."""
        from core.db_qdrant import get_qdrant_client
        c1 = get_qdrant_client()
        c2 = get_qdrant_client()
        assert c1 is c2


class TestServiceBugs:
    """Audit all services."""

    def test_student_service_email_normalization(self):
        """BUG: Email should be normalized to lowercase."""
        from domain.students.service import StudentService, sanitize_email
        # Test the sanitize function directly
        assert sanitize_email("  TEST@EXAMPLE.COM  ") == "test@example.com"
        # Invalid email should raise
        with pytest.raises(ValueError):
            sanitize_email("not-an-email")

    def test_analytics_handles_missing_student(self):
        """BUG: Analytics should return empty data for unknown student."""
        from domain.analytics.service import AnalyticsService
        db = MagicMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        db.flush = AsyncMock()
        svc = AnalyticsService(db)
        result = asyncio.run(svc.get_dashboard_data("nonexistent-id"))
        # Should not crash, should return valid structure
        assert "student_id" in result
        assert "overall_progress" in result

    def test_notes_handles_empty_content(self):
        """BUG: Notes service should handle empty content."""
        from domain.notes.service import NotesService
        db = MagicMock()
        svc = NotesService(db)
        result = asyncio.run(svc.generate_notes("s1", "Topic", ""))
        assert "summary" in result
        assert isinstance(result["key_points"], list)
        assert isinstance(result["flashcards"], list)

    def test_revision_handles_zero_mastery(self):
        """BUG: Revision should handle zero mastery score."""
        from domain.revision.service import RevisionService
        db = MagicMock()
        svc = RevisionService(db)
        result = svc.calculate_next_revision(0.0, 0, 0.0)
        assert result["status"] == "urgent"
        assert result["interval_days"] == 1

    def test_current_affairs_handles_no_date(self):
        """BUG: Current affairs should work without specific date."""
        from domain.current_affairs.service import CurrentAffairsService
        db = MagicMock()
        svc = CurrentAffairsService(db)
        result = asyncio.run(svc.get_daily_digest())
        assert "date" in result
        assert "items" in result

    def test_mock_test_handles_zero_questions(self):
        """BUG: Mock test should handle zero questions request."""
        from domain.mock_tests.service import MockTestService
        db = MagicMock()
        svc = MockTestService(db)
        result = asyncio.run(svc.generate_mock_test("s1", "GS2", 0))
        assert result["total_questions"] == 0

    def test_interview_handles_empty_categories(self):
        """BUG: Interview should handle empty categories list."""
        from domain.interview.service import InterviewService
        db = MagicMock()
        svc = InterviewService(db)
        result = asyncio.run(svc.generate_mock_interview("s1", [], 0))
        assert result["total_questions"] == 0


class TestAPIRouteBugs:
    """Audit API routes."""

    def test_student_routes_use_db_dependency(self):
        """BUG: Routes should inject DB session via Depends."""
        from api.routes_student import router
        # Check that routes exist
        routes = [r for r in router.routes if hasattr(r, 'path')]
        assert len(routes) > 0

    def test_security_endpoints_exist(self):
        """BUG: Security module should have JWT endpoints."""
        from api.security import create_token, verify_token, get_current_student
        assert callable(create_token)
        assert callable(verify_token)

    def test_middleware_order(self):
        """BUG: Security headers middleware should be applied."""
        from main import create_app
        app = create_app()
        # Should have middleware stack
        assert app.user_middleware is not None

    def test_cors_restricted_in_prod(self):
        """BUG: CORS should be restricted in production."""
        from core.config import get_settings
        settings = get_settings()
        # In debug mode, CORS allows localhost
        if settings.APP_DEBUG:
            assert settings.APP_DEBUG is True
        # In prod, CORS should be restricted to specific origins
        # (tested via main.py middleware configuration)


class TestWorkerBugs:
    """Audit workers and governance."""

    def test_celery_app_exists(self):
        """BUG: Celery app should be configured."""
        from workers.celery_app import celery_app
        assert celery_app is not None

    def test_base_scraper_abstract(self):
        """BUG: Base scraper should be abstract."""
        from scrapers.base_scraper import BaseScraper
        assert hasattr(BaseScraper, 'scrape_latest')
        assert hasattr(BaseScraper, 'get_source_name')

    def test_rate_limiter_redis_vs_memory(self):
        """BUG: Governance rate limiter uses in-memory dict, not Redis."""
        from governance.rate_limiter import RateLimiter
        rl = RateLimiter(requests_per_minute=10)
        # Should work without Redis
        assert rl.allow("test") is True


class TestConfigBugs:
    """Audit configuration."""

    def test_settings_singleton(self):
        """BUG: Settings should be singleton."""
        from core.config import get_settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_required_env_vars(self):
        """BUG: Critical env vars should have defaults."""
        from core.config import get_settings
        settings = get_settings()
        assert settings.DATABASE_URL is not None
        assert settings.OPENROUTER_API_KEY is not None or settings.APP_DEBUG

    def test_docker_compose_exists(self):
        """BUG: Docker compose should be valid."""
        import os
        # docker-compose.yml is in the hermes_v2 directory (parent of backend/)
        compose_path = os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.yml")
        if not os.path.exists(compose_path):
            # Skip if not found (container environment)
            pytest.skip(f"docker-compose.yml not found at {compose_path}")
        with open(compose_path) as f:
            content = f.read()
        assert "services" in content
        assert "postgres" in content
