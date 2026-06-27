"""
Hermes V2 — Event Manager (Singleton)
═══════════════════════════════════════════════════════════════
Central event bus instance that all services share.
Provides publish/subscribe helpers and a background listener.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from core.event_bus import (
    EventBus, ANSWER_GENERATED, REVIEW_COMPLETED, REVISION_COMPLETED,
    TOPIC_DETECTED, FEEDBACK_RECEIVED, QUESTION_RECEIVED,
)

logger = logging.getLogger(__name__)

# ── Singleton ─────────────────────────────────────────────────────────────

_event_bus: Optional[EventBus] = None
_listener_task: Optional[asyncio.Task] = None


def get_event_bus() -> EventBus:
    """Get or create the singleton event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def publish(event: str, data: dict[str, Any]) -> None:
    """Publish an event to the bus."""
    bus = get_event_bus()
    try:
        await bus.publish(event, data)
        logger.debug("[EVENT] Published: %s", event)
    except Exception as exc:
        logger.warning("[EVENT] Failed to publish %s: %s", event, exc)


def subscribe(event: str, callback: Callable[[str, dict], Awaitable[None]]) -> None:
    """Subscribe a handler to an event."""
    bus = get_event_bus()
    bus.subscribe(event, callback)
    logger.info("[EVENT] Subscribed handler to: %s", event)


async def start_listener() -> None:
    """Start the background event listener."""
    global _listener_task
    bus = get_event_bus()
    _listener_task = asyncio.create_task(bus.listen())
    logger.info("[EVENT] Event bus listener started")


async def stop_listener() -> None:
    """Stop the background event listener."""
    global _listener_task
    if _listener_task:
        _listener_task.cancel()
        _listener_task = None
        logger.info("[EVENT] Event bus listener stopped")


# ── Module Event Handlers ─────────────────────────────────────────────────

async def on_answer_generated(event: str, data: dict) -> None:
    """When answer is generated, update analytics and revision."""
    logger.info("[EVENT] Answer generated for student=%s topic=%s score=%s",
                data.get("student_id"), data.get("topic"), data.get("score"))


async def on_revision_completed(event: str, data: dict) -> None:
    """When revision is completed, update planner."""
    logger.info("[EVENT] Revision completed for student=%s topic=%s",
                data.get("student_id"), data.get("topic"))


async def on_feedback_received(event: str, data: dict) -> None:
    """When feedback is received, update analytics."""
    logger.info("[EVENT] Feedback received for student=%s", data.get("student_id"))


def register_default_handlers() -> None:
    """Register all default inter-module event handlers."""
    from core.event_consumers import register_all_consumers
    register_all_consumers()
    logger.info("[EVENT] Default handlers registered")
