"""
Hermes V2 — Training Data Tests
═══════════════════════════════════════════════════════════════
Tests for the training data pipeline: collection, formatting,
export, and quality gating.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


class TestDatasetCollector:
    """Test the dataset collector."""

    def test_collect_creates_trajectory(self):
        from domain.dataset.collector import DatasetCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = DatasetCollector(output_dir=tmpdir)
            state = {
                "question": "Explain the Basic Structure Doctrine.",
                "domain": "Polity",
                "question_type": "analytical",
                "detected_entities": ["Kesavananda Bharati", "Article 21"],
                "constitutional_weight": "HIGH",
                "retrieved_chunks": [
                    {"text": "The Basic Structure Doctrine was established in 1973.", "source": "qdrant"},
                ],
                "reasoning_plan": "1. Define doctrine. 2. Explain key cases. 3. Discuss evolution.",
                "framework": "Thematic",
                "examiner_persona": "Constitutional law expert",
                "trap": "Confusing with judicial review",
                "differentiator": "Link to global constitutionalism",
                "draft_answer": "word " * 300,
                "critique": "Well-structured answer with good citations.",
                "critique_score": 0.95,
                "fact_check_passed": True,
                "guardrails_passed": True,
                "constitutional_check_passed": True,
                "revision_iterations": 1,
                "improved_answer": "improved " * 300,
                "final_answer": "final " * 300,
            }
            trajectory = collector.collect_from_state(state)
            assert trajectory is not None
            assert trajectory.training_eligible is True
            assert len(trajectory.cot_trace) >= 5

    def test_reject_low_quality(self):
        from domain.dataset.collector import DatasetCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = DatasetCollector(output_dir=tmpdir)
            state = {
                "question": "Test",
                "critique_score": 0.5,
                "fact_check_passed": False,
                "guardrails_passed": True,
                "constitutional_check_passed": True,
                "revision_iterations": 3,
                "draft_answer": "short",
                "constitutional_weight": "LOW",
            }
            trajectory = collector.collect_from_state(state)
            assert trajectory is None

    def test_chatml_format(self):
        from domain.dataset.collector import DatasetCollector
        from domain.dataset.schemas import TrajectoryRecord

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = DatasetCollector(output_dir=tmpdir)
            state = {
                "question": "Explain GST.",
                "domain": "Economy",
                "question_type": "analytical",
                "detected_entities": ["GST", "101st Amendment"],
                "constitutional_weight": "HIGH",
                "retrieved_chunks": [{"text": "GST context", "source": "qdrant"}],
                "reasoning_plan": "Define GST. Explain structure. Discuss impact.",
                "framework": "Thematic",
                "draft_answer": "word " * 300,
                "critique": "Good answer.",
                "critique_score": 0.95,
                "fact_check_passed": True,
                "guardrails_passed": True,
                "constitutional_check_passed": True,
                "revision_iterations": 0,
                "final_answer": "final " * 300,
            }
            trajectory = collector.collect_from_state(state)
            assert trajectory is not None

            chatml = collector.to_chatml(trajectory)
            assert len(chatml.messages) == 3  # system, user, assistant
            assert chatml.messages[0].role == "system"
            assert chatml.messages[1].role == "user"
            assert chatml.messages[2].role == "assistant"
            assert "<think>" in chatml.messages[2].content
            assert "</think>" in chatml.messages[2].content

    def test_dpo_pair_generation(self):
        from domain.dataset.collector import DatasetCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = DatasetCollector(output_dir=tmpdir)
            state = {
                "question": "Explain GST.",
                "domain": "Economy",
                "question_type": "analytical",
                "detected_entities": ["GST"],
                "constitutional_weight": "MEDIUM",
                "retrieved_chunks": [],
                "reasoning_plan": "Plan",
                "framework": "Thematic",
                "draft_answer": "word " * 300,
                "critique": "Needs improvement in structure and depth.",
                "critique_score": 0.95,
                "fact_check_passed": True,
                "guardrails_passed": True,
                "constitutional_check_passed": True,
                "revision_iterations": 1,
                "improved_answer": "improved " * 300,
                "final_answer": "final " * 300,
            }
            trajectory = collector.collect_from_state(state)
            assert trajectory is not None

            dpo = collector.to_dpo_pair(trajectory)
            assert dpo is not None
            assert dpo.chosen != dpo.rejected


class TestDatasetExporter:
    """Test the dataset exporter."""

    def test_deduplication(self):
        from domain.dataset.exporter import DatasetExporter
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test JSONL with duplicates
            input_path = Path(tmpdir) / "test.jsonl"
            with open(input_path, "w") as f:
                f.write(json.dumps({"question": "Q1", "answer": "A1"}) + "\n")
                f.write(json.dumps({"question": "Q1", "answer": "A1"}) + "\n")
                f.write(json.dumps({"question": "Q2", "answer": "A2"}) + "\n")

            output_path = Path(tmpdir) / "deduped.jsonl"
            kept, removed = DatasetExporter.deduplicate_jsonl(input_path, output_path)
            assert kept == 2
            assert removed == 1

    def test_statistics(self):
        from domain.dataset.exporter import DatasetExporter
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = Path(tmpdir) / "test.jsonl"
            with open(data_file, "w") as f:
                f.write(json.dumps({
                    "question": "Q1",
                    "metadata": {"critique_score": 0.95, "domain": "Polity"},
                }) + "\n")

            exporter = DatasetExporter(data_dir=tmpdir, export_dir=tmpdir)
            stats = exporter.compute_statistics(data_file)
            assert stats["total"] == 1
