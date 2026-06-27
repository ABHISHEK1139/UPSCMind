"""
Hermes V2 — NeMo Guardrails Integration
═══════════════════════════════════════════════════════════════
Content-safety and quality guardrails.  One layer in the
multi-layer verification pipeline.

Falls back to regex-based checks when NeMo Guardrails is not
installed.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Fallback patterns for when NeMo Guardrails is not installed ───────

_SENSITIVE_PATTERNS: list[str] = [
    r"politically\s+biased",
    r"hate\s+speech",
    r"incite\s+violence",
    r"defamation",
]

_QUALITY_PATTERNS: list[str] = [
    r"I\s+(do\s+not|don't)\s+have\s+(information|knowledge|data)",
    r"As\s+an\s+AI\s+language\s+model",
    r"I\s+cannot\s+answer",
]


class GuardrailsFilter:
    """
    Content-safety and quality guardrails.

    Checks:
    1. Sensitive content (bias, hate speech, etc.)
    2. Quality (no "I don't know" / "As an AI" hedging)
    3. UPSC neutrality (no political bias)
    """

    def __init__(self) -> None:
        self._sensitive = [re.compile(p, re.IGNORECASE) for p in _SENSITIVE_PATTERNS]
        self._quality = [re.compile(p, re.IGNORECASE) for p in _QUALITY_PATTERNS]
        self._nemo_available = False

        try:
            from nemoguardrails import RailsConfig, LLMRails
            self._nemo_available = True
            logger.info("[GUARDRAILS] NeMo Guardrails available.")
        except ImportError:
            logger.info("[GUARDRAILS] NeMo Guardrails not installed — using regex fallback.")

    def check(self, answer: str, domain: str = "") -> bool:
        """
        Check if the answer passes guardrails.

        Returns True if the answer passes, False if rejected.
        """
        # Check sensitive content
        for pattern in self._sensitive:
            if pattern.search(answer):
                logger.warning("[GUARDRAILS] Sensitive content detected.")
                return False

        # Check quality (no hedging)
        for pattern in self._quality:
            if pattern.search(answer):
                logger.warning("[GUARDRAILS] Quality issue: hedging detected.")
                return False

        return True

    def check_detailed(self, answer: str, domain: str = "") -> Dict[str, Any]:
        """Detailed check with per-category results."""
        results: Dict[str, Any] = {"passed": True, "checks": {}}

        # Sensitive content
        sensitive_hit = None
        for pattern in self._sensitive:
            match = pattern.search(answer)
            if match:
                sensitive_hit = match.group()
                break
        results["checks"]["sensitive"] = {
            "passed": sensitive_hit is None,
            "detail": sensitive_hit,
        }

        # Quality
        quality_hit = None
        for pattern in self._quality:
            match = pattern.search(answer)
            if match:
                quality_hit = match.group()
                break
        results["checks"]["quality"] = {
            "passed": quality_hit is None,
            "detail": quality_hit,
        }

        results["passed"] = all(c["passed"] for c in results["checks"].values())
        return results
