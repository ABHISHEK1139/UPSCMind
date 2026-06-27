"""
Hermes V2 — Async PostgreSQL Connection Layer
═══════════════════════════════════════════════════════════════
Provides an async SQLAlchemy engine and a context-managed
session factory for use throughout the application.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

logger = logging.getLogger(__name__)

# ── Engine (module-level singleton) ──────────────────────────

_engine: AsyncEngine | None = None


def _get_engine() -> AsyncEngine:
    """Lazily create and return the async engine singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.APP_DEBUG,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        logger.info("[DB_POSTGRES] Async engine created.")
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return an async session factory bound to the engine."""
    return async_sessionmaker(
        bind=_get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session that auto-commits or rolls back."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncSession:
    """Return a bare async session (caller manages commit/rollback)."""
    return _get_session_factory()()


async def check_postgres_health() -> bool:
    """Return True if the database is reachable."""
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("[DB_POSTGRES] Health check failed: %s", exc)
        return False
