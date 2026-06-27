# ═══════════════════════════════════════════════════════════════
# Hermes V2 — One-Click Startup Script
# ═══════════════════════════════════════════════════════════════
# Usage:
#   .\start.ps1              # Start with defaults
#   .\start.ps1 dev          # Start in dev mode
#   .\start.ps1 stop         # Stop all services
#   .\start.ps1 restart      # Restart all services
#   .\start.ps1 status       # Check service status
#   .\start.ps1 logs         # View logs
#   .\start.ps1 test         # Run test suite
#   .\start.ps1 update       # Update & rebuild
# ═══════════════════════════════════════════════════════════════

param(
    [string]$Command = "start"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

function Write-Header {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  Hermes V2 — UPSC Intelligence System" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Docker {
    try {
        docker info > $null 2>&1
        return $true
    } catch {
        return $false
    }
}

function Test-EnvFile {
    if (-not (Test-Path "$ProjectRoot\.env")) {
        Write-Host "⚠️  .env file not found!" -ForegroundColor Yellow
        Write-Host "   Creating from .env.example..." -ForegroundColor Yellow
        Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
        Write-Host ""
        Write-Host "📝 Please edit .env file with your API keys:" -ForegroundColor Cyan
        Write-Host "   notepad $ProjectRoot\.env" -ForegroundColor White
        Write-Host ""
        return $false
    }
    return $true
}

function Test-ApiKey {
    $envContent = Get-Content "$ProjectRoot\.env" -Raw
    if ($envContent -match "OPENROUTER_API_KEY=sk-or-v1-your-key-here") {
        Write-Host "❌ OPENROUTER_API_KEY not configured!" -ForegroundColor Red
        Write-Host "   Please edit .env file and add your API key." -ForegroundColor Yellow
        Write-Host "   Get one at: https://openrouter.ai/settings/credits" -ForegroundColor Cyan
        return $false
    }
    if ($envContent -match "OPENROUTER_API_KEY=") {
        $key = ($envContent -split "OPENROUTER_API_KEY=")[1] -split "`n" | Select-Object -First 1
        if ($key.Length -lt 20) {
            Write-Host "❌ OPENROUTER_API_KEY looks too short!" -ForegroundColor Red
            return $false
        }
    }
    return $true
}

function Get-ContainerStatus {
    $containers = @("hermes_backend", "hermes_postgres", "hermes_redis", "hermes_qdrant", "hermes_neo4j", "hermes_minio", "hermes_celery_worker", "hermes_celery_beat", "hermes_traefik", "hermes_frontend")
    $running = 0
    $stopped = 0
    
    foreach ($c in $containers) {
        $status = docker inspect --format='{{.State.Status}}' $c 2>$null
        if ($status -eq "running") { $running++ } else { $stopped++ }
    }
    
    return @{ Running = $running; Stopped = $stopped; Total = $containers.Count }
}

# ═══════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════

function Start-Services {
    Write-Header
    
    # Pre-flight checks
    if (-not (Test-Docker)) {
        Write-Host "❌ Docker is not running!" -ForegroundColor Red
        Write-Host "   Please start Docker Desktop first." -ForegroundColor Yellow
        exit 1
    }
    
    if (-not (Test-EnvFile)) { exit 1 }
    if (-not (Test-ApiKey)) { exit 1 }
    
    Write-Host "✅ Pre-flight checks passed" -ForegroundColor Green
    Write-Host ""
    
    # Determine compose file
    $composeFile = "docker-compose.yml"
    if ($Command -eq "prod") {
        $composeFile = "docker-compose.prod.yml"
        Write-Host "🚀 Starting in PRODUCTION mode..." -ForegroundColor Cyan
    } else {
        Write-Host "🔧 Starting in DEVELOPMENT mode..." -ForegroundColor Cyan
    }
    
    # Build if needed
    Write-Host ""
    Write-Host "📦 Building images..." -ForegroundColor Yellow
    docker compose -f "$ProjectRoot\$composeFile" build --no-cache backend 2>&1 | Out-String
    
    # Start services
    Write-Host ""
    Write-Host "🚀 Starting services..." -ForegroundColor Yellow
    docker compose -f "$ProjectRoot\$composeFile" up -d 2>&1 | Out-String
    
    # Wait for health
    Write-Host ""
    Write-Host "⏳ Waiting for services to be healthy..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
    
    $status = Get-ContainerStatus
    Write-Host ""
    Write-Host "✅ Services started!" -ForegroundColor Green
    Write-Host "   Running: $($status.Running)/$($status.Total)" -ForegroundColor White
    Write-Host ""
    Write-Host "📊 Service URLs:" -ForegroundColor Cyan
    Write-Host "   API:      http://localhost:8000/api" -ForegroundColor White
    Write-Host "   Docs:     http://localhost:8000/api/docs" -ForegroundColor White
    Write-Host "   Traefik:  http://localhost:8080" -ForegroundColor White
    Write-Host "   MinIO:    http://localhost:9001" -ForegroundColor White
    Write-Host "   Frontend: http://localhost:3000" -ForegroundColor White
    Write-Host ""
    Write-Host "📝 Quick commands:" -ForegroundColor Cyan
    Write-Host "   .\start.ps1 logs     # View logs" -ForegroundColor White
    Write-Host "   .\start.ps1 test     # Run tests" -ForegroundColor White
    Write-Host "   .\start.ps1 stop     # Stop all" -ForegroundColor White
}

function Stop-Services {
    Write-Header
    Write-Host "🛑 Stopping all services..." -ForegroundColor Yellow
    docker compose -f "$ProjectRoot\docker-compose.yml" down 2>&1 | Out-String
    docker compose -f "$ProjectRoot\docker-compose.prod.yml" down 2>&1 | Out-String
    Write-Host "✅ All services stopped!" -ForegroundColor Green
}

function Restart-Services {
    Stop-Services
    Start-Services
}

function Show-Status {
    Write-Header
    $status = Get-ContainerStatus
    Write-Host "📊 Container Status:" -ForegroundColor Cyan
    Write-Host "   Running: $($status.Running)/$($status.Total)" -ForegroundColor White
    Write-Host ""
    
    $containers = @("hermes_backend", "hermes_postgres", "hermes_redis", "hermes_qdrant", "hermes_neo4j", "hermes_minio", "hermes_celery_worker", "hermes_celery_beat", "hermes_traefik", "hermes_frontend")
    foreach ($c in $containers) {
        $state = docker inspect --format='{{.State.Status}}' $c 2>$null
        $health = docker inspect --format='{{.State.Health.Status}}' $c 2>$null
        $color = if ($state -eq "running") { "Green" } else { "Red" }
        $healthStr = if ($health) { " ($health)" } else { "" }
        Write-Host "   $c : $state$healthStr" -ForegroundColor $color
    }
}

function Show-Logs {
    Write-Header
    Write-Host "📋 Showing logs (Ctrl+C to exit)..." -ForegroundColor Cyan
    docker compose -f "$ProjectRoot\docker-compose.yml" logs -f --tail=100 2>&1
}

function Run-Tests {
    Write-Header
    Write-Host "🧪 Running test suite..." -ForegroundColor Cyan
    docker exec hermes_backend python3 /app/test_upsc.py 2>&1
}

function Update-Project {
    Write-Header
    Write-Host "🔄 Updating project..." -ForegroundColor Cyan
    
    # Pull latest code
    Write-Host "📥 Pulling latest code..." -ForegroundColor Yellow
    git pull 2>&1 | Out-String
    
    # Rebuild
    Write-Host "📦 Rebuilding images..." -ForegroundColor Yellow
    docker compose -f "$ProjectRoot\docker-compose.yml" build --no-cache 2>&1 | Out-String
    
    # Restart
    Write-Host "🔄 Restarting services..." -ForegroundColor Yellow
    docker compose -f "$ProjectRoot\docker-compose.yml" up -d 2>&1 | Out-String
    
    Write-Host "✅ Update complete!" -ForegroundColor Green
}

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

Set-Location $ProjectRoot

switch ($Command) {
    "start"    { Start-Services }
    "prod"     { $Command = "prod"; Start-Services }
    "dev"      { Start-Services }
    "stop"     { Stop-Services }
    "restart"  { Restart-Services }
    "status"   { Show-Status }
    "logs"     { Show-Logs }
    "test"     { Run-Tests }
    "update"   { Update-Project }
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host "Usage: .\start.ps1 {start|dev|prod|stop|restart|status|logs|test|update}" -ForegroundColor Yellow
    }
}
