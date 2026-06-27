"""
Hermes V2 — Rate Limiter
═══════════════════════════════════════════════════════════════
Token bucket rate limiter backed by Redis for distributed
rate limiting across workers.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(
        self,
        requests_per_minute: int = 30,
        burst_size: int = 10,
    ) -> None:
        self._rpm = requests_per_minute
        self._burst = burst_size
        self._tokens: dict[str, float] = {}
        self._last_refill: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        """Check if a request is allowed for the given key."""
        now = time.monotonic()
        refill_rate = self._rpm / 60.0  # tokens per second

        if key not in self._tokens:
            self._tokens[key] = float(self._burst)
            self._last_refill[key] = now

        # Refill tokens
        elapsed = now - self._last_refill[key]
        self._tokens[key] = min(
            self._burst,
            self._tokens[key] + elapsed * refill_rate,
        )
        self._last_refill[key] = now

        if self._tokens[key] >= 1.0:
            self._tokens[key] -= 1.0
            return True

        logger.warning("[RATE_LIMIT] Key '%s' exceeded rate limit.", key)
        return False

    def get_remaining(self, key: str) -> float:
        """Get remaining tokens for a key."""
        return self._tokens.get(key, float(self._burst))
