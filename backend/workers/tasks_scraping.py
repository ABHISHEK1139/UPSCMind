"""
Hermes V2 — Scraping Tasks
═══════════════════════════════════════════════════════════════
Background tasks for data ingestion from various UPSC-relevant
sources: PIB, PRS, Supreme Court, RBI, NITI Aayog.

All tasks handle async scraper methods via the _run_async helper.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300)
def scrape_pib_daily(self) -> Dict[str, Any]:
    """Scrape Press Information Bureau daily bulletins."""
    try:
        logger.info("[SCRAPE] Starting PIB daily scrape...")
        from scrapers.pib import PIBScraper
        scraper = PIBScraper()
        articles = _run_async(scraper.scrape_latest())
        indexed = scraper.index_articles(articles)
        logger.info("[SCRAPE] PIB: scraped=%d indexed=%d", len(articles), indexed)
        return {"source": "pib", "scraped": len(articles), "indexed": indexed}
    except Exception as exc:
        logger.error("[SCRAPE] PIB failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300)
def scrape_prs_daily(self) -> Dict[str, Any]:
    """Scrape PRS Legislative Research updates."""
    try:
        logger.info("[SCRAPE] Starting PRS daily scrape...")
        from scrapers.prs import PRSScraper
        scraper = PRSScraper()
        bills = _run_async(scraper.scrape_latest_bills())
        indexed = scraper.index_bills(bills)
        logger.info("[SCRAPE] PRS: scraped=%d indexed=%d", len(bills), indexed)
        return {"source": "prs", "scraped": len(bills), "indexed": indexed}
    except Exception as exc:
        logger.error("[SCRAPE] PRS failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300)
def scrape_sc_judgments(self) -> Dict[str, Any]:
    """Scrape latest Supreme Court judgments."""
    try:
        logger.info("[SCRAPE] Starting SC judgments scrape...")
        from scrapers.sc_judgments import SCJudgmentsScraper
        scraper = SCJudgmentsScraper()
        judgments = _run_async(scraper.scrape_latest())
        indexed = scraper.index_judgments(judgments)
        logger.info("[SCRAPE] SC: scraped=%d indexed=%d", len(judgments), indexed)
        return {"source": "sc_judgments", "scraped": len(judgments), "indexed": indexed}
    except Exception as exc:
        logger.error("[SCRAPE] SC failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300)
def scrape_rbi_bulletins(self) -> Dict[str, Any]:
    """Scrape RBI bulletins and reports."""
    try:
        logger.info("[SCRAPE] Starting RBI bulletin scrape...")
        from scrapers.rbi import RBIScraper
        scraper = RBIScraper()
        bulletins = _run_async(scraper.scrape_latest())
        indexed = scraper.index_bulletins(bulletins)
        logger.info("[SCRAPE] RBI: scraped=%d indexed=%d", len(bulletins), indexed)
        return {"source": "rbi", "scraped": len(bulletins), "indexed": indexed}
    except Exception as exc:
        logger.error("[SCRAPE] RBI failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300)
def scrape_niti_aayog(self) -> Dict[str, Any]:
    """Scrape NITI Aayog reports and data."""
    try:
        logger.info("[SCRAPE] Starting NITI Aayog scrape...")
        from scrapers.niti import NITIScraper
        scraper = NITIScraper()
        reports = _run_async(scraper.scrape_latest())
        indexed = scraper.index_reports(reports)
        logger.info("[SCRAPE] NITI: scraped=%d indexed=%d", len(reports), indexed)
        return {"source": "niti", "scraped": len(reports), "indexed": indexed}
    except Exception as exc:
        logger.error("[SCRAPE] NITI failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=600)
def run_full_ingestion_pipeline(self) -> Dict[str, Any]:
    """Run the full ingestion pipeline: scrape → embed → store."""
    try:
        logger.info("[SCRAPE] Starting full ingestion pipeline...")
        from scrapers.pipeline import IngestionPipeline
        pipeline = IngestionPipeline()
        result = _run_async(pipeline.run_full())
        logger.info("[SCRAPE] Full pipeline complete: %s", result)
        return result
    except Exception as exc:
        logger.error("[SCRAPE] Full pipeline failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)
