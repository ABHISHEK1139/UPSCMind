"""
Hermes V2 — Answer Quality Tests
═══════════════════════════════════════════════════════════════
Tests for answer generation quality using DeepEval metrics.
"""

from __future__ import annotations

import pytest


class TestAnswerQuality:
    """Test suite for answer quality."""

    def test_answer_has_structure(self):
        """Answers should have intro, body, and conclusion."""
        sample_answer = """
        Introduction: The Basic Structure Doctrine is a judicial principle...
        
        Body:
        - Origin in Kesavananda Bharati (1973)
        - Core elements: secularism, federalism, democracy
        - Evolution through Minerva Mills, Waman Rao
        
        Conclusion: The doctrine remains a cornerstone...
        """
        assert "Introduction" in sample_answer or "Intro" in sample_answer
        assert "Body" in sample_answer
        assert "Conclusion" in sample_answer

    def test_answer_has_citations(self):
        """Answers should cite Articles, Amendments, or cases."""
        sample_answer = "Article 21 was interpreted in Maneka Gandhi v. Union of India."
        assert "Article" in sample_answer or "v." in sample_answer

    def test_answer_minimum_length(self):
        """Answers should be at least 200 words."""
        sample_answer = "word " * 250
        assert len(sample_answer.split()) >= 200

    def test_no_hedging(self):
        """Answers should not contain AI hedging phrases."""
        sample_answer = "The Basic Structure Doctrine establishes that..."
        hedging = ["I do not have", "As an AI", "I cannot answer"]
        for phrase in hedging:
            assert phrase not in sample_answer

    def test_quality_score_threshold(self):
        """Quality score should meet the threshold."""
        from domain.evaluation.metrics import StructuralMetric
        metric = StructuralMetric()
        result = metric.evaluate(
            "Test question",
            "Introduction: ... Body: ... Conclusion: ...",
        )
        assert result.score > 0.5


class TestCoTTrace:
    """Test Chain-of-Thought trace generation."""

    def test_cot_trace_has_all_steps(self):
        """CoT trace should have all 7 steps."""
        from domain.dataset.collector import DatasetCollector

        state = {
            "question": "Test question",
            "domain": "Polity",
            "question_type": "analytical",
            "detected_entities": ["Article 21"],
            "constitutional_weight": "HIGH",
            "retrieved_chunks": [{"text": "context", "source": "qdrant"}],
            "reasoning_plan": "Step 1: Define. Step 2: Explain.",
            "framework": "Thematic",
            "draft_answer": "word " * 300,
            "critique": "Good answer",
            "critique_score": 0.95,
            "fact_check_passed": True,
            "guardrails_passed": True,
            "constitutional_check_passed": True,
            "revision_iterations": 0,
        }
        collector = DatasetCollector(output_dir="/tmp/test_data")
        trace = collector.build_cot_trace(state)
        assert len(trace) >= 5  # At least 5 steps should be present

    def test_quality_gating(self):
        """Quality gate should reject low-quality answers."""
        from domain.dataset.collector import DatasetCollector

        collector = DatasetCollector(output_dir="/tmp/test_data")

        # Should pass
        good_state = {
            "question": "Test",
            "critique_score": 0.95,
            "fact_check_passed": True,
            "guardrails_passed": True,
            "constitutional_check_passed": True,
            "revision_iterations": 1,
            "draft_answer": "word " * 300,
            "constitutional_weight": "LOW",
        }
        passed, reason = collector.check_quality(good_state)
        assert passed is True
        assert reason is None

        # Should fail
        bad_state = {
            "question": "Test",
            "critique_score": 0.5,
            "fact_check_passed": False,
            "guardrails_passed": True,
            "constitutional_check_passed": True,
            "revision_iterations": 3,
            "draft_answer": "short",
            "constitutional_weight": "HIGH",
        }
        passed, reason = collector.check_quality(bad_state)
        assert passed is False
        assert reason is not None
