"""
Hermes V2 — L3 Long-Term Memory
═══════════════════════════════════════════════════════════════
Cross-session user preferences, weak areas, and learning history
managed via Mem0 (https://github.com/mem0ai/mem0).

Falls back gracefully to no-ops when ``mem0ai`` is not installed.
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_mem0_available = False

try:
    from mem0 import Memory as Mem0Memory
    _mem0_available = True
except ImportError:
    Mem0Memory = None
    logger.warning(
        "[LT_MEM] mem0ai package not installed — long-term memory disabled. "
        "Run: pip install mem0ai"
    )


def _build_mem0_config() -> dict:
    """Build Mem0 configuration dict, preferring Qdrant as the vector store."""
    from core.config import get_settings
    settings = get_settings()
    config: dict[str, Any] = {}

    if settings.QDRANT_HOST:
        config["vector_store"] = {
            "provider": "qdrant",
            "config": {
                "host": settings.QDRANT_HOST,
                "port": settings.QDRANT_PORT,
                "collection_name": settings.MEM0_COLLECTION,
                "api_key": settings.QDRANT_API_KEY or None,
            },
        }

    llm_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if llm_api_key:
        config["llm"] = {
            "provider": "openai",
            "config": {
                "api_key": llm_api_key,
                "model": settings.MEM0_LLM_MODEL,
            },
        }

    return config


class LongTermMemory:
    """L3 — cross-session user memory backed by Mem0 → Qdrant."""

    def __init__(self, user_id: str = "default_user") -> None:
        self._user_id = user_id
        self._mem0: Any = None

        if _mem0_available:
            try:
                config = _build_mem0_config()
                self._mem0 = Mem0Memory.from_config(config_dict=config)
                logger.info("[LT_MEM] Mem0 initialized for user '%s'.", user_id)
            except Exception as exc:
                logger.warning("[LT_MEM] Failed to initialize Mem0: %s", exc)

    async def add(self, content: str, metadata: Optional[dict] = None) -> None:
        """Store a long-term memory."""
        if self._mem0 is None:
            logger.debug("[LT_MEM] Mem0 unavailable — skipping add.")
            return
        try:
            self._mem0.add(
                messages=[{"role": "user", "content": content}],
                user_id=self._user_id,
                metadata=metadata or {},
            )
            logger.debug("[LT_MEM] Added memory for user '%s'.", self._user_id)
        except Exception as exc:
            logger.warning("[LT_MEM] Failed to add memory: %s", exc)

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search long-term memories."""
        if self._mem0 is None:
            return []
        try:
            results = self._mem0.search(query=query, user_id=self._user_id, limit=limit)
            return results.get("results", []) if isinstance(results, dict) else list(results)
        except Exception as exc:
            logger.warning("[LT_MEM] Search failed: %s", exc)
            return []

    async def get_all(self) -> list[dict]:
        """Return all memories for the user."""
        if self._mem0 is None:
            return []
        try:
            results = self._mem0.get_all(user_id=self._user_id)
            return results.get("results", []) if isinstance(results, dict) else list(results)
        except Exception as exc:
            logger.warning("[LT_MEM] get_all failed: %s", exc)
            return []
