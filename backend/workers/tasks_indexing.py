"""
Hermes V2 — Indexing Tasks
═══════════════════════════════════════════════════════════════
Background tasks for embedding and indexing documents into
Qdrant and Neo4j.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600)
def index_documents_qdrant(self, documents: list[dict] = None) -> Dict[str, Any]:
    """Embed and index documents into Qdrant."""
    try:
        logger.info("[INDEX] Starting Qdrant indexing...")
        from scrapers.pipeline import IngestionPipeline

        pipeline = IngestionPipeline()
        count = pipeline.index_to_qdrant(documents or [])
        logger.info("[INDEX] Qdrant: indexed %d documents.", count)
        return {"backend": "qdrant", "indexed": count}
    except Exception as exc:
        logger.error("[INDEX] Qdrant indexing failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600)
def index_graph_neo4j(self, entities: list[dict] = None) -> Dict[str, Any]:
    """Index entities and relationships into Neo4j."""
    try:
        logger.info("[INDEX] Starting Neo4j graph indexing...")
        from scrapers.pipeline import IngestionPipeline

        pipeline = IngestionPipeline()
        count = pipeline.index_to_neo4j(entities or [])
        logger.info("[INDEX] Neo4j: indexed %d entities.", count)
        return {"backend": "neo4j", "indexed": count}
    except Exception as exc:
        logger.error("[INDEX] Neo4j indexing failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=900)
def rebuild_all_indexes(self) -> Dict[str, Any]:
    """Rebuild all indexes from scratch."""
    try:
        logger.info("[INDEX] Rebuilding all indexes...")
        from scrapers.pipeline import IngestionPipeline

        pipeline = IngestionPipeline()
        result = pipeline.rebuild_indexes()
        logger.info("[INDEX] Rebuild complete: %s", result)
        return result
    except Exception as exc:
        logger.error("[INDEX] Rebuild failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)
