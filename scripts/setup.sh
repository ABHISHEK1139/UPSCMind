#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Hermes V2 — One-Click Setup (Linux / macOS)
# ═══════════════════════════════════════════════════════════════
# Builds containers, installs deps, runs health check.
# Works on: Ubuntu 22.04+, Debian 12+, macOS (with Homebrew)
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colors ─────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Hermes V2 — Automated Setup"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── Step 1: Check Docker ────────────────────────────────────────
log_info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    log_error "Docker not found."
    echo "  Install: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null; then
    log_error "Docker is not running. Start Docker Desktop."
    exit 1
fi
log_ok "Docker is running"

# Detect compose command
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
else
    log_error "Docker Compose not found."
    exit 1
fi
log_ok "Docker Compose available"

# ── Step 2: Create .env ─────────────────────────────────────────
log_info "Setting up environment..."

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        log_ok "Created .env from .env.example"
        log_warn "IMPORTANT: Edit .env and add your OPENROUTER_API_KEY"
    else
        log_error ".env.example not found"
        exit 1
    fi
else
    log_ok ".env already exists"
fi

# ── Step 3: Create directories ──────────────────────────────────
log_info "Creating directories..."

mkdir -p databases/{postgres,neo4j,qdrant,redis,minio}
mkdir -p backend/logs training_data
log_ok "Directories ready"

# ── Step 4: Build & Start ───────────────────────────────────────
log_info "Building and starting containers..."
log_info "  This may take 5-10 minutes on first run..."

$COMPOSE build --parallel 2>&1 | tail -5
log_ok "Build complete"

$COMPOSE up -d 2>&1 | tail -5
log_ok "Services starting..."

# ── Step 5: Wait for health ─────────────────────────────────────
log_info "Waiting for services (this may take 2-3 minutes)..."

wait_for_health() {
    local container=$1
    local max_wait=${2:-120}
    local waited=0

    while [ $waited -lt $max_wait ]; do
        local status
        status=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' "$container" 2>/dev/null || echo "missing")

        if [ "$status" = "healthy" ] || [ "$status" = "running" ]; then
            return 0
        fi

        sleep 2
        waited=$((waited + 2))
    done
    return 1
}

CONTAINERS=("hermes_postgres" "hermes_redis" "hermes_qdrant" "hermes_neo4j" "hermes_backend")

for container in "${CONTAINERS[@]}"; do
    if wait_for_health "$container" 120; then
        log_ok "$container is ready"
    else
        log_warn "$container may still be starting..."
    fi
done

# ── Step 6: Run tests ───────────────────────────────────────────
log_info "Running tests..."

if docker exec hermes_backend python3 -m pytest tests/ -q --tb=short 2>&1 | tail -3; then
    log_ok "All tests passed!"
else
    log_warn "Some tests failed. Check with: docker exec hermes_backend python3 -m pytest tests/ -v"
fi

# ── Summary ─────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Hermes V2 is ready!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  API:            http://localhost:8000/api"
echo "  API Docs:       http://localhost:8000/api/docs"
echo "  Traefik:        http://localhost:8080"
echo "  MinIO Console:  http://localhost:9001"
echo ""
echo "  Stop:  ./stop.sh"
echo "  Logs:  docker logs hermes_backend"
echo "  Test:  docker exec hermes_backend python3 -m pytest tests/ -v"
echo ""
