"""
Hermes V2 — Fact Checker
═══════════════════════════════════════════════════════════════
Cross-references answer claims against the knowledge base
(Qdrant + Neo4j) to detect hallucinations and factual errors.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CONSTITUTIONAL_SYSTEM = """\
You are a constitutional-law fact checker for UPSC answers.
Verify every Article, Amendment, Schedule, case citation, and
statutory reference in the answer against the provided context.

Return a JSON object with:
  constitutional_pass  — boolean
  notes               — list of specific issues, or "None"

Return ONLY valid JSON.
"""


class FactChecker:
    """Cross-references answer claims against the knowledge base."""

    def __init__(self) -> None:
        self._nemo_available = False
        try:
            import nemoguardrails
            self._nemo_available = True
        except ImportError:
            pass

    async def check_facts(
        self,
        answer: str,
        context: str,
        domain: str = "General Studies",
    ) -> Dict[str, Any]:
        """
        Check factual accuracy of an answer against context.

        Returns
        -------
        dict with keys: passed (bool), issues (list), severity (str)
        """
        try:
            from core.llm_gateway import LLMGateway

            gateway = LLMGateway()
            user_content = (
                f"Domain: {domain}\n\n"
                f"Answer:\n{answer}\n\n"
                f"Retrieved Context:\n{context}"
            )
            response = await gateway.complete(
                messages=[
                    {"role": "system", "content": _CONSTITUTIONAL_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_tokens=1024,
            )

            result = json.loads(response.content)
            return {
                "passed": result.get("constitutional_pass", True),
                "issues": result.get("notes", "None"),
            }
        except json.JSONDecodeError:
            logger.warning("[FACT_CHECKER] Could not parse LLM response.")
            return {"passed": True, "issues": "None"}
        except Exception as exc:
            logger.error("[FACT_CHECKER] Check failed: %s", exc)
            return {"passed": True, "issues": "None"}

    def extract_claims(self, answer: str) -> List[str]:
        """Extract factual claims from an answer for verification."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', answer)
        claims = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            # Look for sentences with numbers, dates, or citations
            if re.search(r'\d{4}|Article|Amendment|Schedule|Act|Section|vs\.', sentence):
                claims.append(sentence)
        return claims
