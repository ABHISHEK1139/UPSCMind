"""
Hermes V2 — Health Check Routes
═══════════════════════════════════════════════════════════════
Comprehensive health checks for all services.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check."""
    return {"status": "ok", "service": "hermes-v2", "version": "2.0.0"}


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check — verifies all database connections."""
    t0 = time.monotonic()
    checks: Dict[str, Any] = {}
    all_healthy = True
    
    for name, check_fn in [
        ("postgres", "check_postgres_health"),
        ("redis", "check_redis_health"),
        ("qdrant", "check_qdrant_health"),
        ("neo4j", "check_neo4j_health"),
    ]:
        try:
            mod = __import__(f"core.db_{name}" if name != "postgres" else "core.db_postgres",
                           fromlist=[check_fn])
            healthy = await getattr(mod, check_fn)()
            checks[name] = {"status": "healthy" if healthy else "unhealthy"}
            if not healthy:
                all_healthy = False
        except Exception as exc:
            checks[name] = {"status": "error", "error": str(exc)}
            all_healthy = False
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "response_time_ms": round((time.monotonic() - t0) * 1000, 2),
    }


@router.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check — is the service ready to accept traffic?"""
    try:
        from domain.answer_generation.orchestrator import build_answer_graph
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "not_ready", "error": str(exc)}


@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check — is the process alive?"""
    return {"status": "alive"}
