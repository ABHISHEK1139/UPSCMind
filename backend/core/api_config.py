"""
Hermes V2 — Centralized API Configuration
═══════════════════════════════════════════════════════════════
All API endpoints are defined here. Change once, affects everything.

Usage:
    from core.api_config import api_config
    
    # Full URL
    url = api_config.answer_url           # http://localhost:8000/api/answer
    
    # Just the path
    path = api_config.answer_endpoint      # /api/answer
    
    # Check health
    async with httpx.AsyncClient() as client:
        resp = await client.get(api_config.health_url)
"""

from __future__ import annotations

from core.config import get_settings


class APIConfig:
    """Centralized API endpoint configuration."""
    
    def __init__(self):
        self._settings = get_settings()
    
    @property
    def base_url(self) -> str:
        """Base URL of the API server."""
        return self._settings.API_BASE_URL
    
    @property
    def answer_endpoint(self) -> str:
        """Path for answer generation endpoint."""
        return self._settings.API_ANSWER_ENDPOINT
    
    @property
    def answer_url(self) -> str:
        """Full URL for answer generation."""
        return f"{self.base_url}{self.answer_endpoint}"
    
    @property
    def answer_stream_endpoint(self) -> str:
        """Path for streaming answer endpoint."""
        return f"{self.answer_endpoint}/stream"
    
    @property
    def answer_stream_url(self) -> str:
        """Full URL for streaming answer."""
        return f"{self.base_url}{self.answer_stream_endpoint}"
    
    @property
    def health_endpoint(self) -> str:
        """Path for health check endpoint."""
        return self._settings.API_HEALTH_ENDPOINT
    
    @property
    def health_url(self) -> str:
        """Full URL for health check."""
        return f"{self.base_url}{self.health_endpoint}"
    
    @property
    def docs_endpoint(self) -> str:
        """Path for API documentation."""
        return self._settings.API_DOCS_ENDPOINT
    
    @property
    def docs_url(self) -> str:
        """Full URL for API documentation."""
        return f"{self.base_url}{self.docs_endpoint}"


# Singleton instance — import this everywhere
api_config = APIConfig()
