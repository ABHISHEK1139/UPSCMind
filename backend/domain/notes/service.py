"""
Notes Engine Service (Enhanced)
═══════════════════════════════════════════════════════════════
Auto-generates revision notes, flashcards, and mindmaps
from student answers and study material.
Uses LLM for intelligent content extraction and structuring.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class NotesService:
    """Manages auto-generated notes, flashcards, and mindmaps."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_notes(
        self,
        student_id: str,
        topic: str,
        content: str,
        source: str = "answer",
        note_type: str = "structured",
    ) -> Dict[str, Any]:
        """Generate structured notes from content."""
        
        key_points = await self._extract_key_points(content, topic)
        flashcards = await self._generate_flashcards(content, topic)
        summary = await self._generate_summary(content, topic)
        mindmap = self._generate_mindmap(topic, content, key_points)

        return {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "topic": topic,
            "source": source,
            "note_type": note_type,
            "summary": summary,
            "key_points": key_points,
            "flashcards": flashcards,
            "mindmap": mindmap,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _extract_key_points(self, content: str, topic: str) -> List[Dict[str, Any]]:
        """Extract key points from content using LLM."""
        from core.llm_gateway import LLMGateway

        gateway = LLMGateway()
        system_prompt = """You are a UPSC notes extraction expert. Extract the most important key points from the content.
For each point, provide: point, importance (high/medium/low), category (fact/concept/amendment/article/data/scheme), upsc_relevance (GS1/GS2/GS3/GS4).
Return JSON array: [{"point": "...", "importance": "high", "category": "concept", "upsc_relevance": "GS2"}]"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Topic: {topic}\n\nContent:\n{content[:3000]}"},
        ]

        try:
            response = await gateway.complete(
                messages=messages, temperature=0.2, max_tokens=1024, use_cache=True,
            )
            result = json.loads(response.content)
            if isinstance(result, list):
                return result[:15]
        except Exception as exc:
            logger.warning("[NOTES] LLM extraction failed, using fallback: %s", exc)

        return self._fallback_key_points(content)

    async def _generate_flashcards(self, content: str, topic: str) -> List[Dict[str, str]]:
        """Generate flashcard-style Q&A from content using LLM."""
        from core.llm_gateway import LLMGateway

        gateway = LLMGateway()
        system_prompt = """Create UPSC-relevant flashcards from the content.
Each flashcard: front (question/term), back (answer max 50 words), difficulty (easy/medium/hard).
Return JSON array: [{"front": "...", "back": "...", "difficulty": "medium"}]"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Topic: {topic}\n\nContent:\n{content[:2000]}"},
        ]

        try:
            response = await gateway.complete(
                messages=messages, temperature=0.3, max_tokens=1024, use_cache=True,
            )
            result = json.loads(response.content)
            if isinstance(result, list):
                return result[:10]
        except Exception as exc:
            logger.warning("[NOTES] LLM flashcard generation failed: %s", exc)

        return self._fallback_flashcards(content, topic)

    async def _generate_summary(self, content: str, topic: str) -> str:
        """Generate a concise summary using LLM."""
        from core.llm_gateway import LLMGateway

        gateway = LLMGateway()
        system_prompt = """Write a concise UPSC-relevant summary (150-200 words) of the content.
Focus on: key facts, constitutional provisions, data points, schemes, and recent developments.
Use bullet points for easy revision."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Topic: {topic}\n\nContent:\n{content[:3000]}"},
        ]

        try:
            response = await gateway.complete(
                messages=messages, temperature=0.2, max_tokens=512, use_cache=True,
            )
            return response.content
        except Exception as exc:
            logger.warning("[NOTES] LLM summary failed: %s", exc)
            return f"Summary of {topic}: {content[:300]}..."

    def _generate_mindmap(
        self, topic: str, content: str, key_points: List[Dict]
    ) -> Dict[str, Any]:
        """Generate mindmap structure from key points."""
        nodes = []
        for i, kp in enumerate(key_points[:8]):
            if isinstance(kp, dict):
                point = kp.get("point", str(kp))
                category = kp.get("category", "concept")
            else:
                point = str(kp)
                category = "concept"
            nodes.append({
                "id": f"node-{i+1}",
                "label": point[:60],
                "category": category,
            })

        return {
            "central_node": topic,
            "branches": [
                {"label": "Key Concepts", "nodes": [n for n in nodes if n["category"] == "concept"][:3]},
                {"label": "Facts & Data", "nodes": [n for n in nodes if n["category"] in ("fact", "data")][:3]},
                {"label": "Provisions", "nodes": [n for n in nodes if n["category"] in ("amendment", "article")][:2]},
                {"label": "Schemes & Programs", "nodes": [n for n in nodes if n["category"] == "scheme"][:2]},
            ],
            "all_nodes": nodes,
        }

    def _fallback_key_points(self, content: str) -> List[Dict[str, Any]]:
        """Fallback key point extraction without LLM."""
        lines = content.split('\n')
        key_points = []
        for line in lines:
            line = line.strip()
            if line and len(line) > 20 and len(line) < 200:
                clean = line.lstrip('#-*• ').strip()
                if clean and not clean.startswith('http'):
                    key_points.append({
                        "point": clean,
                        "importance": "medium",
                        "category": "concept",
                        "upsc_relevance": "GS",
                    })
        return key_points[:10]

    def _fallback_flashcards(self, content: str, topic: str) -> List[Dict[str, str]]:
        """Fallback flashcard generation without LLM."""
        return [
            {
                "front": f"What is the significance of {topic} for UPSC?",
                "back": f"{topic} is a critical topic for UPSC preparation, relevant for both Prelims and Mains.",
                "difficulty": "medium",
            },
            {
                "front": f"Key constitutional provisions related to {topic}",
                "back": "Important articles and amendments form the foundation of this topic.",
                "difficulty": "medium",
            },
        ]
