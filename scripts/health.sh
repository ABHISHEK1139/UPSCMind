#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Hermes V2 — Health Check
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Hermes V2 — Health Check"
echo "═══════════════════════════════════════════════════════"
echo ""

FAILURES=0

check_container() {
    local name=$1
    local url=${2:-}

    local status
    status=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' "$name" 2>/dev/null || echo "missing")

    if [ "$status" = "missing" ]; then
        fail "$name — not found"
        FAILURES=$((FAILURES + 1))
        return
    fi

    if [ -n "$url" ]; then
        if curl -sf -o /dev/null --max-time 5 "$url" 2>/dev/null; then
            ok "$name — healthy"
        else
            fail "$name — not responding"
            FAILURES=$((FAILURES + 1))
        fi
    else
        if [ "$status" = "running" ] || [ "$status" = "healthy" ]; then
            ok "$name — $status"
        else
            fail "$name — $status"
            FAILURES=$((FAILURES + 1))
        fi
    fi
}

check_container "hermes_traefik"    "http://localhost:8080"
check_container "hermes_postgres"
check_container "hermes_redis"
check_container "hermes_qdrant"     "http://localhost:6333/health"
check_container "hermes_neo4j"      "http://localhost:7474"
check_container "hermes_minio"      "http://localhost:9000/minio/health/live"
check_container "hermes_backend"    "http://localhost:8000/api/health"
check_container "hermes_frontend"   "http://localhost:5173"

echo ""

if [ $FAILURES -gt 0 ]; then
    echo "═══════════════════════════════════════════════════════"
    echo "  $FAILURES service(s) unhealthy"
    echo "═══════════════════════════════════════════════════════"
    echo ""
    echo "Fix: ./scripts/setup.sh"
    exit 1
else
    echo "═══════════════════════════════════════════════════════"
    echo "  All systems healthy!"
    echo "═══════════════════════════════════════════════════════"
    exit 0
fi
