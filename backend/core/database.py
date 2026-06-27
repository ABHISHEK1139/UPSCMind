"""
Hermes V2 — Database Connection & Session Management
═══════════════════════════════════════════════════════════════
SQLAlchemy async engine, session factory, and table creation.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Async Engine ───────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# ── Session Factory ────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base Class for ORM Models ───────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── Session Dependency ─────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Database Initialization ────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables (for development/testing)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[DB] Tables created successfully")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("[DB] Connections closed")
