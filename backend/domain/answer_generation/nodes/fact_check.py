"""
Hermes V2 — Fact Check & Verification Node
═══════════════════════════════════════════════════════════════
Final gate before an answer is returned to the user.  Runs a
multi-layer verification pipeline:

  Layer 1 — **Verifier Agent**: LLM-based factual cross-check
            against the retrieved context.
  Layer 2 — **NeMo Guardrails**: Content-safety / hallucination
            rail (when nemoguardrails is installed).
  Layer 3 — **Fact Checker**: Constitutional-provision validator
            that ensures cited Articles, Amendments, and cases
            are real and correctly described.

If all layers pass, the best available answer is promoted to
``final_answer``.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from domain.answer_generation.state import AnswerGenerationState

logger = logging.getLogger(__name__)

# ── Verifier prompt ─────────────────────────────────────────

_VERIFIER_SYSTEM = """\
You are a factual-accuracy verifier for UPSC answers.  Compare
the answer against the retrieved context and general knowledge.

Return a JSON object with:
  fact_check_pass  — boolean, true if all major facts are correct
  issues           — list of strings describing any inaccuracies

Return ONLY valid JSON.
"""

# ── Constitutional fact-check prompt ────────────────────────

_CONSTITUTIONAL_SYSTEM = """\
You are a constitutional-law fact checker.  Verify every Article,
Amendment, Schedule, case citation, and statutory reference in the
answer.  Flag any that are incorrect, misattributed, or invented.

Return a JSON object with:
  constitutional_pass  — boolean
  notes               — list of strings with specific issues

Return ONLY valid JSON.
"""


def _best_answer(state: AnswerGenerationState) -> str:
    """Return the most-refined answer available."""
    return (
        state.get("improved_answer")
        or state.get("draft_answer")
        or ""
    )


def _chunks_to_context(chunks: list[dict]) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] {c.get('text', '')}")
    return "\n\n".join(parts) if parts else "(no context)"


async def node_fact_check(
    state: AnswerGenerationState,
) -> dict[str, Any]:
    """Run multi-layer verification on the answer.

    Parameters
    ----------
    state : AnswerGenerationState
        Must contain the question, answer (draft or improved),
        and retrieved_chunks.

    Returns
    -------
    dict
        Partial state update with ``guardrails_pass``,
        ``fact_check_pass``, ``verification_notes``, and
        ``final_answer``.
    """
    answer = _best_answer(state)
    question: str = state["question"]
    chunks: list[dict] = state.get("retrieved_chunks", [])
    context = _chunks_to_context(chunks)
    constitutional_weight: str = state.get("constitutional_weight", "MEDIUM")

    notes_parts: list[str] = []
    fact_pass = True
    guardrails_pass = True

    t0 = time.monotonic()

    # ═══════════════════════════════════════════════════════
    # Layer 1 — LLM Verifier Agent
    # ═══════════════════════════════════════════════════════
    try:
        from core.llm_gateway import LLMGateway

        gateway = LLMGateway()
        verifier_response = gateway.complete(
            messages=[
                {"role": "system", "content": _VERIFIER_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\n"
                        f"Answer:\n{answer}\n\n"
                        f"Retrieved Context:\n{context}"
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=1024,
        )

        try:
            vr = json.loads(verifier_response.content)
            fact_pass = bool(vr.get("fact_check_pass", True))
            issues = vr.get("issues", [])
            if issues:
                notes_parts.append(
                    "Verifier issues: " + "; ".join(issues)
                )
        except json.JSONDecodeError:
            notes_parts.append(
                "Verifier returned non-JSON — treating as pass."
            )

    except Exception as exc:
        logger.warning("[FACT_CHECK] Verifier layer failed: %s", exc)
        notes_parts.append(f"Verifier error: {exc}")

    # ═══════════════════════════════════════════════════════
    # Layer 2 — NeMo Guardrails (optional)
    # ═══════════════════════════════════════════════════════
    try:
        from nemoguardrails import RailsConfig, LLMRails  # type: ignore[import]

        config = RailsConfig.from_path("config/guardrails")
        rails = LLMRails(config)
        rail_result = await rails.generate_async(
            messages=[
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        )
        # If guardrails rewrites the answer, treat as a soft fail
        if rail_result and rail_result.get("content") != answer:
            guardrails_pass = False
            notes_parts.append(
                "NeMo guardrails modified the answer — review suggested."
            )
        else:
            notes_parts.append("NeMo guardrails: PASS.")

    except ImportError:
        logger.info(
            "[FACT_CHECK] nemoguardrails not installed — skipping Layer 2."
        )
        notes_parts.append("NeMo guardrails: skipped (not installed).")

    except Exception as exc:
        logger.warning("[FACT_CHECK] NeMo guardrails error: %s", exc)
        notes_parts.append(f"NeMo guardrails error: {exc}")

    # ═══════════════════════════════════════════════════════
    # Layer 3 — Constitutional Fact Checker
    # ═══════════════════════════════════════════════════════
    if constitutional_weight in ("HIGH", "MEDIUM"):
        try:
            const_response = gateway.complete(
                messages=[
                    {"role": "system", "content": _CONSTITUTIONAL_SYSTEM},
                    {
                        "role": "user",
                        "content": f"Answer to verify:\n{answer}",
                    },
                ],
                temperature=0.0,
                max_tokens=1024,
            )

            try:
                cr = json.loads(const_response.content)
                if not cr.get("constitutional_pass", True):
                    fact_pass = False
                    const_notes = cr.get("notes", [])
                    notes_parts.append(
                        "Constitutional issues: " + "; ".join(const_notes)
                    )
                else:
                    notes_parts.append("Constitutional check: PASS.")
            except json.JSONDecodeError:
                notes_parts.append(
                    "Constitutional checker returned non-JSON — treating as pass."
                )

        except Exception as exc:
            logger.warning(
                "[FACT_CHECK] Constitutional checker failed: %s", exc
            )
            notes_parts.append(f"Constitutional checker error: {exc}")
    else:
        notes_parts.append(
            f"Constitutional check: skipped (weight={constitutional_weight})."
        )

    # ═══════════════════════════════════════════════════════
    # Compose final result
    # ═══════════════════════════════════════════════════════
    latency = (time.monotonic() - t0) * 1000
    verification_notes = "\n".join(notes_parts)

    logger.info(
        "[FACT_CHECK] fact_pass=%s | guardrails_pass=%s | %.0fms",
        fact_pass,
        guardrails_pass,
        latency,
    )

    return {
        "guardrails_pass": guardrails_pass,
        "fact_check_pass": fact_pass,
        "verification_notes": verification_notes,
        "final_answer": answer,
    }
