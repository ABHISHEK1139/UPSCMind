"""
Hermes V2 — Application Configuration
═══════════════════════════════════════════════════════════════
Centralised Pydantic Settings class loaded from environment
variables / .env file. Every service in the system imports
settings from here via `get_settings()`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration for Hermes V2, loaded once and cached."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "2.0.0"
    ACTIVE_PROFILE: str = "development"

    # ── API Endpoints (change these to customize URLs) ──────
    API_BASE_URL: str = "http://localhost:8000"
    API_ANSWER_ENDPOINT: str = "/api/answer"
    API_HEALTH_ENDPOINT: str = "/api/health"
    API_DOCS_ENDPOINT: str = "/api/docs"

    # ── Postgres ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://upsc_user:upsc_password@hermes_postgres:5432/upsc_db"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://hermes_redis:6379/0"

    # ── Neo4j ─────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://hermes_neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "upsc_neo4j_password"

    # ── Qdrant ────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "upsc_knowledge"

    # ── LLM Providers ─────────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # ── Langfuse (Optional) ───────────────────────────────────
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # ── LLM Settings ──────────────────────────────────────────
    LLM_CACHE_TTL: int = 3600
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT: int = 120
    LLM_DEFAULT_MODEL: str = "openrouter/owl-alpha"
    LLM_MAX_RETRIES: int = 3

    # ── Governance ─────────────────────────────────────────────
    GOVERNANCE_RATE_LIMIT_PER_MINUTE: int = 60
    GOVERNANCE_MAX_CONCURRENT_AGENTS: int = 10
    GOVERNANCE_AUDIT_LOG_ENABLED: bool = True

    # ── GPU ────────────────────────────────────────────────────
    CUDA_VISIBLE_DEVICES: str = "0"
    ENABLE_GPU: bool = True

    # ── MinIO Object Storage ──────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_DATASETS: str = "hermes-datasets"
    MINIO_BUCKET_LOGS: str = "hermes-logs"

    # ── Celery ────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Retrieval ─────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_RERANK_TOP_K: int = 5
    RETRIEVAL_DENSE_WEIGHT: float = 0.5
    RETRIEVAL_SPARSE_WEIGHT: float = 0.5

    # ── Orchestrator ──────────────────────────────────────────
    ORCHESTRATOR_MAX_REVISIONS: int = 2
    ORCHESTRATOR_QUALITY_THRESHOLD: float = 0.8

    # ── Memory ────────────────────────────────────────────────
    MEM0_COLLECTION: str = "hermes_lt_memory"
    MEM0_LLM_MODEL: str = "gpt-4o-mini"
    MEM0_EMBEDDER_MODEL: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, singleton Settings instance."""
    return Settings()
