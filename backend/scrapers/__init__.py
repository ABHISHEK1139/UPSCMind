"""Hermes V2 — Data Ingestion Scrapers."""

from scrapers.base_scraper import BaseScraper
from scrapers.pib import PIBScraper
from scrapers.prs import PRSScraper
from scrapers.sc_judgments import SCJudgmentsScraper
from scrapers.rbi import RBIScraper
from scrapers.niti import NITIScraper
from scrapers.pipeline import IngestionPipeline

__all__ = [
    "BaseScraper",
    "PIBScraper",
    "PRSScraper",
    "SCJudgmentsScraper",
    "RBIScraper",
    "NITIScraper",
    "IngestionPipeline",
]
