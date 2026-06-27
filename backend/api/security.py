"""
Hermes V2 — Security Module
═══════════════════════════════════════════════════════════════
JWT authentication, input sanitization, and security utilities.
"""

from __future__ import annotations

import hashlib
import html
import os
import logging
import re
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ── JWT (simple implementation without PyJWT dependency) ──────────────────

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24


def _base64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    import base64
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def create_token(student_id: str, email: str) -> str:
    """Create a simple JWT-like token (header.payload.signature)."""
    import json
    import hmac

    header = {"alg": ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": student_id,
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY_HOURS * 3600,
        "jti": secrets.token_hex(16),
    }

    header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{signing_input}.{signature_b64}"


def verify_token(token: str) -> Dict[str, Any]:
    """Verify token and return payload. Raises HTTPException on failure."""
    import json
    import hmac

    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"

        expected_sig = hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _base64url_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid signature")

        payload = json.loads(_base64url_decode(payload_b64))

        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expired")

        return payload
    except Exception as exc:
        logger.warning("[SECURITY] Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Security Dependencies ────────────────────────────────────────────────

security_scheme = HTTPBearer(auto_error=False)


async def get_current_student(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Dict[str, Any]:
    """Extract and verify student from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(credentials.credentials)


# ── Input Sanitization ────────────────────────────────────────────────────

def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Sanitize user input — prevent XSS, SQL injection patterns."""
    if not text:
        return ""

    # Truncate
    text = text[:max_length]

    # HTML escape (quote=True to escape single quotes too)
    text = html.escape(text, quote=True)

    # Remove potential SQL injection patterns
    sql_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
        r"(--|;|/\*|\*/)",
        r"(\b(OR|AND)\b\s+\d+\s*=\s*\d+)",
    ]
    for pattern in sql_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning("[SECURITY] Potential SQL injection detected")
            # Remove the suspicious pattern
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Remove potential XSS event handlers
    xss_patterns = [
        r"\bon\w+\s*=",  # onerror=, onclick=, onload=, etc.
        r"javascript\s*:",  # javascript: protocol
    ]
    for pattern in xss_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning("[SECURITY] Potential XSS detected")
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return text.strip()


def sanitize_email(email: str) -> str:
    """Validate and sanitize email."""
    email = email.strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValueError("Invalid email format")
    return email


def sanitize_uuid(uid: str) -> str:
    """Validate UUID format."""
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    if not re.match(pattern, uid, re.IGNORECASE):
        raise ValueError("Invalid UUID format")
    return uid


# ── Password Validation ───────────────────────────────────────────────────

def validate_password(password: str) -> str:
    """Validate password strength."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain digit")
    return password


# ── Rate Limiting Helper ─────────────────────────────────────────────────

_rate_limit_store: Dict[str, list] = {}


def check_rate_limit(key: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
    """Check if request is within rate limit. Returns True if allowed."""
    now = time.time()
    if key not in _rate_limit_store:
        _rate_limit_store[key] = []

    # Clean old entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < window_seconds]

    if len(_rate_limit_store[key]) >= max_requests:
        return False

    _rate_limit_store[key].append(now)
    return True


# ── Security Headers Middleware ──────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
