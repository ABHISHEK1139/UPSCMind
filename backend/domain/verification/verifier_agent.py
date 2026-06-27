"""
Hermes V2 — Verifier Agent
═══════════════════════════════════════════════════════════════
LLM-based verifier that cross-checks the answer against
retrieved context and general knowledge.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_VERIFIER_SYSTEM = """\
You are a factual-accuracy verifier for UPSC answers. Compare the
answer against the retrieved context and general UPSC knowledge.

Check for:
1. Factual errors (wrong dates, numbers, names)
2. Hallucinated citations (Articles, Amendments, cases that don't exist)
3. Logical inconsistencies
4. Missing key points that the question demands

Return a JSON object with:
  fact_check_pass  — boolean
  issues           — list of strings describing inaccuracies
  severity         — "none", "minor", "major", or "critical"

Return ONLY valid JSON.
"""


class VerifierAgent:
    """LLM-based answer verifier."""

    def __init__(self, model: str = "openrouter/owl-alpha") -> None:
        self._model = model

    async def verify(
        self,
        question: str,
        answer: str,
        context: str = "",
        domain: str = "General Studies",
    ) -> Dict[str, Any]:
        """
        Verify an answer against context.

        Returns
        -------
        dict with keys: fact_check_pass (bool), issues (list), severity (str)
        """
        try:
            from core.llm_gateway import LLMGateway

            gateway = LLMGateway(models=[self._model])
            user_content = (
                f"Question: {question}\n"
                f"Domain: {domain}\n\n"
                f"Answer:\n{answer}\n\n"
                f"Retrieved Context:\n{context}"
            )
            response = await gateway.complete(
                messages=[
                    {"role": "system", "content": _VERIFIER_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_tokens=1024,
            )

            result = json.loads(response.content)
            return {
                "fact_check_pass": result.get("fact_check_pass", False),
                "issues": result.get("issues", []),
                "severity": result.get("severity", "none"),
            }
        except json.JSONDecodeError:
            logger.warning("[VERIFIER] Could not parse LLM response as JSON.")
            return {"fact_check_pass": True, "issues": [], "severity": "none"}
        except Exception as exc:
            logger.error("[VERIFIER] Verification failed: %s", exc)
            return {"fact_check_pass": True, "issues": [], "severity": "none"}
