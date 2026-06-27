"""
Hermes V2 — Redis Pub/Sub Event Bus
═══════════════════════════════════════════════════════════════
Lightweight async event bus built on top of Redis Pub/Sub.

Producers call ``await bus.publish(EVENT, data)``; consumers
register handlers via ``bus.subscribe(EVENT, callback)`` and
then call ``await bus.listen()`` to start dispatching.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import redis.asyncio as aioredis

from core.config import get_settings

logger = logging.getLogger(__name__)

# ── Domain Event Constants ───────────────────────────────────

QUESTION_RECEIVED: str = "hermes.question_received"
TOPIC_DETECTED: str = "hermes.topic_detected"
RETRIEVAL_COMPLETED: str = "hermes.retrieval_completed"
DRAFT_COMPLETED: str = "hermes.draft_completed"
REVIEW_COMPLETED: str = "hermes.review_completed"
REVISION_COMPLETED: str = "hermes.revision_completed"
VERIFICATION_PASSED: str = "hermes.verification_passed"
ANSWER_GENERATED: str = "hermes.answer_generated"
FEEDBACK_RECEIVED: str = "hermes.feedback_received"
DATASET_SAVED: str = "hermes.dataset_saved"
BENCHMARK_STARTED: str = "hermes.benchmark_started"
BENCHMARK_COMPLETED: str = "hermes.benchmark_completed"

# Type alias for subscriber callbacks
EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class EventBus:
    """
    Async event bus backed by Redis Pub/Sub.

    Usage::

        bus = EventBus()

        # Publishing
        await bus.publish(QUESTION_RECEIVED, {"question_id": "abc123"})

        # Subscribing (register then listen)
        async def on_question(event: str, data: dict):
            print(f"Got {event}: {data}")

        bus.subscribe(QUESTION_RECEIVED, on_question)
        await bus.listen()          # blocks, dispatching events
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or get_settings().REDIS_URL
        self._pub_client: aioredis.Redis | None = None
        self._sub_client: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._handlers: dict[str, list[EventCallback]] = {}

    # ── Connection helpers ───────────────────────────────────

    async def _get_pub_client(self) -> aioredis.Redis:
        if self._pub_client is None:
            self._pub_client = aioredis.from_url(
                self._redis_url, decode_responses=True
            )
        return self._pub_client

    async def _get_pubsub(self) -> aioredis.client.PubSub:
        if self._pubsub is None:
            self._sub_client = aioredis.from_url(
                self._redis_url, decode_responses=True
            )
            self._pubsub = self._sub_client.pubsub()
        return self._pubsub

    # ── Public API ───────────────────────────────────────────

    async def publish(self, event_name: str, data: dict[str, Any]) -> int:
        """
        Publish an event to all subscribers.

        Returns the number of clients that received the message.
        """
        client = await self._get_pub_client()
        payload = json.dumps({"event": event_name, "data": data})
        receivers: int = await client.publish(event_name, payload)
        logger.info(
            "[EVENT_BUS] Published %s → %d receiver(s)", event_name, receivers
        )
        return receivers

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        """Register *callback* to be invoked whenever *event_name* fires."""
        self._handlers.setdefault(event_name, []).append(callback)
        logger.debug("[EVENT_BUS] Subscribed %s → %s", event_name, callback.__name__)

    async def listen(self) -> None:
        """
        Start the subscriber loop — **blocks** until cancelled.

        Subscribes to all channels that have registered handlers,
        then dispatches incoming messages to the matching callbacks.
        """
        if not self._handlers:
            logger.warning("[EVENT_BUS] listen() called with no handlers registered.")
            return

        pubsub = await self._get_pubsub()
        await pubsub.subscribe(*self._handlers.keys())
        logger.info(
            "[EVENT_BUS] Listening on %d channel(s): %s",
            len(self._handlers),
            ", ".join(self._handlers.keys()),
        )

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            channel: str = message["channel"]
            try:
                envelope = json.loads(message["data"])
                event_name = envelope.get("event", channel)
                data = envelope.get("data", {})
            except (json.JSONDecodeError, AttributeError):
                logger.warning("[EVENT_BUS] Malformed payload on %s", channel)
                continue

            for handler in self._handlers.get(channel, []):
                try:
                    await handler(event_name, data)
                except Exception:
                    logger.exception(
                        "[EVENT_BUS] Handler %s raised on %s",
                        handler.__name__,
                        event_name,
                    )

    # ── Cleanup ──────────────────────────────────────────────

    async def close(self) -> None:
        """Unsubscribe and close underlying Redis connections."""
        if self._pubsub is not None:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._sub_client is not None:
            await self._sub_client.close()
        if self._pub_client is not None:
            await self._pub_client.close()
        logger.info("[EVENT_BUS] Closed.")
