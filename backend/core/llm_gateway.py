"""
Hermes V2 — Unified LLM Gateway
═══════════════════════════════════════════════════════════════
Single entry-point for **every** LLM call in the system.

Features
--------
* LiteLLM ``completion()`` routed through OpenRouter
* Redis-based response caching (SHA-256 of messages+model → TTL)
* Langfuse tracing via ``@observe`` (graceful no-op if missing)
* Priority failover chain:
    owl-alpha (single model for all tasks)
* Structured ``LLMResponse`` dataclass
* ``complete()`` for chat completions
* ``embed()``  for embedding vectors
* Structured logging with structlog
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── Structlog ────────────────────────────────────────────────
try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# ── Langfuse (optional) ─────────────────────────────────────
try:
    from langfuse.decorators import observe
except ImportError:

    def observe(*args: Any, **kwargs: Any):
        """No-op decorator when langfuse is not installed."""
        def _decorator(func):
            return func
        return _decorator

# ── LiteLLM ──────────────────────────────────────────────────
try:
    import litellm
    from litellm import completion as litellm_completion
    from litellm import embedding as litellm_embedding
except ImportError:
    litellm = None
    litellm_completion = None
    litellm_embedding = None

# ── Redis (async) ────────────────────────────────────────────
try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

from core.config import get_settings

# ── Constants ────────────────────────────────────────────────

FAILOVER_CHAIN: list[str] = [
    "openrouter/owl-alpha",
]

# ── Response DTO ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Immutable result returned from every LLM call."""

    content: str
    model_used: str
    latency_ms: float
    tokens_used: int
    cached: bool
    cost_usd: float


# ── Gateway ──────────────────────────────────────────────────


