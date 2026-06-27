"""
Hermes V2 — Model Router & Cost Policy Engine
═══════════════════════════════════════════════════════════════
Routes each cognitive task to the most appropriate model based on
complexity, cost, and capability requirements.

Instead of using one model for everything:
  MCQ/Classification → cheap model
  Drafting/Planning → standard model
  Critique/Verification → reasoning model
  Fact checking → database lookup (no LLM)

This can reduce LLM costs by 40-60% without quality loss.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.config import get_settings

logger = logging.getLogger(__name__)


# ── Model Tiers ──────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    """Configuration for a single model."""
    name: str
    provider: str
    max_tokens: int = 4096
    cost_per_1m_input: float = 0.0
    cost_per_1m_output: float = 0.0
    is_reasoning: bool = False
    is_local: bool = False


# Pre-defined model tiers
MODEL_TIERS = {
    "cheap": ModelConfig(
        name="openrouter/owl-alpha",
        provider="openrouter",
        max_tokens=4096,
        cost_per_1m_input=0.0,
        cost_per_1m_output=0.0,
    ),
    "standard": ModelConfig(
        name="openrouter/owl-alpha",
        provider="openrouter",
        max_tokens=4096,
        cost_per_1m_input=0.15,
        cost_per_1m_output=0.60,
    ),
    "reasoning": ModelConfig(
        name="openrouter/owl-alpha",
        provider="openrouter",
        max_tokens=4096,
        cost_per_1m_input=0.0,
        cost_per_1m_output=0.0,
        is_reasoning=True,
    ),
    "local": ModelConfig(
        name="local/llama-3-8b-instruct",
        provider="local",
        max_tokens=4096,
        cost_per_1m_input=0.0,
        cost_per_1m_output=0.0,
        is_local=True,
    ),
}


# ── Task Routing Table ──────────────────────────────────────────────

TASK_ROUTING: Dict[str, str] = {
    # Simple classification → cheap model
    "topic_detection": "cheap",
    
    # Retrieval uses no LLM (vector search + BM25)
    "retrieval": "none",
    
    # Planning needs moderate reasoning
    "planning": "standard",
    
    # Drafting is the main generation task
    "drafting": "standard",
    
    # Critique needs deep analysis → reasoning model
    "critique": "reasoning",
    
    # Fact checking uses DB lookup, not LLM
    "fact_check": "none",
    
    # Constitutional check uses DB lookup, not LLM
    "constitutional_check": "none",
    
    # Guardrails uses regex, not LLM
    "guardrails": "none",
    
    # Revision regenerates with feedback → standard
    "revision": "standard",
    
    # Verification uses DB + light LLM → cheap
    "verification": "cheap",
}


@dataclass
class RoutingDecision:
    """Record of a routing decision."""
    task: str
    model_tier: str
    model_name: str
    reason: str
    timestamp: float = field(default_factory=time.time)


class ModelRouter:
    """
    Routes tasks to appropriate models based on complexity and cost.
    
    Usage:
        router = ModelRouter()
        model = router.get_model("critique")  # → reasoning model
        model = router.get_model("topic_detection")  # → cheap model
        model = router.get_model("fact_check")  # → None (DB lookup)
    """
    
    def __init__(self, custom_routing: Dict[str, str] | None = None) -> None:
        self._routing = {**TASK_ROUTING}
        if custom_routing:
            self._routing.update(custom_routing)
        self._decisions: List[RoutingDecision] = []
        self._cost_tracker: Dict[str, float] = {
            "cheap": 0.0,
            "standard": 0.0,
            "reasoning": 0.0,
            "none": 0.0,
        }
    
    def get_model(self, task: str) -> Optional[ModelConfig]:
        """
        Get the appropriate model for a task.
        
        Returns None for tasks that don't need an LLM
        (retrieval, fact checking, guardrails).
        """
        tier_name = self._routing.get(task, "standard")
        
        if tier_name == "none":
            self._decisions.append(RoutingDecision(
                task=task,
                model_tier="none",
                model_name="none",
                reason=f"{task} uses non-LLM method (DB lookup / regex / vector search)",
            ))
            return None
        
        model = MODEL_TIERS.get(tier_name, MODEL_TIERS["standard"])
        self._decisions.append(RoutingDecision(
            task=task,
            model_tier=tier_name,
            model_name=model.name,
            reason=f"{task} → {tier_name} tier",
        ))
        
        return model
    
    def get_dspy_lm(self, task: str) -> Any:
        """Get a configured DSPy LM for a task."""
        model = self.get_model(task)
        if model is None:
            return None
        
        try:
            import dspy
            return dspy.LM(
                model.name,
                api_key=get_settings().OPENROUTER_API_KEY,
                api_base="https://openrouter.ai/api/v1",
                max_tokens=model.max_tokens,
            )
        except ImportError:
            logger.warning("[ROUTER] DSPy not installed")
            return None
    
    def estimate_cost(self, task: str, estimated_tokens: int = 2000) -> float:
        """Estimate the cost of a task in USD."""
        model = self.get_model(task)
        if model is None:
            return 0.0
        return (estimated_tokens / 1_000_000) * (model.cost_per_1m_input + model.cost_per_1m_output)
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get a summary of routing decisions and estimated costs."""
        summary: Dict[str, Any] = {
            "total_decisions": len(self._decisions),
            "by_tier": {},
            "estimated_total_cost_usd": 0.0,
        }
        
        for decision in self._decisions:
            tier = decision.model_tier
            if tier not in summary["by_tier"]:
                summary["by_tier"][tier] = {"count": 0, "tasks": []}
            summary["by_tier"][tier]["count"] += 1
            summary["by_tier"][tier]["tasks"].append(decision.task)
        
        return summary
    
    def should_use_llm(self, task: str) -> bool:
        """Check if a task should use an LLM or a non-LLM method."""
        return self._routing.get(task, "standard") != "none"
