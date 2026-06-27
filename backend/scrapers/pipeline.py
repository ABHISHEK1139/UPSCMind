"""
Hermes V2 — Ingestion Pipeline
═══════════════════════════════════════════════════════════════
Full pipeline: scrape → chunk → embed → store (Qdrant + Neo4j).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Full ingestion pipeline from raw data to indexed knowledge."""

    def run_full(self) -> Dict[str, Any]:
        """Run the full pipeline across all sources."""
        results = {}
        try:
            from scrapers.pib import PIBScraper
            scraper = PIBScraper()
            import asyncio
            articles = asyncio.run(scraper.scrape_latest())
            results["pib"] = scraper.index_articles(articles)
        except Exception as exc:
            logger.error("[PIPE] PIB failed: %s", exc)
            results["pib"] = 0
        return results

    def index_to_qdrant(self, documents: list[dict]) -> int:
        """Embed and index documents into Qdrant."""
        if not documents:
            return 0
        try:
            from core.db_qdrant import get_qdrant_client
            from core.config import get_settings
            from qdrant_client.http.models import PointStruct

            client = get_qdrant_client()
            settings = get_settings()
            points = []
            for doc in documents:
                text = doc.get("text", doc.get("content", ""))
                if not text:
                    continue
                # TODO: replace with real embedding
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[0.0] * 384,
                    payload={"text": text, "source": doc.get("source", "unknown")},
                ))
            if points:
                client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
            return len(points)
        except Exception as exc:
            logger.error("[PIPE] Qdrant indexing failed: %s", exc)
            return 0

    def index_to_neo4j(self, entities: list[dict]) -> int:
        """Index entities and relationships into Neo4j."""
        if not entities:
            return 0
        try:
            from core.db_neo4j import execute_cypher
            import asyncio
            count = 0
            for entity in entities:
                name = entity.get("name", "")
                label = entity.get("label", "Entity")
                if name:
                    asyncio.run(
                        execute_cypher(
                            f"MERGE (n:{label} {{name: $name}}) SET n += $props",
                            {"name": name, "props": entity.get("properties", {})},
                        )
                    )
                    count += 1
            return count
        except Exception as exc:
            logger.error("[PIPE] Neo4j indexing failed: %s", exc)
            return 0

    def rebuild_indexes(self) -> Dict[str, Any]:
        """Rebuild all indexes from scratch."""
        logger.info("[PIPE] Rebuilding all indexes...")
        return {"status": "not_implemented", "message": "Full rebuild requires data source configuration"}
