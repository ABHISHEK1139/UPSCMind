"""
Hermes V2 — PIB Scraper (Crawl4AI + Fallback)
═══════════════════════════════════════════════════════════════
Scrapes Press Information Bureau daily bulletins.
Uses Crawl4AI when available, falls back to requests+BeautifulSoup.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PIB_BASE_URL = "https://pib.gov.in"
PIB_RELEASES_URL = "https://pib.gov.in/PressReleasePage.aspx"


class PIBScraper(BaseScraper):
    """Scraper for Press Information Bureau."""
    
    def __init__(self) -> None:
        super().__init__(base_url=PIB_BASE_URL, timeout=30)
    
    def get_source_name(self) -> str:
        return "pib"
    
    async def scrape_latest(self) -> List[Dict[str, Any]]:
        """Scrape latest PIB press releases."""
        try:
            return await self._scrape_with_crawl4ai()
        except ImportError:
            logger.info("[PIB] Crawl4AI not installed, using fallback.")
        except Exception as exc:
            logger.warning("[PIB] Crawl4AI failed: %s", exc)
        return await self._scrape_with_requests()
    
    async def _scrape_with_crawl4ai(self) -> List[Dict[str, Any]]:
        """Scrape using Crawl4AI with LLM extraction."""
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
        from crawl4ai.extraction_strategy import LLMExtractionStrategy
        
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url=PIB_RELEASES_URL,
                config=CrawlerRunConfig(
                    word_count_threshold=50,
                    extraction_strategy=LLMExtractionStrategy(
                        provider="openrouter/owl-alpha",
                        instruction=(
                            "Extract all press releases with: title, date, ministry, "
                            "content_summary. Return as JSON list."
                        ),
                    ),
                    cache_mode="BYPASS",
                ),
            )
            if result.extracted_content:
                try:
                    data = json.loads(result.extracted_content)
                    return data if isinstance(data, list) else data.get("releases", [])
                except json.JSONDecodeError:
                    pass
        return []
    
    async def _scrape_with_requests(self) -> List[Dict[str, Any]]:
        """Fallback: requests + BeautifulSoup."""
        html = await self._fetch(PIB_RELEASES_URL)
        if not html:
            return []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            articles = []
            for item in soup.select(".release_list, .press-release-item, .listing-item"):
                title_elem = item.select_one("a, .title, h3")
                date_elem = item.select_one(".date, .release-date, span")
                content_elem = item.select_one(".content, .summary, p")
                if title_elem:
                    articles.append({
                        "title": title_elem.get_text(strip=True),
                        "url": title_elem.get("href", ""),
                        "date": date_elem.get_text(strip=True) if date_elem else None,
                        "content": content_elem.get_text(strip=True) if content_elem else "",
                        "source": "pib",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    })
            return articles
        except ImportError:
            logger.warning("[PIB] Install beautifulsoup4 for fallback scraping.")
            return []
    
    def index_articles(self, articles: List[Dict[str, Any]]) -> int:
        """Index scraped articles into Qdrant with real embeddings."""
        if not articles:
            return 0
        try:
            from core.db_qdrant import get_qdrant_client
            from core.config import get_settings
            from qdrant_client.http.models import PointStruct
            
            client = get_qdrant_client()
            settings = get_settings()
            
            texts = [f"{a.get('title', '')}\n\n{a.get('content', '')}" for a in articles]
            
            # Real embeddings
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                vectors = model.encode(texts).tolist()
            except ImportError:
                vectors = [[0.0] * 384] * len(texts)
            
            points = []
            for article, vector in zip(articles, vectors):
                date = article.get("date", "")
                published_date = None
                if date:
                    for fmt in ["%d %B %Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                        try:
                            published_date = datetime.strptime(date.strip(), fmt).strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            continue
                
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "text": f"{article.get('title', '')}\n\n{article.get('content', '')}",
                        "source": "pib",
                        "title": article.get("title", ""),
                        "date": date,
                        "published_date": published_date,
                        "valid_until": None,
                        "url": article.get("url", ""),
                        "ministry": article.get("ministry", ""),
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    },
                ))
            
            if points:
                client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points, wait=True)
            return len(points)
        except Exception as exc:
            logger.error("[PIB] Indexing failed: %s", exc)
            return 0
