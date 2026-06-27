# ═══════════════════════════════════════════════════════════════
# Hermes V2 — Stop All Services
# ═══════════════════════════════════════════════════════════════

$ErrorActionPreference = "SilentlyContinue"

Write-Host "Stopping Hermes V2 services..." -ForegroundColor Cyan

# Check docker compose
$composeCmd = "docker compose"
try {
    $null = & docker compose version 2>$null
} catch {
    $composeCmd = "docker-compose"
}

# Stop all services
& $composeCmd down 2>&1

Write-Host "All services stopped." -ForegroundColor Green
Write-Host ""
Write-Host "To remove all data: .\stop.ps1 --volumes" -ForegroundColor Yellow
Write-Host "To restart:          .\start.ps1" -ForegroundColor Yellow

# Optional: remove volumes
if ($args -contains "--volumes") {
    Write-Host "Removing volumes..." -ForegroundColor Yellow
    & $composeCmd down -v 2>&1
    Write-Host "All data removed." -ForegroundColor Green
}
