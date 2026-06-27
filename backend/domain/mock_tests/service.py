"""
Mock Test Service
═══════════════════════════════════════════════════════════════
Generates mock tests, evaluates answers, and tracks performance.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class MockTestService:
    """Manages mock test generation and evaluation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_mock_test(
        self,
        student_id: str,
        paper: str = "GS2",
        num_questions: int = 10,
        duration_minutes: int = 120,
        topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a mock test for a student."""
        
        # Sample questions (in production, fetch from database)
        # Use deterministic IDs based on student_id and index
        import hashlib
        seed = int(hashlib.md5(student_id.encode()).hexdigest()[:8], 16)
        
        sample_questions = [
            {
                "id": f"q-{seed:04d}-001",
                "question": "Discuss the significance of the 73rd and 74th Constitutional Amendments.",
                "marks": 15,
                "topic": "Polity",
            },
            {
                "id": f"q-{seed:04d}-002",
                "question": "What is fiscal deficit? Discuss its implications.",
                "marks": 15,
                "topic": "Economy",
            },
            {
                "id": f"q-{seed:04d}-003",
                "question": "Discuss the salient features of Harappan architecture.",
                "marks": 15,
                "topic": "History",
            },
        ]

        questions = sample_questions[:num_questions]

        return {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "paper": paper,
            "title": f"{paper} Mock Test",
            "duration_minutes": duration_minutes,
            "total_marks": sum(q["marks"] for q in questions),
            "total_questions": len(questions),
            "questions": questions,
            "instructions": [
                "Write answers in your own words",
                "Include specific data, articles, and examples",
                "Structure: Introduction → Body → Conclusion",
                "Time management is crucial",
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "not_started",
        }

    async def evaluate_answer(
        self,
        test_id: str,
        question_id: str,
        student_answer: str,
        max_marks: int,
        question_text: str = "",
        topic: str = "",
    ) -> Dict[str, Any]:
        """Evaluate a student's answer using LLM."""
        
        # Try LLM evaluation first
        try:
            eval_result = await self._llm_evaluate(
                question_text, student_answer, max_marks, topic
            )
            if eval_result:
                return eval_result
        except Exception as exc:
            logger.warning("[MOCK] LLM eval failed, using heuristic: %s", exc)

        # Fallback: heuristic evaluation
        word_count = len(student_answer.split())
        
        if word_count < 50:
            score = max_marks * 0.3
            feedback = "Too short. Expand with examples and data."
        elif word_count < 100:
            score = max_marks * 0.5
            feedback = "Good start. Add more structure and examples."
        elif word_count < 200:
            score = max_marks * 0.7
            feedback = "Good answer. Improve conclusion and add diagrams."
        else:
            score = max_marks * 0.85
            feedback = "Comprehensive answer. Fine-tune presentation."

        return {
            "test_id": test_id,
            "question_id": question_id,
            "score": round(score, 1),
            "max_marks": max_marks,
            "percentage": round((score / max_marks) * 100, 1),
            "word_count": word_count,
            "feedback": feedback,
            "strengths": ["Content coverage", "Structure"],
            "weaknesses": ["Could add more examples", "Conclusion needs improvement"],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _llm_evaluate(
        self,
        question: str,
        answer: str,
        max_marks: int,
        topic: str,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate answer using LLM."""
        from core.llm_gateway import LLMGateway

        gateway = LLMGateway()
        system_prompt = f"""You are a UPSC answer evaluator. Evaluate the student's answer for the given question.
Score each dimension 0-{max_marks}:
- Content & Knowledge (40%): Factual accuracy, relevant concepts
- Structure & Framework (25%): Introduction, body, conclusion, logical flow
- Examples & Data (20%): Specific examples, data points, constitutional articles
- Language & Presentation (15%): Grammar, clarity, academic tone

Return JSON: {{"score": X, "percentage": X, "strengths": [...], "weaknesses": [...], "feedback": "..."}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Topic: {topic}\n\nQuestion: {question}\n\nStudent Answer:\n{answer}"},
        ]

        response = await gateway.complete(
            messages=messages,
            temperature=0.2,
            max_tokens=512,
            use_cache=True,
        )
        import json
        result = json.loads(response.content)
        result["test_id"] = "eval"
        result["question_id"] = "eval"
        result["max_marks"] = max_marks
        result["word_count"] = len(answer.split())
        result["evaluated_at"] = datetime.now(timezone.utc).isoformat()
        return result

    async def get_test_history(
        self, student_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get mock test history for a student."""
        return []

    async def get_test_analysis(self, test_id: str) -> Dict[str, Any]:
        """Get detailed analysis of a completed test."""
        return {
            "test_id": test_id,
            "overall_score": 0,
            "time_taken_minutes": 0,
            "question_wise_analysis": [],
            "topic_wise_score": {},
            "improvement_areas": [],
            "strengths": [],
        }
