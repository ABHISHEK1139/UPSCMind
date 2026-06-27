"""
Hermes V2 — L5 Execution State Memory
═══════════════════════════════════════════════════════════════
Hybrid storage for orchestrator control state:

  • **Redis** — fast ephemeral read/write of current epoch position
    and task-queue state (key pattern ``es:{key}``).
  • **Postgres** — durable checkpoint rows for audit trail and
    crash-recovery (table ``execution_checkpoints``).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from core.db_redis import get_redis_client
from core.db_postgres import get_session

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS: int = 7_200  # 2 hours


class ExecutionStateMemory:
    """L5 — orchestrator epoch / task-queue state (Redis + Postgres)."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._redis = get_redis_client()

    @staticmethod
    def _redis_key(key: str) -> str:
        return f"es:{key}"

    async def save_state(self, key: str, state: dict) -> None:
        """Write a JSON-serializable state dict to Redis."""
        rkey = self._redis_key(key)
        pipe = self._redis.pipeline()
        pipe.set(rkey, json.dumps(state, default=str))
        pipe.expire(rkey, self._ttl)
        await pipe.execute()
        logger.debug("[EXEC_MEM] save_state key=%s", key)

    async def load_state(self, key: str) -> dict:
        """Load state from Redis."""
        raw = await self._redis.get(self._redis_key(key))
        if raw is None:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    async def save_checkpoint(
        self, run_id: str, node: str, state: dict
    ) -> None:
        """Persist a durable checkpoint to Postgres."""
        try:
            session = await get_session()
            from sqlalchemy import text
            await session.execute(
                text(
                    """
                    INSERT INTO execution_checkpoints (run_id, node, state, created_at)
                    VALUES (:run_id, :node, :state, :created_at)
                    """
                ),
                {
                    "run_id": run_id,
                    "node": node,
                    "state": json.dumps(state, default=str),
                    "created_at": datetime.now(timezone.utc),
                },
            )
            await session.commit()
            logger.debug("[EXEC_MEM] checkpoint saved run_id=%s node=%s", run_id, node)
        except Exception as exc:
            logger.warning("[EXEC_MEM] checkpoint save failed: %s", exc)

    async def load_latest_checkpoint(self, run_id: str) -> Optional[dict]:
        """Load the most recent checkpoint for a run."""
        try:
            session = await get_session()
            from sqlalchemy import text
            result = await session.execute(
                text(
                    """
                    SELECT node, state, created_at
                    FROM execution_checkpoints
                    WHERE run_id = :run_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"run_id": run_id},
            )
            row = result.fetchone()
            if row:
                return {
                    "node": row[0],
                    "state": json.loads(row[1]),
                    "created_at": row[2],
                }
            return None
        except Exception as exc:
            logger.warning("[EXEC_MEM] checkpoint load failed: %s", exc)
            return None
