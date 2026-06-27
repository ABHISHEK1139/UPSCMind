"""
Hermes V3 — Enhanced LangGraph Orchestrator
═══════════════════════════════════════════════════════════════
V3 pipeline with:
1. Intent + Difficulty
2. Multi-Query Retrieval
3. Enhanced Planning
4. Section Drafting
5. Multi-Reviewer
6. Evidence Verification
7. Confidence Estimation
8. Reflection Loop
"""

from __future__ import annotations

import logging
from typing import Any, Annotated

from langgraph.graph import END, StateGraph

from domain.answer_generation.nodes_v3 import (
    node_intent_and_difficulty,
    node_multi_retrieval,
    node_revision_blueprint,
    node_enhanced_planner,
    node_section_drafting,
    node_multi_reviewer,
    node_evidence_verification,
    node_confidence_estimator,
    should_revise,
)
from domain.answer_generation.upsc_blueprint import node_upsc_blueprint

logger = logging.getLogger(__name__)


def _configure_dspy():
    """DSPy configuration skipped for V3 — using direct LLMGateway calls."""
    # V3 pipeline uses LLMGateway directly, not DSPy
    pass


# ── State with merge reducer so partial updates don't lose keys ────

def _state_reducer(a, b):
    """Merge two state dicts, preserving all keys."""
    if a is None:
        return b or {}
    if b is None:
        return a or {}
    merged = dict(a)
    for k, v in b.items():
        if v is not None:
            merged[k] = v
    return merged


# Use Annotated dict with merge reducer
StateType = Annotated[dict, _state_reducer]


def build_answer_graph_v3():
    """Build and compile the V3 LangGraph state machine."""
    _configure_dspy()

    workflow = StateGraph(StateType)

    # V3 Nodes
    workflow.add_node("intent_difficulty", node_intent_and_difficulty)
    workflow.add_node("multi_retrieval", node_multi_retrieval)
    workflow.add_node("upsc_blueprint", node_upsc_blueprint)
    workflow.add_node("enhanced_planner", node_enhanced_planner)
    workflow.add_node("section_drafting", node_section_drafting)
    workflow.add_node("multi_reviewer", node_multi_reviewer)
    workflow.add_node("revision_blueprint", node_revision_blueprint)  # NEW: Structured revision
    workflow.add_node("evidence_verification", node_evidence_verification)
    workflow.add_node("confidence_estimator", node_confidence_estimator)

    # Edges
    workflow.set_entry_point("intent_difficulty")
    workflow.add_edge("intent_difficulty", "multi_retrieval")
    workflow.add_edge("multi_retrieval", "upsc_blueprint")
    workflow.add_edge("upsc_blueprint", "enhanced_planner")
    workflow.add_edge("enhanced_planner", "section_drafting")
    workflow.add_edge("section_drafting", "multi_reviewer")
    # Revision: reviewer → revision_blueprint → counter → (revise → section_drafting) OR finalize
    workflow.add_edge("multi_reviewer", "revision_blueprint")

    # Revision counter node (increments revision_iterations in state)
    def _increment_revision(state):
        return {"revision_iterations": state.get("revision_iterations", 0) + 1}

    workflow.add_node("revision_counter", _increment_revision)

    # Reflection loop: revision_blueprint → revision_counter → (revise → section_drafting → ... OR finalize)
    workflow.add_edge("revision_blueprint", "revision_counter")
    workflow.add_conditional_edges(
        "revision_counter",
        should_revise,
        {"revise": "section_drafting", "finalize": "evidence_verification"},
    )

    workflow.add_edge("evidence_verification", "confidence_estimator")
    workflow.add_edge("confidence_estimator", END)

    logger.info("[V3 ORCHESTRATOR] Graph compiled: 8 nodes, reflection loop enabled.")
    return workflow.compile()
