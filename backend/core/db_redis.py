"""
Hermes V2 — Redis Client Factory
═══════════════════════════════════════════════════════════════
Provides both an **async** client (for FastAPI / async workers)
and a **sync** client (for Celery workers).
"""

from __future__ import annotations

import logging

import redis as sync_redis
import redis.asyncio as aioredis

from core.config import get_settings

logger = logging.getLogger(__name__)

# ── Async client (singleton) ─────────────────────────────────

_async_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Return a singleton ``redis.asyncio.Redis`` instance."""
    global _async_client
    if _async_client is None:
        settings = get_settings()
        _async_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        logger.info("[DB_REDIS] Async client created (%s)", settings.REDIS_URL)
    return _async_client


# ── Sync client (singleton, for Celery) ──────────────────────

_sync_client: sync_redis.Redis | None = None


def get_redis_sync() -> sync_redis.Redis:
    """Return a singleton synchronous ``redis.Redis`` for Celery workers."""
    global _sync_client
    if _sync_client is None:
        settings = get_settings()
        _sync_client = sync_redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        logger.info("[DB_REDIS] Sync client created (%s)", settings.REDIS_URL)
    return _sync_client


async def check_redis_health() -> bool:
    """Return True if Redis is reachable."""
    try:
        client = get_redis_client()
        await client.ping()
        return True
    except Exception as exc:
        logger.error("[DB_REDIS] Health check failed: %s", exc)
        return False
