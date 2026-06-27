"""
Hermes V2 — DSPy Signatures
═══════════════════════════════════════════════════════════════
All DSPy signatures used in the LangGraph orchestrator.
Each signature is a small, compilable, testable unit.

These signatures are used inside LangGraph nodes, NOT as a
monolithic replacement for the orchestrator.
"""

from __future__ import annotations

from typing import Optional

# ── DSPy availability check ─────────────────────────────────────────
try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False


def dspy_available() -> bool:
    """Return True if DSPy is installed and importable."""
    return DSPY_AVAILABLE


# ── Topic Detection ──────────────────────────────────────────────────

class TopicDetectionSignature(dspy.Signature):
    """Analyze a UPSC civil services question to determine its domain and core entities."""

    question = dspy.InputField(desc="The UPSC question")

    domain = dspy.OutputField(
        desc="Subject domain: Polity, Economy, History, Geography, "
             "Ethics, Science-Tech, Environment, IR, Society"
    )
    question_type = dspy.OutputField(
        desc="Type: factual, analytical, evaluative, comparison, "
             "evolution, relationship, timeline, "
             "constitutional_amendment_chain, institutional_interaction"
    )
    entities = dspy.OutputField(desc="Comma-separated core entities or keywords")
    constitutional_weight = dspy.OutputField(
        desc="HIGH if question involves Articles/Amendments/Cases, "
             "MEDIUM if tangential, LOW if none"
    )
    sub_topics = dspy.OutputField(desc="Comma-separated sub-topics")


# ── Framework Selection ──────────────────────────────────────────────

class FrameworkSelectionSignature(dspy.Signature):
    """Select the optimal answer framework for a UPSC question."""

    question = dspy.InputField()
    domain = dspy.InputField()
    question_type = dspy.InputField()

    framework = dspy.OutputField(
        desc="Framework: PESTLE, Timeline, Pro-Con, Institutional, "
             "Thematic, Cause-Effect, Comparative, Spatial"
    )
    examiner_persona = dspy.OutputField(
        desc="One-line persona of the likely evaluator"
    )
    trap = dspy.OutputField(
        desc="The most common student mistake for this question"
    )
    differentiator = dspy.OutputField(
        desc="A single non-obvious insight that elevates the answer"
    )


# ── Answer Planning ──────────────────────────────────────────────────

class AnswerPlanSignature(dspy.Signature):
    """Produce a step-by-step reasoning plan for the answer."""

    question = dspy.InputField()
    domain = dspy.InputField()
    framework = dspy.InputField()
    retrieved_context = dspy.InputField()

    reasoning_plan = dspy.OutputField(
        desc="Numbered step-by-step plan: intro strategy, body paragraph "
             "themes with evidence to cite, conclusion hook"
    )


# ── Answer Drafting ──────────────────────────────────────────────────

class DraftAnswerSignature(dspy.Signature):
    """Draft a comprehensive, well-structured UPSC answer."""

    question = dspy.InputField()
    domain = dspy.InputField()
    reasoning_plan = dspy.InputField()
    framework = dspy.InputField()
    retrieved_context = dspy.InputField()
    constitutional_weight = dspy.InputField()

    answer = dspy.OutputField(
        desc="Detailed UPSC-grade answer (800-1200 words) with "
             "headings, bullet points, and citations"
    )


# ── Critique / Review ────────────────────────────────────────────────

class CritiqueSignature(dspy.Signature):
    """Critique a drafted UPSC answer against evaluation criteria."""

    question = dspy.InputField()
    domain = dspy.InputField()
    constitutional_weight = dspy.InputField()
    answer = dspy.InputField()

    critique = dspy.OutputField(
        desc="Detailed feedback on: factual accuracy, structural coherence, "
             "depth of analysis, constitutional grounding, examples/data, "
             "conclusion quality"
    )
    quality_score = dspy.OutputField(
        desc="Float from 0.0 (unusable) to 1.0 (exceptional)"
    )


# ── Fact Checker ─────────────────────────────────────────────────────

class FactCheckerSignature(dspy.Signature):
    """Check a drafted answer against retrieved context."""

    answer = dspy.InputField()
    context = dspy.InputField()

    hallucinations_found = dspy.OutputField(
        desc="List statements that contradict context, or 'None'"
    )


# ── Constitutional Checker ───────────────────────────────────────────

class ConstitutionalCheckerSignature(dspy.Signature):
    """Verify constitutional provisions cited in the answer."""

    answer = dspy.InputField()
    domain = dspy.InputField()

    constitutional_pass = dspy.OutputField(
        desc="Boolean: true if all Articles/Amendments/cases are correct"
    )
    notes = dspy.OutputField(
        desc="List of specific issues found, or 'None'"
    )


# ── Improvement / Revision ───────────────────────────────────────────

class ImprovementSignature(dspy.Signature):
    """Revise a drafted answer incorporating critique feedback."""

    question = dspy.InputField()
    domain = dspy.InputField()
    answer = dspy.InputField()
    critique = dspy.InputField()
    framework = dspy.InputField()

    improved_answer = dspy.OutputField(
        desc="The improved final answer addressing all critique points"
    )
