"""
Hermes V2 — API Middleware
═══════════════════════════════════════════════════════════════
Rate limiting, request logging, and circuit breaker middleware.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ── Rate Limiting Middleware ─────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiter per client IP.
    Uses in-memory tracking (use Redis in production for distributed setup).
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 30,
        burst_size: int = 10,
    ):
        super().__init__(app)
        self._rpm = requests_per_minute
        self._burst = burst_size
        self._tokens: dict[str, float] = defaultdict(lambda: float(burst_size))
        self._last_refill: dict[str, float] = defaultdict(time.monotonic)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        
        if not self._allow_request(client_ip):
            from fastapi.responses import JSONResponse
            retry_after = max(1, int(60 / max(self._rpm, 1)))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        
        return await call_next(request)
    
    def _allow_request(self, client_ip: str) -> bool:
        now = time.monotonic()
        refill_rate = self._rpm / 60.0
        
        elapsed = now - self._last_refill[client_ip]
        self._tokens[client_ip] = min(
            self._burst,
            self._tokens[client_ip] + elapsed * refill_rate,
        )
        self._last_refill[client_ip] = now
        
        if self._tokens[client_ip] >= 1.0:
            self._tokens[client_ip] -= 1.0
            return True
        return False


# ── Request Logging Middleware ──────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs all requests with timing, status, and client info."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        t0 = time.monotonic()
        
        # Log request
        logger.info(
            "[REQUEST] %s %s from %s",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
        )
        
        try:
            response = await call_next(request)
            latency_ms = (time.monotonic() - t0) * 1000
            
            # Log response
            logger.info(
                "[RESPONSE] %s %s → %d (%.0fms)",
                request.method,
                request.url.path,
                response.status_code,
                latency_ms,
            )
            
            # Add timing header
            response.headers["X-Response-Time-Ms"] = str(round(latency_ms, 2))
            return response
            
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            logger.error(
                "[ERROR] %s %s → %s (%.0fms)",
                request.method,
                request.url.path,
                str(exc),
                latency_ms,
            )
            raise


# ── Circuit Breaker ─────────────────────────────────────────────────

class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected immediately
    - HALF_OPEN: Testing if service has recovered
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
    
    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time > self._recovery_timeout:
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
        return self._state
    
    def record_success(self) -> None:
        if self._state == self.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self._half_open_max_calls:
                self._state = self.CLOSED
                self._failure_count = 0
        elif self._state == self.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)
    
    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        
        if self._state == self.HALF_OPEN:
            self._state = self.OPEN
        elif self._failure_count >= self._failure_threshold:
            self._state = self.OPEN
            logger.warning(
                "[CIRCUIT] Opened after %d failures", self._failure_count
            )
    
    def can_execute(self) -> bool:
        state = self.state
        if state == self.CLOSED:
            return True
        if state == self.HALF_OPEN:
            return self._half_open_calls < self._half_open_max_calls
        return False


# ── Global circuit breakers ─────────────────────────────────────────

_llm_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
_db_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=15.0)


def get_llm_circuit_breaker() -> CircuitBreaker:
    return _llm_circuit_breaker


def get_db_circuit_breaker() -> CircuitBreaker:
    return _db_circuit_breaker
