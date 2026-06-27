"""
Hermes V2 — Citation Score Metric
═══════════════════════════════════════════════════════════════
Evaluates whether the answer properly cites constitutional
provisions, cases, and statutory references.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from domain.evaluation.metrics import Metric, MetricResult

logger = logging.getLogger(__name__)


class CitationScoreMetric(Metric):
    """Score based on presence and correctness of citations."""

    def name(self) -> str:
        return "citation_score"

    def evaluate(
        self,
        question: str,
        answer: str,
        context: list[str] = None,
        reference: str = None,
    ) -> MetricResult:
        score = 0.0
        details_parts = []

        # Check for Article references
        articles = re.findall(r'Article\s+\d+[A-Z]?', answer)
        if articles:
            score += 0.3
            details_parts.append(f"Articles cited: {', '.join(set(articles))}")

        # Check for Amendment references
        amendments = re.findall(r'(\d+(?:st|nd|rd|th)\s+Amendment)', answer, re.IGNORECASE)
        if amendments:
            score += 0.2
            details_parts.append(f"Amendments cited: {len(amendments)}")

        # Check for case citations (Name vs. Name pattern)
        cases = re.findall(r'\w+\s+v\.?\s+\w+', answer)
        if cases:
            score += 0.2
            details_parts.append(f"Case citations: {len(cases)}")

        # Check for Schedule references
        schedules = re.findall(r'(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth)\s+Schedule', answer)
        if schedules:
            score += 0.15
            details_parts.append(f"Schedules cited: {len(schedules)}")

        # Check for Act references
        acts = re.findall(r'\w+\s+Act,?\s+\d{4}', answer)
        if acts:
            score += 0.15
            details_parts.append(f"Acts cited: {len(acts)}")

        details = "; ".join(details_parts) if details_parts else "No citations found."
        return MetricResult(name=self.name(), score=min(score, 1.0), details=details)
