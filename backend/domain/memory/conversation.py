"""
Hermes V2 — L1 Conversation Memory
═══════════════════════════════════════════════════════════════
Ephemeral chat-turn history stored as a Redis list with TTL.

Key pattern : conv:{session_id}
Storage     : JSON-encoded messages in a Redis list (RPUSH / LRANGE)
Default TTL : 3 600 s (1 hour)
"""

import json
import logging
from typing import Optional

from core.db_redis import get_redis_client

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS: int = 3_600  # 1 hour


class ConversationMemory:
    """L1 — ephemeral per-session conversation history backed by Redis."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._redis = get_redis_client()

    # ── helpers ──────────────────────────────────────────────
    @staticmethod
    def _key(session_id: str) -> str:
        return f"conv:{session_id}"

    # ── public API ───────────────────────────────────────────
    async def add(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session's conversation list.

        Args:
            session_id: Unique session identifier.
            role:       One of ``"user"`` / ``"assistant"`` / ``"system"``.
            content:    Raw message text.
        """
        key = self._key(session_id)
        message = json.dumps({"role": role, "content": content})

        pipe = self._redis.pipeline()
        pipe.rpush(key, message)
        pipe.expire(key, self._ttl)  # reset TTL on every write
        await pipe.execute()

        logger.debug("[CONV_MEM] +msg  session=%s role=%s len=%d", session_id, role, len(content))

    async def get_history(self, session_id: str, limit: int = 20) -> list[dict]:
        """Return the most recent *limit* messages for a session.

        Args:
            session_id: Unique session identifier.
            limit:      Max number of messages to return (default 20).

        Returns:
            List of ``{"role": ..., "content": ...}`` dicts, oldest first.
        """
        key = self._key(session_id)
        # Negative index → last `limit` items in the list
        raw_messages: list[str] = await self._redis.lrange(key, -limit, -1)
        history = [json.loads(m) for m in raw_messages]
        logger.debug("[CONV_MEM] get   session=%s returned=%d", session_id, len(history))
        return history

    async def clear(self, session_id: str) -> None:
        """Delete all conversation history for a session."""
        key = self._key(session_id)
        await self._redis.delete(key)
        logger.info("[CONV_MEM] clear session=%s", session_id)
