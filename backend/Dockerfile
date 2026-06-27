# ═══════════════════════════════════════════════════════════════
# Hermes V2 — Self-Healing Backend Dockerfile
# ═══════════════════════════════════════════════════════════════
# Features:
#   - Multi-stage build for smaller image
#   - Pip retry logic for network resilience
#   - Non-root user for security
#   - Proper health checks with startup grace period
#   - Graceful shutdown handling via tini init
#   - Dependency layer caching for faster rebuilds
# ═══════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies with retry logic
# Handles network timeouts, DNS failures, and transient errors
RUN pip install --no-cache-dir --retries 5 --timeout 300 \
    -r requirements.txt || \
    (echo "First attempt failed, retrying..." && \
     pip install --no-cache-dir --retries 10 --timeout 600 \
     -r requirements.txt) || \
    (echo "Second attempt failed, final retry..." && \
     pip install --no-cache-dir --retries 15 --timeout 900 \
     -r requirements.txt)

# ── Stage 2: Runtime ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Create non-root user for security
RUN groupadd -r hermes && useradd -r -g hermes -d /app -s /bin/bash hermes

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY --chown=hermes:hermes . .

# Create data directories with proper permissions
USER root
RUN mkdir -p /app/dataset/training_data /app/dataset/exports /app/data /app/logs && \
    chown -R hermes:hermes /app

# Switch to non-root user
USER hermes

# Expose port
EXPOSE 8000

# Health check with startup grace period
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Use tini as init for proper signal handling
ENTRYPOINT ["tini", "--"]

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--timeout-keep-alive", "75", \
     "--access-log", \
     "--reload"]
