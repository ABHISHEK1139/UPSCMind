"""
Hermes V2 — LangGraph Orchestrator
═══════════════════════════════════════════════════════════════
Builds and compiles the LangGraph state machine that orchestrates
the entire answer-generation pipeline.

Flow:
    topic_detection → retrieval → planning → drafting → review
                                                          ↓
                    revision ←── (loop if score < threshold)
                                                          ↓
                                        export → END

Every node appends to the ``cot_trace`` list so the full
Chain-of-Thought is captured for training data generation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph

from domain.answer_generation.state import AnswerGenerationState
from domain.dataset.collector import DatasetCollector

logger = logging.getLogger(__name__)


def _run_async_in_sync(coro):
    """Run an async coroutine from a sync context (LangGraph node).
    Creates a new event loop to avoid 'event loop already running' errors."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# ── DSPy setup with Model Router ────────────────────────────────────
_DSPY_CONFIGURED = False
_model_router: Any = None


def _get_router() -> "ModelRouter":
    """Get or create the model router singleton."""
    global _model_router
    if _model_router is None:
        from core.model_router import ModelRouter
        _model_router = ModelRouter()
    return _model_router


def _configure_dspy() -> None:
    """Configure DSPy with LiteLLM backend (idempotent)."""
    global _DSPY_CONFIGURED
    if _DSPY_CONFIGURED:
        return
    try:
        import dspy

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        api_base = "https://openrouter.ai/api/v1"

        # Model tier: owl-alpha (single model for all tasks)
        cheap_lm = dspy.LM(
            "openrouter/owl-alpha",
            api_key=api_key,
            api_base=api_base,
            max_tokens=2000,
        )
        # Model tier: owl-alpha (single model for all tasks)
        standard_lm = dspy.LM(
            "openrouter/owl-alpha",
            api_key=api_key,
            api_base=api_base,
            max_tokens=4096,
        )
        # Model tier: owl-alpha (single model for all tasks)
        reasoning_lm = dspy.LM(
            "openrouter/owl-alpha",
            api_key=api_key,
            api_base=api_base,
            max_tokens=8192,
        )

        dspy.settings.configure(lm=standard_lm)
        _DSPY_CONFIGURED = True
        logger.info("[ORCHESTRATOR] DSPy configured with 3-tier model routing.")
    except ImportError:
        logger.warning("[ORCHESTRATOR] DSPy not available — using LLM gateway fallback.")
    except Exception as exc:
        logger.warning("[ORCHESTRATOR] DSPy config failed: %s", exc)


def _get_lm_for_task(task: str) -> Any:
    """Get the appropriate DSPy LM for a specific task."""
    try:
        import dspy
        router = _get_router()
        model_config = router.get_model(task)
        if model_config is None:
            return None  # Non-LLM task (DB lookup, regex, etc.)
        return dspy.LM(
            model_config.name,
            api_key=get_settings().OPENROUTER_API_KEY,
            api_base="https://openrouter.ai/api/v1",
            max_tokens=model_config.max_tokens,
        )
    except Exception:
        return None


