"""
Hermes V2 — Qdrant Vector Database Client
═══════════════════════════════════════════════════════════════
Singleton Qdrant client configured from application settings.
"""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from core.config import get_settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Return a singleton QdrantClient instance."""
    global _client
    if _client is None:
        settings = get_settings()
        kwargs = {
            "host": settings.QDRANT_HOST,
            "port": settings.QDRANT_PORT,
            "prefer_grpc": True,
        }
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY
        _client = QdrantClient(**kwargs)
        logger.info(
            "[DB_QDRANT] Client connected to %s:%s",
            settings.QDRANT_HOST,
            settings.QDRANT_PORT,
        )
    return _client


async def ensure_collection(
    collection_name: str,
    vector_size: int = 384,
    distance: Distance = Distance.COSINE,
) -> None:
    """Create the collection if it does not already exist."""
    client = get_qdrant_client()
    existing = {c.name for c in client.get_collections().collections}
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )
        logger.info("[DB_QDRANT] Created collection '%s'.", collection_name)
    else:
        logger.debug("[DB_QDRANT] Collection '%s' already exists.", collection_name)


async def check_qdrant_health() -> bool:
    """Return True if Qdrant is reachable."""
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True
    except Exception as exc:
        logger.error("[DB_QDRANT] Health check failed: %s", exc)
        return False
