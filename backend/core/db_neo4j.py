"""
Hermes V2 — Neo4j Graph Database Client
═══════════════════════════════════════════════════════════════
Singleton driver and a convenience ``execute_cypher`` helper
for running Cypher queries from async code.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from core.config import get_settings

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None


def get_neo4j_driver() -> AsyncDriver:
    """Return a singleton async Neo4j driver."""
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
        )
        logger.info("[DB_NEO4J] Driver created for %s", settings.NEO4J_URI)
    return _driver


async def execute_cypher(
    query: str,
    params: dict[str, Any] | None = None,
    *,
    database: str = "neo4j",
) -> list[dict[str, Any]]:
    """
    Run a single Cypher query and return all records as dicts.

    Parameters
    ----------
    query : str
        The Cypher query string.
    params : dict, optional
        Query parameters (``$name`` style).
    database : str
        Target Neo4j database (default ``"neo4j"``).

    Returns
    -------
    list[dict[str, Any]]
        Each record as a ``{key: value}`` dict.
    """
    driver = get_neo4j_driver()
    async with driver.session(database=database) as session:
        result = await session.run(query, parameters=params or {})
        records = await result.data()
        return records


async def check_neo4j_health() -> bool:
    """Return True if Neo4j is reachable."""
    try:
        driver = get_neo4j_driver()
        await driver.verify_connectivity()
        return True
    except Exception as exc:
        logger.error("[DB_NEO4J] Health check failed: %s", exc)
        return False
