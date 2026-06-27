#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Hermes V2 — Stop All Services
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "Stopping Hermes V2 services..."

# Detect compose command
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
else
    echo "Docker Compose not found"
    exit 1
fi

$COMPOSE down

echo "All services stopped."
echo ""
echo "To remove all data: ./scripts/stop.sh --volumes"
echo "To restart:          ./scripts/start.sh"

# Optional: remove volumes
if [[ "${1:-}" == "--volumes" ]]; then
    echo "Removing volumes..."
    $COMPOSE down -v
    echo "All data removed."
fi
