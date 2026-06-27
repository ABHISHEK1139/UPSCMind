"""Hermes V2 — NITI Aayog Scraper."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class NITIScraper(BaseScraper):
    """Scraper for NITI Aayog reports."""

    def __init__(self) -> None:
        super().__init__(base_url="https://niti.gov.in", timeout=30)

    def get_source_name(self) -> str:
        return "niti"

    async def scrape_latest(self) -> List[Dict[str, Any]]:
        """Scrape latest NITI Aayog reports."""
        return []

    def index_reports(self, reports: List[Dict[str, Any]]) -> int:
        """Index reports into Qdrant."""
        if not reports:
            return 0
        try:
            from core.db_qdrant import get_qdrant_client
            from core.config import get_settings
            from qdrant_client.http.models import PointStruct
            import uuid

            client = get_qdrant_client()
            settings = get_settings()
            points = []
            for r in reports:
                text = r.get("content", r.get("summary", ""))
                chunks = self._chunk_text(text)
                for chunk in chunks:
                    points.append(PointStruct(
                        id=str(uuid.uuid4()),
                        vector=[0.0] * 384,
                        payload={"text": chunk, "source": "niti", "title": r.get("title", "")},
                    ))
            if points:
                client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
            return len(points)
        except Exception as exc:
            logger.error("[NITI] Indexing failed: %s", exc)
            return 0
