"""
Hermes V2 — Agent Registry & Permissions
═══════════════════════════════════════════════════════════════
Manages agent permissions, resource usage, and inter-agent
communication policies.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class AgentPermission:
    """Permissions for a single agent."""

    agent_id: str
    allowed_tools: Set[str] = field(default_factory=set)
    max_tokens_per_run: int = 8000
    max_cost_per_run_usd: float = 0.05
    can_access_neo4j: bool = True
    can_access_qdrant: bool = True
    can_call_llm: bool = True
    can_write_files: bool = False
    can_access_web: bool = False


class AgentRegistry:
    """Manages agent registration, permissions, and resource tracking."""

    def __init__(self) -> None:
        self._agents: Dict[str, AgentPermission] = {}
        self._resource_usage: Dict[str, Dict[str, Any]] = {}

    def register_agent(
        self,
        agent_id: str,
        permissions: Optional[AgentPermission] = None,
    ) -> AgentPermission:
        """Register an agent with permissions."""
        if permissions is None:
            permissions = AgentPermission(agent_id=agent_id)
        self._agents[agent_id] = permissions
        self._resource_usage[agent_id] = {
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_runs": 0,
            "last_run": None,
        }
        logger.info("[GOVERNANCE] Registered agent: %s", agent_id)
        return permissions

    def check_permission(self, agent_id: str, tool: str) -> bool:
        """Check if an agent is allowed to use a tool."""
        agent = self._agents.get(agent_id)
        if agent is None:
            logger.warning("[GOVERNANCE] Unknown agent: %s", agent_id)
            return False
        return tool in agent.allowed_tools or len(agent.allowed_tools) == 0

    def record_usage(
        self,
        agent_id: str,
        tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record resource usage for an agent."""
        usage = self._resource_usage.get(agent_id)
        if usage is None:
            return
        usage["total_tokens"] += tokens
        usage["total_cost_usd"] += cost_usd
        usage["total_runs"] += 1
        usage["last_run"] = time.time()

        agent = self._agents.get(agent_id)
        if agent and cost_usd > agent.max_cost_per_run_usd:
            logger.warning(
                "[GOVERNANCE] Agent %s exceeded cost budget: %.4f > %.4f",
                agent_id, cost_usd, agent.max_cost_per_run_usd,
            )

    def get_usage(self, agent_id: str) -> Dict[str, Any]:
        """Get resource usage for an agent."""
        return self._resource_usage.get(agent_id, {})

    def get_all_usage(self) -> Dict[str, Dict[str, Any]]:
        """Get resource usage for all agents."""
        return dict(self._resource_usage)

    def list_agents(self) -> List[str]:
        """List all registered agent IDs."""
        return list(self._agents.keys())
