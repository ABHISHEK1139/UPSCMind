"""
Hermes V2 — Audit Logger
═══════════════════════════════════════════════════════════════
Structured audit logging for compliance and debugging.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = Path("data/audit_logs.jsonl")


class AuditLogger:
    """Structured audit logger."""

    def __init__(self, log_path: str | Path = AUDIT_LOG_PATH) -> None:
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._enabled = os.getenv("GOVERNANCE_AUDIT_LOG_ENABLED", "true").lower() == "true"

    def log(
        self,
        event: str,
        agent_id: str = "system",
        details: Optional[Dict[str, Any]] = None,
        session_id: str = "",
    ) -> None:
        """Write an audit log entry."""
        if not self._enabled:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "agent_id": agent_id,
            "session_id": session_id,
            "details": details or {},
        }
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.error("[AUDIT] Failed to write log: %s", exc)

    def log_answer_generated(
        self,
        session_id: str,
        question: str,
        domain: str,
        score: float,
        cost_usd: float,
        latency_ms: float,
    ) -> None:
        """Log an answer generation event."""
        self.log(
            event="answer.generated",
            session_id=session_id,
            details={
                "question": question[:200],
                "domain": domain,
                "critique_score": score,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
            },
        )

    def log_feedback_received(
        self, session_id: str, rating: int, corrections: Optional[str]
    ) -> None:
        """Log a feedback event."""
        self.log(
            event="feedback.received",
            session_id=session_id,
            details={"rating": rating, "has_corrections": corrections is not None},
        )
