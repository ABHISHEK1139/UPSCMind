"""
Hermes V2 — FastAPI Application Entry Point
═══════════════════════════════════════════════════════════════
Initializes the FastAPI app with all routers, middleware,
CORS, telemetry, and event bus integration.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.telemetry import setup_telemetry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info("═" * 60)
    logger.info("  Hermes V2 — UPSC Intelligence System")
    logger.info("  Version: %s | Env: %s", settings.APP_VERSION, settings.APP_ENV)
    logger.info("═" * 60)
    setup_telemetry(service_name="hermes-v2")

    # ── Event Bus ────────────────────────────────────────────────
    from core.event_manager import register_default_handlers, start_listener
    register_default_handlers()
    await start_listener()
    logger.info("─" * 60)
    logger.info("  System ready. Accepting requests.")
    logger.info("─" * 60)
    yield
    logger.info("Shutting down Hermes V2...")
    from core.event_manager import stop_listener
    await stop_listener()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="Hermes V2 — UPSC Intelligence System",
        version=settings.APP_VERSION,
        description="Advanced agentic system for UPSC Civil Services answer generation.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    # ── Security Headers Middleware ───────────────────────────────
    from api.security import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"] if settings.APP_DEBUG else ["https://upscmind.ai"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    # ── API Routers ──────────────────────────────────────────────
    from api.routes_answer import router as answer_router
    from api.routes_health import router as health_router
    from api.routes_evaluation import router as evaluation_router
    from api.routes_feedback import router as feedback_router
    from api.routes_student import router as student_router
    app.include_router(answer_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(evaluation_router, prefix="/api")
    app.include_router(feedback_router, prefix="/api")
    app.include_router(student_router, prefix="/api/student")

    # ── Middleware (order matters: last added = first executed) ────
    from api.middleware import RequestLoggingMiddleware, RateLimitMiddleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.GOVERNANCE_RATE_LIMIT_PER_MINUTE)

    # ── Global Exception Handler ─────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.APP_DEBUG else "An unexpected error occurred",
            },
        )

    @app.get("/")
    async def root():
        return {
            "name": "Hermes V2",
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/api/docs",
        }

    return app


app = create_app()