class LLMGateway:
    """
    Unified LLM client with caching, tracing, and failover.

    Parameters
    ----------
    models : list[str] | None
        Ordered failover chain. Falls back to ``FAILOVER_CHAIN``.
    redis_url : str | None
        Override the Redis URL used for caching.
    cache_ttl : int | None
        Override the default TTL (seconds) for cached responses.
    """

    def __init__(
        self,
        models: list[str] | None = None,
        redis_url: str | None = None,
        cache_ttl: int | None = None,
    ) -> None:
        settings = get_settings()
        self.models = models or FAILOVER_CHAIN
        self.api_key: str = settings.OPENROUTER_API_KEY
        self.cache_ttl: int = cache_ttl or settings.LLM_CACHE_TTL
        self.max_tokens: int = settings.LLM_MAX_TOKENS
        self.timeout: int = settings.LLM_TIMEOUT

        # Lazy-init Redis handle
        self._redis_url = redis_url or settings.REDIS_URL
        self._redis: Any = None

        if not self.api_key:
            logger.warning("llm_gateway.no_api_key — Set OPENROUTER_API_KEY")

    # ── Redis helpers ────────────────────────────────────────

    async def _get_redis(self) -> Any:
        if self._redis is None and aioredis is not None:
            self._redis = aioredis.from_url(
                self._redis_url, decode_responses=True
            )
        return self._redis

    @staticmethod
    def _cache_key(messages: list[dict[str, str]], model: str) -> str:
        """SHA-256 hash of the messages + model for cache lookup."""
        blob = json.dumps({"messages": messages, "model": model}, sort_keys=True)
        return f"llm:cache:{hashlib.sha256(blob.encode()).hexdigest()}"

    async def _cache_get(self, key: str) -> str | None:
        rd = await self._get_redis()
        if rd is None:
            return None
        try:
            return await rd.get(key)
        except Exception:
            logger.warning("llm_gateway.cache_get_failed key=%s", key)
            return None

    async def _cache_set(self, key: str, value: str) -> None:
        rd = await self._get_redis()
        if rd is None:
            return
        try:
            await rd.set(key, value, ex=self.cache_ttl)
        except Exception:
            logger.warning("llm_gateway.cache_set_failed key=%s", key)

    # ── Chat Completion ──────────────────────────────────────

    @observe(name="llm_gateway.complete")
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        model: str | None = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Execute a chat completion with automatic failover.

        If *model* is supplied it is tried first; the remaining
        failover chain is appended automatically.
        """
        if litellm_completion is None:
            raise RuntimeError("litellm is not installed — cannot call LLM.")

        chain = self._build_chain(model)

        # ── Cache lookup ─────────────────────────────────────
        cache_key = self._cache_key(messages, chain[0])
        if use_cache:
            cached = await self._cache_get(cache_key)
            if cached is not None:
                logger.info("llm_gateway.cache_hit model=%s", chain[0])
                return LLMResponse(
                    content=cached,
                    model_used=chain[0],
                    latency_ms=0.0,
                    tokens_used=0,
                    cached=True,
                    cost_usd=0.0,
                )

        # ── Failover loop with circuit breaker & rate limit handling ──
        from api.middleware import get_llm_circuit_breaker
        
        breaker = get_llm_circuit_breaker()
        if not breaker.can_execute():
            raise RuntimeError("LLM circuit breaker is OPEN — too many recent failures. Try again later.")
        
        errors: list[str] = []
        for candidate in chain:
            # Retry with exponential backoff for rate limits
            max_retries = 3
            for attempt in range(max_retries):
                t0 = time.perf_counter()
                try:
                    response = litellm_completion(
                        model=candidate,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        api_key=self.api_key,
                        timeout=self.timeout,
                        **kwargs,
                    )

                    content: str = response.choices[0].message.content or ""
                    latency = (time.perf_counter() - t0) * 1000
                    usage = getattr(response, "usage", None)
                    tokens = (
                        (usage.prompt_tokens + usage.completion_tokens)
                        if usage
                        else 0
                    )
                    cost = float(getattr(response, "_hidden_params", {}).get("response_cost", 0.0))

                    logger.info(
                        "llm_gateway.complete_ok model=%s latency_ms=%.1f tokens=%d attempt=%d",
                        candidate, latency, tokens, attempt + 1,
                    )

                    # Record success with circuit breaker
                    breaker.record_success()

                    # Populate cache
                    if use_cache:
                        await self._cache_set(cache_key, content)

                    return LLMResponse(
                        content=content,
                        model_used=candidate,
                        latency_ms=round(latency, 2),
                        tokens_used=tokens,
                        cached=False,
                        cost_usd=cost,
                    )

                except Exception as exc:
                    latency = (time.perf_counter() - t0) * 1000
                    error_str = str(exc).lower()
                    
                    # Detect rate limit errors
                    is_rate_limit = any(kw in error_str for kw in [
                        "rate_limit", "ratelimit", "429", "too many requests",
                        "quota", "throttl"
                    ])
                    
                    if is_rate_limit and attempt < max_retries - 1:
                        # Exponential backoff: 5s, 15s, 60s
                        wait_time = min(5 * (3 ** attempt), 60)
                        logger.warning(
                            "llm_gateway.rate_limit model=%s attempt=%d wait=%ds",
                            candidate, attempt + 1, wait_time,
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # Detect connection errors with shorter retry
                    is_connection = any(kw in error_str for kw in [
                        "connection", "timeout", "network", "503", "502", "504"
                    ])
                    
                    if is_connection and attempt < max_retries - 1:
                        wait_time = 3 * (attempt + 1)
                        logger.warning(
                            "llm_gateway.connection_error model=%s attempt=%d wait=%ds error=%s",
                            candidate, attempt + 1, wait_time, str(exc)[:100],
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    
                    logger.warning(
                        "llm_gateway.complete_fail model=%s error=%s",
                        candidate, str(exc)[:200],
                    )
                    errors.append(f"{candidate}: {exc}")
                    
                    # Record failure with circuit breaker
                    breaker.record_failure()
                    break  # No more retries for this model

        raise RuntimeError(
            f"All models in failover chain failed. Errors: {errors}"
        )

    # ── Embeddings ───────────────────────────────────────────

    @observe(name="llm_gateway.embed")
    async def embed(
        self,
        texts: list[str],
        *,
        model: str = "openrouter/owl-alpha",
        **kwargs: Any,
    ) -> list[list[float]]:
        """
        Generate embedding vectors for a batch of texts.
        """
        if litellm_embedding is None:
            raise RuntimeError("litellm is not installed — cannot embed.")

        t0 = time.perf_counter()
        response = litellm_embedding(
            model=model,
            input=texts,
            api_key=self.api_key,
            **kwargs,
        )
        latency = (time.perf_counter() - t0) * 1000

        embeddings: list[list[float]] = [
            item["embedding"] for item in response.data
        ]
        logger.info(
            "llm_gateway.embed_ok model=%s texts=%d latency_ms=%.1f",
            model, len(texts), latency,
        )
        return embeddings

    # ── Internal ─────────────────────────────────────────────

    def _build_chain(self, preferred: str | None) -> list[str]:
        """Build the failover chain with *preferred* model first."""
        if preferred is None:
            return list(self.models)
        chain = [preferred]
        for m in self.models:
            if m != preferred:
                chain.append(m)
        return chain
