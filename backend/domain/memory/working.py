"""
Hermes V2 — L2 Working Memory
═══════════════════════════════════════════════════════════════
Scratch-pad state for a single answer-generation run, stored as a
Redis hash so individual fields can be read/written independently.

Key pattern : wm:{run_id}
Storage     : Redis hash (HSET / HGET / HGETALL)
Default TTL : 1 800 s (30 minutes)
"""

import json
import logging
from typing import Any, Optional

from core.db_redis import get_redis_client

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS: int = 1_800  # 30 minutes


class WorkingMemory:
    """L2 — transient scratch state per orchestrator run, backed by Redis hash."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._redis = get_redis_client()

    # ── helpers ──────────────────────────────────────────────
    @staticmethod
    def _key(run_id: str) -> str:
        return f"wm:{run_id}"

    @staticmethod
    def _serialize(value: Any) -> str:
        """Serialize arbitrary Python objects to a JSON string."""
        return json.dumps(value, default=str)

    @staticmethod
    def _deserialize(raw: Optional[str]) -> Any:
        """Deserialize a JSON string back to a Python object."""
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw  # return as-is if not valid JSON

    # ── public API ───────────────────────────────────────────
    async def set(self, run_id: str, key: str, value: Any) -> None:
        """Store a single key-value pair in the run's working memory.

        Args:
            run_id: Unique run / task identifier.
            key:    Field name (e.g. ``"retrieved_docs"``, ``"plan"``).
            value:  Any JSON-serializable value.
        """
        rkey = self._key(run_id)
        pipe = self._redis.pipeline()
        pipe.hset(rkey, key, self._serialize(value))
        pipe.expire(rkey, self._ttl)
        await pipe.execute()

        logger.debug("[WM] set   run=%s key=%s", run_id, key)

    async def get(self, run_id: str, key: str) -> Any:
        """Retrieve a single field from working memory.

        Returns:
            Deserialized value, or ``None`` if the field does not exist.
        """
        raw = await self._redis.hget(self._key(run_id), key)
        value = self._deserialize(raw)
        logger.debug("[WM] get   run=%s key=%s found=%s", run_id, key, raw is not None)
        return value

    async def get_all(self, run_id: str) -> dict:
        """Return the entire working-memory hash as a dict.

        Returns:
            Dict of ``{field: deserialized_value}``.  Empty dict if key
            does not exist.
        """
        raw_map: dict[str, str] = await self._redis.hgetall(self._key(run_id))
        result = {k: self._deserialize(v) for k, v in raw_map.items()}
        logger.debug("[WM] all   run=%s fields=%d", run_id, len(result))
        return result

    async def clear(self, run_id: str) -> None:
        """Delete all working-memory state for a run."""
        await self._redis.delete(self._key(run_id))
        logger.info("[WM] clear run=%s", run_id)
