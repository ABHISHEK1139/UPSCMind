"""
Interview Preparation Service
═══════════════════════════════════════════════════════════════
Manages UPSC Civil Services Interview (Personality Test) preparation.
Features:
- Mock interview simulation
- Personality trait analysis
- Question bank by category
- Answer evaluation with feedback
- DAF (Detailed Application Form) analysis
- Current affairs integration for interview
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Interview Categories ────────────────────────────────────────────────────

INTERVIEW_CATEGORIES = [
    "Personal Background",
    "Current Affairs",
    "Optional Subject",
    "General Studies",
    "Personality & Leadership",
    "Ethical Dilemmas",
    "Hobbies & Interests",
    "State-Specific Questions",
    "International Relations",
    "Economy & Development",
    "Science & Technology",
    "Social Issues",
]

# ── Question Bank Template ──────────────────────────────────────────────────

SAMPLE_QUESTIONS = {
    "Personal Background": [
        "Tell us about yourself.",
        "Why do you want to join the civil services?",
        "What are your strengths and weaknesses?",
        "Tell us about your hometown and its significance.",
        "What is the meaning of your name?",
        "How has your background influenced your career choice?",
    ],
    "Current Affairs": [
        "What are the most important national issues today?",
        "What is your view on the recent [policy/legislation]?",
        "How would you handle [current crisis situation]?",
        "What are the challenges in India's neighborhood policy?",
        "Discuss the impact of AI on governance.",
    ],
    "Optional Subject": [
        "How does your optional subject help in administration?",
        "What are the recent developments in your optional subject?",
        "How would you apply your optional subject knowledge as a DC?",
    ],
    "Personality & Leadership": [
        "Describe a situation where you demonstrated leadership.",
        "How do you handle conflict in a team?",
        "What would you do if your orders conflict with your conscience?",
        "How do you prioritize when faced with multiple crises?",
        "Tell us about a failure and what you learned from it.",
    ],
    "Ethical Dilemmas": [
        "You discover a colleague is corrupt. What do you do?",
        "A powerful politician asks you to bend rules. How do you handle it?",
        "You have to choose between following rules and helping a poor person.",
        "What would you do if you witness discrimination in your office?",
    ],
    "General Studies": [
        "What are the major challenges facing Indian agriculture?",
        "Discuss the federal structure of India.",
        "What reforms would you suggest for Indian education?",
        "How can India achieve sustainable development?",
    ],
}


class InterviewService:
    """Manages UPSC Interview preparation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_mock_interview(
        self,
        student_id: str,
        categories: Optional[List[str]] = None,
        num_questions: int = 10,
        focus_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate a mock interview session."""
        import hashlib
        seed = int(hashlib.md5(student_id.encode()).hexdigest()[:8], 16)
        
        selected_categories = categories or INTERVIEW_CATEGORIES[:5]
        
        # Filter by focus_areas if provided
        if focus_areas:
            selected_categories = [c for c in selected_categories if c in focus_areas] or selected_categories
        
        questions = []
        q_idx = 0

        for cat in selected_categories:
            cat_questions = SAMPLE_QUESTIONS.get(cat, [])
            if cat_questions:
                num_from_cat = max(1, num_questions // len(selected_categories))
                for i in range(min(num_from_cat, len(cat_questions))):
                    q_idx += 1
                    q = cat_questions[i]
                    # Deterministic difficulty based on question index
                    difficulty = ["easy", "medium", "hard"][(seed + q_idx) % 3]
                    duration = 2 + ((seed + q_idx) % 4)  # 2-5 minutes
                    
                    questions.append({
                        "id": f"iq-{seed:05d}-{q_idx:03d}",
                        "category": cat,
                        "question": q,
                        "difficulty": difficulty,
                        "expected_duration_min": duration,
                        "follow_up": f"Follow-up to '{q[:30]}...'",
                    })

        # Trim to requested count
        questions = questions[:num_questions]

        return {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "type": "mock_interview",
            "total_questions": len(questions),
            "estimated_duration_min": sum(q["expected_duration_min"] for q in questions),
            "categories_covered": selected_categories,
            "questions": questions,
            "instructions": [
                "Answer as if you are in a real UPSC interview panel",
                "Be concise — aim for 2-3 minutes per answer",
                "Maintain composure and body language",
                "Support your answer with facts and examples",
                "Show balanced perspective — avoid extreme views",
                "Be honest — 'I don't know' is acceptable for unknown topics",
            ],
            "evaluation_criteria": [
                "Content Knowledge (25%)",
                "Clarity of Thought (20%)",
                "Communication Skills (20%)",
                "Confidence & Composure (15%)",
                "Analytical Ability (10%)",
                "Personality & Values (10%)",
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "not_started",
        }

    async def evaluate_interview_answer(
        self,
        question_id: str,
        answer: str,
        category: str,
    ) -> Dict[str, Any]:
        """Evaluate an interview answer and provide feedback."""
        # In production, this would use LLM for evaluation
        # For now, provide structured feedback template

        word_count = len(answer.split())
        duration_est = word_count / 150  # ~150 words per minute

        return {
            "question_id": question_id,
            "category": category,
            "evaluation": {
                "content_score": round(random.uniform(0.5, 0.95), 2),
                "clarity_score": round(random.uniform(0.5, 0.95), 2),
                "confidence_score": round(random.uniform(0.5, 0.95), 2),
                "relevance_score": round(random.uniform(0.5, 0.95), 2),
                "overall_score": round(random.uniform(0.55, 0.90), 2),
            },
            "feedback": {
                "strengths": [
                    "Good understanding of the topic",
                    "Relevant examples cited",
                    "Balanced perspective shown",
                ],
                "areas_for_improvement": [
                    "Could include more specific data points",
                    "Structure could be improved (Introduction → Body → Conclusion)",
                    "Add constitutional/articles references where applicable",
                ],
                "suggested_answer_framework": [
                    "Start with a brief introduction/context",
                    "Present 2-3 key arguments with examples",
                    "Include relevant data/constitutional provisions",
                    "Conclude with a balanced way forward",
                ],
            },
            "word_count": word_count,
            "estimated_duration_min": round(duration_est, 1),
            "answer_quality": "good" if word_count > 100 else "needs_improvement",
        }

    async def analyze_daf(
        self,
        student_id: str,
        daf_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze Detailed Application Form and suggest preparation areas."""
        return {
            "student_id": student_id,
            "analysis": {
                "background": {
                    "education": daf_data.get("education", "Not provided"),
                    "work_experience": daf_data.get("work_experience", "Fresher"),
                    "hometown": daf_data.get("hometown", "Not provided"),
                    "state": daf_data.get("state", "Not provided"),
                },
                "likely_questions": [
                    f"About {daf_data.get('hometown', 'your hometown')} — its culture, issues, development",
                    f"Why {daf_data.get('optional_subject', 'your optional')} as optional?",
                    "Your service preference and why",
                    "How your background will help in administration",
                ],
                "preparation_focus": [
                    f"Deep knowledge of {daf_data.get('hometown', 'hometown')} — history, geography, issues",
                    f"State-specific current affairs for {daf_data.get('state', 'your state')}",
                    "Detailed understanding of optional subject applications",
                    "Your hobbies — be prepared for in-depth questions",
                    "Work experience — lessons learned, challenges faced",
                ],
                "strengths_to_highlight": [
                    "Academic achievements",
                    "Extracurricular activities",
                    "Leadership experiences",
                    "Community service",
                    "Unique skills or certifications",
                ],
            },
        }

    async def get_interview_tips(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get interview preparation tips."""
        tips = {
            "general": [
                "Be yourself — the panel values authenticity",
                "Stay calm and composed even under pressure",
                "Listen carefully before answering",
                "Admit if you don't know something — don't bluff",
                "Maintain eye contact with all panel members",
                "Dress formally and arrive early",
            ],
            "current_affairs": [
                "Read at least 2 newspapers daily",
                "Focus on government policies and schemes",
                "Know major international developments",
                "Prepare state-specific current affairs",
                "Have opinions backed by facts",
            ],
            "personality": [
                "Prepare your 'Tell us about yourself' thoroughly",
                "Be ready to justify your service preferences",
                "Know your DAF inside out",
                "Practice mock interviews regularly",
                "Develop a balanced worldview",
            ],
        }

        if category and category in tips:
            return {"category": category, "tips": tips[category]}

        return {"category": "all", "tips": tips}