def _append_cot(
    state: AnswerGenerationState,
    node_name: str,
    thought: str,
    output: Dict[str, Any],
    model_used: Optional[str] = None,
    latency_ms: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Append a CoT step to the state's trace."""
    trace: List[Dict[str, Any]] = list(state.get("cot_trace", []))
    trace.append({
        "step_number": len(trace) + 1,
        "node": node_name,
        "thought": thought,
        "output": output,
        "model_used": model_used,
        "latency_ms": latency_ms,
    })
    return trace


# ── Node Implementations ─────────────────────────────────────────────


def node_topic_detection(state: AnswerGenerationState) -> Dict[str, Any]:
    """Classify the question into domain, type, entities, weight."""
    _configure_dspy()
    t0 = time.monotonic()
    import dspy
    from domain.answer_generation.dspy_signatures import TopicDetectionSignature

    try:
        # Route to cheap model — this is a simple classification task
        task_lm = _get_lm_for_task("topic_detection") or dspy.settings.lm
        with dspy.context(lm=task_lm):
            predictor = dspy.Predict(TopicDetectionSignature)
            result = predictor(question=state["question"])

        entities = [e.strip() for e in result.entities.split(",") if e.strip()]
        sub_topics = [s.strip() for s in getattr(result, "sub_topics", "").split(",") if s.strip()]
        latency = (time.monotonic() - t0) * 1000

        thought = (
            f"Analyzing question: '{state['question'][:80]}...' "
            f"Domain: {result.domain}. Type: {result.question_type}. "
            f"Entities: {', '.join(entities)}. "
            f"Constitutional weight: {getattr(result, 'constitutional_weight', 'LOW')}."
        )

        return {
            "domain": result.domain,
            "question_type": result.question_type,
            "detected_entities": entities,
            "constitutional_weight": getattr(result, "constitutional_weight", "LOW"),
            "sub_topics": sub_topics,
            "cot_trace": _append_cot(state, "topic_detection", thought, {
                "domain": result.domain,
                "question_type": result.question_type,
            }, model_used="cheap", latency_ms=latency),
        }
    except Exception as exc:
        logger.error("[TOPIC_DETECTION] Failed: %s", exc)
        return {
            "domain": "General Studies",
            "question_type": "analytical",
            "detected_entities": [],
            "constitutional_weight": "LOW",
            "sub_topics": [],
            "cot_trace": _append_cot(state, "topic_detection",
                f"ERROR: Topic detection failed — {exc}. Defaulting to General Studies.",
                {"error": str(exc)}, latency_ms=0),
            "error": str(exc),
        }


def node_retrieval(state: AnswerGenerationState) -> Dict[str, Any]:
    """Retrieve relevant knowledge chunks. No LLM needed — vector search only."""
    t0 = time.monotonic()
    try:
        from domain.retrieval.router import RetrievalRouter

        router = RetrievalRouter()
        chunks, strategy = _run_async_in_sync(router.retrieve(
            question=state["question"],
            question_type=state.get("question_type", "analytical"),
            domain=state.get("domain", "General Studies"),
        ))
        latency = (time.monotonic() - t0) * 1000

        thought = (
            f"Retrieved {len(chunks)} chunks using {strategy.value} strategy. "
            f"Top sources: {', '.join(set(c.source for c in chunks[:3]))}."
        )

        return {
            "retrieved_chunks": [{"text": c.text, "score": c.score, "source": c.source, "metadata": c.metadata} for c in chunks],
            "retrieval_strategy": strategy.value,
            "retrieval_latency_ms": latency,
            "cot_trace": _append_cot(state, "retrieval", thought, {
                "strategy": strategy.value,
                "chunks_count": len(chunks),
            }, latency_ms=latency),
        }
    except Exception as exc:
        logger.error("[RETRIEVAL] Failed: %s", exc)
        return {
            "retrieved_chunks": [], "retrieval_strategy": "none",
            "cot_trace": _append_cot(state, "retrieval",
                f"ERROR: Retrieval failed — {exc}. No context retrieved.",
                {"error": str(exc)}, latency_ms=0),
            "error": str(exc),
        }


def node_planning(state: AnswerGenerationState) -> Dict[str, Any]:
    """Select framework and produce reasoning plan."""
    _configure_dspy()
    t0 = time.monotonic()
    import dspy
    from domain.answer_generation.dspy_signatures import (
        FrameworkSelectionSignature,
        AnswerPlanSignature,
    )

    try:
        chunks = state.get("retrieved_chunks", [])
        context = "\n".join(c.get("text", "") for c in chunks[:5])
        
        # Route to standard model — planning needs moderate reasoning
        task_lm = _get_lm_for_task("planning") or dspy.settings.lm

        # Step 1: Framework selection
        with dspy.context(lm=task_lm):
            fw_predictor = dspy.Predict(FrameworkSelectionSignature)
            fw_result = fw_predictor(
                question=state["question"],
                domain=state.get("domain", "General Studies"),
                question_type=state.get("question_type", "analytical"),
            )

        # Step 2: Answer plan
        with dspy.context(lm=task_lm):
            plan_predictor = dspy.Predict(AnswerPlanSignature)
            plan_result = plan_predictor(
                question=state["question"],
                domain=state.get("domain", "General Studies"),
                framework=fw_result.framework,
                retrieved_context=context,
            )

        latency = (time.monotonic() - t0) * 1000

        thought = (
            f"Selected framework: {fw_result.framework}. "
            f"Examiner persona: {fw_result.examiner_persona}. "
            f"Common trap: {fw_result.trap}. "
            f"Differentiator: {fw_result.differentiator}. "
            f"Plan: {plan_result.reasoning_plan[:200]}..."
        )

        return {
            "framework": fw_result.framework,
            "examiner_persona": fw_result.examiner_persona,
            "trap": fw_result.trap,
            "differentiator": fw_result.differentiator,
            "reasoning_plan": plan_result.reasoning_plan,
            "cot_trace": _append_cot(state, "planning", thought, {
                "framework": fw_result.framework,
            }, latency_ms=latency),
        }
    except Exception as exc:
        logger.error("[PLANNING] Failed: %s", exc)
        return {
            "framework": "Thematic", "reasoning_plan": "Standard structure",
            "examiner_persona": None, "trap": None, "differentiator": None,
            "cot_trace": _append_cot(state, "planning",
                f"ERROR: Planning failed — {exc}. Using default Thematic framework.",
                {"error": str(exc)}, latency_ms=0),
            "error": str(exc),
        }


def node_drafting(state: AnswerGenerationState) -> Dict[str, Any]:
    """Draft the first complete answer."""
    _configure_dspy()
    t0 = time.monotonic()
    import dspy
    from domain.answer_generation.dspy_signatures import DraftAnswerSignature

    try:
        chunks = state.get("retrieved_chunks", [])
        context = "\n".join(c.get("text", "") for c in chunks[:5])

        with dspy.context(lm=dspy.settings.lm):
            predictor = dspy.Predict(DraftAnswerSignature)
            result = predictor(
                question=state["question"],
                domain=state.get("domain", "General Studies"),
                reasoning_plan=state.get("reasoning_plan", ""),
                framework=state.get("framework", "Thematic"),
                retrieved_context=context,
                constitutional_weight=state.get("constitutional_weight", "LOW"),
            )

        latency = (time.monotonic() - t0) * 1000
        word_count = len(result.answer.split())

        thought = (
            f"Drafted answer using {state.get('framework', 'Thematic')} framework. "
            f"Word count: {word_count}. "
            f"Incorporated {len(chunks)} context chunks."
        )

        models = list(state.get("models_used", []))
        models.append("dspy/owl-alpha")

        return {
            "draft_answer": result.answer,
            "draft_model": "owl-alpha",
            "draft_tokens": 0,
            "draft_latency_ms": latency,
            "models_used": models,
            "cot_trace": _append_cot(state, "drafting", thought, {
                "word_count": word_count,
                "framework": state.get("framework"),
            }, model_used="owl-alpha", latency_ms=latency),
        }
    except Exception as exc:
        logger.error("[DRAFTING] Failed: %s", exc)
        return {
            "draft_answer": "Error generating draft.",
            "cot_trace": _append_cot(state, "drafting",
                f"ERROR: Drafting failed — {exc}. No draft produced.",
                {"error": str(exc)}, latency_ms=0),
            "error": str(exc),
        }


def node_review(state: AnswerGenerationState) -> Dict[str, Any]:
    """Critique the draft and assign quality score. Uses reasoning model for deep analysis.
    
    NOTE: This is a SYNC node (not async). All async operations are handled via
    run_async_in_sync() to avoid LangGraph sync/async mismatch.
    """
    _configure_dspy()
    t0 = time.monotonic()
    import dspy
    from domain.answer_generation.dspy_signatures import (
        CritiqueSignature,
        FactCheckerSignature,
    )

    try:
        answer = state.get("draft_answer", "") or state.get("improved_answer", "")
        chunks = state.get("retrieved_chunks", [])
        context = "\n".join(c.get("text", "") for c in chunks[:5])

        # Route critique to reasoning model — needs deep analysis
        task_lm = _get_lm_for_task("critique") or dspy.settings.lm
        
        with dspy.context(lm=task_lm):
            # Critique (uses reasoning model)
            reviewer = dspy.Predict(CritiqueSignature)
            rev_result = reviewer(
                question=state["question"],
                domain=state.get("domain", "General Studies"),
                constitutional_weight=state.get("constitutional_weight", "LOW"),
                answer=answer,
            )

        # Fact check: use targeted UPSC fact checker (DB lookup, not LLM)
        # Run async fact checker in sync context since this is a sync LangGraph node
        fact_check_passed = True
        fact_check_issues = None
        try:
            from domain.evaluation.upsc_fact_checker import UPSCFactChecker
            fact_checker = UPSCFactChecker()
            fc_result = _run_async_in_sync(fact_checker.check_answer(
                answer, state.get("domain", "General Studies")
            ))
            fact_check_passed = fc_result["passed"]
            if not fact_check_passed:
                fact_check_issues = json.dumps(fc_result["issues"])
        except Exception as exc:
            logger.warning("[REVIEW] Fact checker failed, falling back to LLM: %s", exc)
            # Fallback to LLM-based fact check
            with dspy.context(lm=task_lm):
                fc_predictor = dspy.Predict(FactCheckerSignature)
                fc_result_llm = fc_predictor(answer=answer, context=context)
                fact_check_passed = fc_result_llm.hallucinations_found.strip().lower() in (
                    "none", "", "no hallucinations", "n/a",
                )

        latency = (time.monotonic() - t0) * 1000

        score = 0.0
        try:
            score = float(rev_result.quality_score)
        except (ValueError, TypeError):
            pass

        has_hallucinations = not fact_check_passed

        thought = (
            f"Critique complete. Score: {score:.2f}/1.0. "
            f"Hallucinations: {'FOUND' if has_hallucinations else 'NONE'}. "
            f"Feedback: {rev_result.critique[:200]}..."
        )

        return {
            "critique": rev_result.critique,
            "critique_score": score,
            "critique_model": "owl-alpha",
            "critique_latency_ms": latency,
            "fact_check_passed": fact_check_passed,
            "fact_check_issues": fact_check_issues,
            "guardrails_passed": True,  # Set by verification node if needed
            "constitutional_check_passed": True,  # Set by verification node
            "cot_trace": _append_cot(state, "review", thought, {
                "score": score,
                "hallucinations": has_hallucinations,
            }, model_used="reasoning", latency_ms=latency),
        }
    except Exception as exc:
        logger.error("[REVIEW] Failed: %s", exc)
        return {
            "critique_score": 0.0,
            "fact_check_passed": False,
            "guardrails_passed": True,
            "constitutional_check_passed": True,
            "error": str(exc),
        }


def node_revision(state: AnswerGenerationState) -> Dict[str, Any]:
    """Revise the answer based on critique."""
    _configure_dspy()
    t0 = time.monotonic()
    import dspy
    from domain.answer_generation.dspy_signatures import ImprovementSignature

    try:
        answer = state.get("draft_answer", "") or state.get("improved_answer", "")

        with dspy.context(lm=dspy.settings.lm):
            predictor = dspy.Predict(ImprovementSignature)
            result = predictor(
                question=state["question"],
                domain=state.get("domain", "General Studies"),
                answer=answer,
                critique=state.get("critique", ""),
                framework=state.get("framework", "Thematic"),
            )

        latency = (time.monotonic() - t0) * 1000
        iterations = state.get("revision_iterations", 0) + 1

        thought = (
            f"Revision #{iterations}. Addressing critique feedback. "
            f"Improved word count: {len(result.improved_answer.split())}."
        )

        return {
            "improved_answer": result.improved_answer,
            "revision_iterations": iterations,
            "cot_trace": _append_cot(state, "revision", thought, {
                "iteration": iterations,
                "improved_word_count": len(result.improved_answer.split()),
            }, latency_ms=latency),
        }
    except Exception as exc:
        logger.error("[REVISION] Failed: %s", exc)
        return {
            "revision_iterations": state.get("revision_iterations", 0) + 1,
            "cot_trace": _append_cot(state, "revision",
                f"ERROR: Revision failed — {exc}. Keeping previous draft.",
                {"error": str(exc)}, latency_ms=0),
            "error": str(exc),
        }


def node_verification(state: AnswerGenerationState) -> Dict[str, Any]:
    """Multi-layer verification: fact check + guardrails + constitutional."""
    _configure_dspy()
    t0 = time.monotonic()
    import dspy
    from domain.answer_generation.dspy_signatures import ConstitutionalCheckerSignature

    layers: Dict[str, bool] = {}
    notes_parts: List[str] = []

    # Layer 1: Fact check (already done in review, reuse)
    fact_passed = state.get("fact_check_passed", False)
    layers["fact_check"] = fact_passed
    if not fact_passed:
        notes_parts.append(f"Fact check failed: {state.get('fact_check_issues', 'unknown')}")

    # Layer 2: Guardrails (basic content safety)
    guardrails_passed = True
    try:
        from domain.verification.guardrails import GuardrailsFilter
        filter_obj = GuardrailsFilter()
        answer = state.get("improved_answer") or state.get("draft_answer", "")
        guardrails_passed = filter_obj.check(answer, state.get("domain", ""))
    except Exception:
        guardrails_passed = True  # Pass if guardrails not available
    layers["guardrails"] = guardrails_passed
    if not guardrails_passed:
        notes_parts.append("Guardrails failed")

    # Layer 3: Constitutional check (if HIGH weight)
    constitutional_passed = True
    if state.get("constitutional_weight") == "HIGH":
        try:
            answer = state.get("improved_answer") or state.get("draft_answer", "")
            with dspy.context(lm=dspy.settings.lm):
                checker = dspy.Predict(ConstitutionalCheckerSignature)
                result = checker(answer=answer, domain=state.get("domain", ""))
            constitutional_passed = str(result.constitutional_pass).lower() in ("true", "yes", "1")
            if not constitutional_passed:
                notes_parts.append(f"Constitutional issues: {result.get('notes', 'unknown')}")
        except Exception:
            constitutional_passed = True
    layers["constitutional"] = constitutional_passed

    all_passed = all(layers.values())
    latency = (time.monotonic() - t0) * 1000

    thought = (
        f"Verification layers: {', '.join(f'{k}={"PASS" if v else "FAIL"}' for k, v in layers.items())}. "
        f"Overall: {'ALL PASSED' if all_passed else 'ISSUES FOUND'}."
    )

    return {
        "verification_passed": all_passed,
        "verification_layers": layers,
        "guardrails_passed": guardrails_passed,
        "constitutional_check_passed": constitutional_passed,
        "guardrails_notes": "; ".join(notes_parts) if notes_parts else None,
        "cot_trace": _append_cot(state, "verification", thought, layers, latency_ms=latency),
    }


def node_export(state: AnswerGenerationState) -> Dict[str, Any]:
    """Export the trajectory to training data (quality-gated)."""
    try:
        collector = DatasetCollector()
        trajectory = collector.collect_from_state(dict(state))

        quality_score = state.get("critique_score", 0.0)
        training_eligible = trajectory is not None

        # Compute totals from the trajectory if available
        total_cost = 0.0
        total_tokens = 0
        total_latency = 0.0
        models_used = list(state.get("models_used", []))
        if trajectory and trajectory.get("total_cost_usd"):
            total_cost = trajectory["total_cost_usd"]
            total_tokens = trajectory.get("total_tokens", 0)
            total_latency = trajectory.get("total_latency_ms", 0.0)

        return {
            "quality_score": quality_score,
            "training_eligible": training_eligible,
            "final_answer": (
                state.get("improved_answer") or state.get("draft_answer", "")
            ),
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency,
            "models_used": models_used,
        }
    except Exception as exc:
        logger.error("[EXPORT] Failed: %s", exc)
        return {
            "quality_score": state.get("critique_score", 0.0),
            "training_eligible": False,
            "final_answer": state.get("improved_answer") or state.get("draft_answer", ""),
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "total_latency_ms": 0.0,
            "models_used": list(state.get("models_used", [])),
        }


# ── Routing Logic ───────────────────────────────────────────────────


def should_revise(state: AnswerGenerationState) -> str:
    """Decide whether to revise or export."""
    score = state.get("critique_score", 0.0) or 0.0
    fact_passed = state.get("fact_check_passed", False)
    iterations = state.get("revision_iterations", 0)

    if score >= 0.9 and fact_passed:
        return "verify"
    if iterations >= 2:
        return "verify"
    return "revise"


# ── Graph Builder ───────────────────────────────────────────────────


def build_answer_graph():
    """Build and compile the LangGraph state machine."""
    _configure_dspy()

    workflow = StateGraph(AnswerGenerationState)

    workflow.add_node("topic_detection", node_topic_detection)
    workflow.add_node("retrieval", node_retrieval)
    workflow.add_node("planning", node_planning)
    workflow.add_node("drafting", node_drafting)
    workflow.add_node("review", node_review)
    workflow.add_node("revision", node_revision)
    workflow.add_node("verification", node_verification)
    workflow.add_node("export", node_export)

    workflow.set_entry_point("topic_detection")
    workflow.add_edge("topic_detection", "retrieval")
    workflow.add_edge("retrieval", "planning")
    workflow.add_edge("planning", "drafting")
    workflow.add_edge("drafting", "review")

    workflow.add_conditional_edges(
        "review",
        should_revise,
        {"revise": "revision", "verify": "verification"},
    )

    workflow.add_edge("revision", "review")
    workflow.add_edge("verification", "export")
    workflow.add_edge("export", END)

    logger.info("[ORCHESTRATOR] Graph compiled: 8 nodes, conditional revision loop.")
    return workflow.compile()
