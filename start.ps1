# ═══════════════════════════════════════════════════════════════
# Hermes V2 — One-Click Startup Script (Windows)
# ═══════════════════════════════════════════════════════════════
# Downloads, builds, and launches all 10 containers.
# Works on any Windows 10/11 machine with Docker Desktop.
# ═══════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

# ── Colors ─────────────────────────────────────────────────────
function Write-Info    { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok      { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error   { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

# ── Step 1: Check Docker ────────────────────────────────────────
Write-Info "Checking prerequisites..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not found. Install Docker Desktop first:"
    Write-Error "  https://www.docker.com/products/docker-desktop/"
    exit 1
}

$dockerVersion = docker --version 2>$null
if (-not $dockerVersion) {
    Write-Error "Docker is not running. Start Docker Desktop first."
    exit 1
}
Write-Ok "Docker is running"

# Check docker compose
$composeCmd = "docker compose"
try {
    $null = & docker compose version 2>$null
    $composeCmd = "docker compose"
    Write-Ok "Docker Compose (plugin) available"
} catch {
    try {
        $null = & docker-compose version 2>$null
        $composeCmd = "docker-compose"
        Write-Ok "docker-compose (standalone) available"
    } catch {
        Write-Error "Docker Compose not found. Update Docker Desktop."
        exit 1
    }
}

# ── Step 2: Create .env if missing ──────────────────────────────
Write-Info "Setting up environment..."

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Ok "Created .env from .env.example"
        Write-Warn "IMPORTANT: Edit .env and add your OPENROUTER_API_KEY"
    } else {
        Write-Error ".env.example not found"
        exit 1
    }
} else {
    Write-Ok ".env already exists"
}

# ── Step 3: Create required directories ────────────────────────
Write-Info "Creating directories..."

$dirs = @(
    "databases\postgres",
    "databases\neo4j",
    "databases\qdrant",
    "databases\redis",
    "databases\minio",
    "backend\logs",
    "training_data"
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Ok "Directories ready"

# ── Step 4: Pull latest images ──────────────────────────────────
Write-Info "Pulling Docker images (this may take a few minutes)..."

$images = @(
    "postgres:16-alpine",
    "qdrant/qdrant:latest",
    "neo4j:5",
    "redis:7-alpine",
    "minio/minio:latest",
    "traefik:v2.10"
)

foreach ($img in $images) {
    Write-Info "  Pulling $img..."
    try {
        & docker pull $img 2>&1 | Out-Null
        Write-Ok "  $img ready"
    } catch {
        Write-Warn "  Failed to pull $img (will retry during build)"
    }
}

# ── Step 5: Build backend ───────────────────────────────────────
Write-Info "Building backend container..."

try {
    & $composeCmd build backend 2>&1
    Write-Ok "Backend built successfully"
} catch {
    Write-Error "Backend build failed. Check Docker logs."
    exit 1
}

# ── Step 6: Start all services ──────────────────────────────────
Write-Info "Starting all services..."

& $composeCmd up -d 2>&1

Write-Ok "All services started!"

# ── Step 7: Wait for health checks ──────────────────────────────
Write-Info "Waiting for services to be healthy..."

$services = @("postgres", "redis", "qdrant", "neo4j", "backend")
$maxWait = 120
$waited = 0

foreach ($svc in $services) {
    $container = "hermes_$svc"
    Write-Info "  Waiting for $container..."

    $healthy = $false
    $svcWait = 0

    while ($svcWait -lt $maxWait) {
        $status = & docker inspect --format='{{.State.Health.Status}}' $container 2>$null
        if ($status -eq "healthy" -or $status -eq "") {
            $healthy = $true
            break
        }
        Start-Sleep -Seconds 2
        $svcWait += 2
    }

    if ($healthy) {
        Write-Ok "  $container is ready"
    } else {
        Write-Warn "  $container may still be starting..."
    }
}

# ── Step 8: Run tests ───────────────────────────────────────────
Write-Info "Running tests..."

$testOutput = & docker exec hermes_backend python3 -m pytest tests/ -q --tb=short 2>&1
$testExitCode = $LASTEXITCODE

if ($testExitCode -eq 0) {
    Write-Ok "All tests passed!"
} else {
    Write-Warn "Some tests failed (exit code: $testExitCode)"
    Write-Warn "Run manually: docker exec hermes_backend python3 -m pytest tests/ -v"
}

# ── Summary ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Hermes V2 is running!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  API:            http://localhost:8000/api"
Write-Host "  API Docs:       http://localhost:8000/api/docs"
Write-Host "  Traefik:        http://localhost:8080"
Write-Host "  MinIO Console:  http://localhost:9001"
Write-Host ""
Write-Host "  Stop:  .\stop.ps1"
Write-Host "  Logs:  docker logs hermes_backend"
Write-Host "  Test:  docker exec hermes_backend python3 -m pytest tests/ -v"
Write-Host ""
