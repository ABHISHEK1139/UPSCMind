"""
Hermes V2 — Base Scraper
═══════════════════════════════════════════════════════════════
Abstract base class for all scrapers with timeout, retry,
and rate-limiting support.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0  # seconds
DEFAULT_RATE_LIMIT = 1.0  # seconds between requests


class BaseScraper(ABC):
    """Abstract base scraper with timeout, retry, and rate-limiting."""

    def __init__(
        self,
        base_url: str = "",
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        rate_limit: float = DEFAULT_RATE_LIMIT,
    ) -> None:
        self._base_url = base_url
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._rate_limit = rate_limit
        self._last_request_time: float = 0.0

    @abstractmethod
    async def scrape_latest(self) -> List[Dict[str, Any]]:
        """Scrape the latest content. Returns list of article dicts."""
        ...

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of this source."""
        ...

    async def _fetch(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Fetch a URL with retry and rate-limiting."""
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            for attempt in range(self._max_retries):
                try:
                    # Rate limiting
                    elapsed = time.monotonic() - self._last_request_time
                    if elapsed < self._rate_limit:
                        await asyncio.sleep(self._rate_limit - elapsed)

                    self._last_request_time = time.monotonic()

                    async with session.get(url, params=params, headers=headers) as resp:
                        if resp.status == 200:
                            return await resp.text()
                        if resp.status == 429:  # Rate limited
                            wait = self._retry_delay * (attempt + 1)
                            logger.warning("[SCRAPE] Rate limited, waiting %.1fs", wait)
                            await asyncio.sleep(wait)
                            continue
                        logger.warning("[SCRAPE] HTTP %d for %s", resp.status, url)
                        return None
                except asyncio.TimeoutError:
                    logger.warning("[SCRAPE] Timeout for %s (attempt %d)", url, attempt + 1)
                except Exception as exc:
                    logger.warning("[SCRAPE] Error for %s: %s", url, exc)

                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay)

        return None

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks for embedding."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i : i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks
