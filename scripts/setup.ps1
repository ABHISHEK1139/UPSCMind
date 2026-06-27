# ═══════════════════════════════════════════════════════════════
# Hermes V2 — First-Time Setup Script
# ═══════════════════════════════════════════════════════════════
# Run this after cloning:
#   .\setup.ps1
#
# Or use the all-in-one command:
#   git clone <repo-url> && cd hermes_v2 && .\setup.ps1
# ═══════════════════════════════════════════════════════════════

param(
    [switch]$SkipDocker,
    [switch]$SkipIngest
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Hermes V2 — First-Time Setup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ═══════════════════════════════════════════════════════════════
# Step 1: Check Prerequisites
# ═══════════════════════════════════════════════════════════════
Write-Host "Step 1: Checking prerequisites..." -ForegroundColor Yellow

# Check Docker
if (-not $SkipDocker) {
    try {
        docker info > $null 2>&1
        Write-Host "  ✅ Docker is running" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Docker is not running!" -ForegroundColor Red
        Write-Host "     Please start Docker Desktop first." -ForegroundColor Yellow
        exit 1
    }
}

# Check Git LFS
try {
    git lfs version > $null 2>&1
    Write-Host "  ✅ Git LFS is installed" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Git LFS not found. Installing..." -ForegroundColor Yellow
    git lfs install
    Write-Host "  ✅ Git LFS installed" -ForegroundColor Green
}

# ═══════════════════════════════════════════════════════════════
# Step 2: Configure Environment
# ═══════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "Step 2: Configuring environment..." -ForegroundColor Yellow

if (-not (Test-Path "$ProjectRoot\.env")) {
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
    Write-Host "  ✅ Created .env from .env.example" -ForegroundColor Green
    Write-Host ""
    Write-Host "  📝 IMPORTANT: Edit .env file with your API keys:" -ForegroundColor Cyan
    Write-Host "     notepad $ProjectRoot\.env" -ForegroundColor White
    Write-Host ""
    Write-Host "  Required:" -ForegroundColor Yellow
    Write-Host "    OPENROUTER_API_KEY=sk-or-v1-your-key-here" -ForegroundColor White
    Write-Host "    Get one at: https://openrouter.ai/settings/credits" -ForegroundColor Cyan
    Write-Host ""
    
    $edit = Read-Host "  Open .env file now? (y/n)"
    if ($edit -eq 'y') {
        Start-Process notepad.exe "$ProjectRoot\.env"
        Write-Host "  ⏳ Waiting for you to save .env..." -ForegroundColor Yellow
        Read-Host "  Press Enter when done"
    }
} else {
    Write-Host "  ✅ .env file already exists" -ForegroundColor Green
}

# ═══════════════════════════════════════════════════════════════
# Step 3: Build Docker Images
# ═══════════════════════════════════════════════════════════════
if (-not $SkipDocker) {
    Write-Host ""
    Write-Host "Step 3: Building Docker images..." -ForegroundColor Yellow
    
    docker compose -f "$ProjectRoot\docker-compose.yml" build --no-cache backend 2>&1 | Out-String
    
    Write-Host "  ✅ Docker images built" -ForegroundColor Green
}

# ═══════════════════════════════════════════════════════════════
# Step 4: Start Services
# ═══════════════════════════════════════════════════════════════
if (-not $SkipDocker) {
    Write-Host ""
    Write-Host "Step 4: Starting services..." -ForegroundColor Yellow
    
    docker compose -f "$ProjectRoot\docker-compose.yml" up -d 2>&1 | Out-String
    
    Write-Host "  ⏳ Waiting for services to start..." -ForegroundColor Yellow
    Start-Sleep -Seconds 20
    
    Write-Host "  ✅ Services started" -ForegroundColor Green
}

# ═══════════════════════════════════════════════════════════════
# Step 5: Ingest Knowledge Base
# ═══════════════════════════════════════════════════════════════
if (-not $SkipDocker -and -not $SkipIngest) {
    Write-Host ""
    Write-Host "Step 5: Ingesting knowledge base..." -ForegroundColor Yellow
    Write-Host "  This will load UPSC questions into Qdrant vector DB..." -ForegroundColor Cyan
    
    docker exec hermes_backend python3 /app/ingest_knowledge_base.py 2>&1 | Out-String
    
    Write-Host "  ✅ Knowledge base ingested" -ForegroundColor Green
}

# ═══════════════════════════════════════════════════════════════
# Step 6: Run Test
# ═══════════════════════════════════════════════════════════════
if (-not $SkipDocker) {
    Write-Host ""
    Write-Host "Step 6: Running quick test..." -ForegroundColor Yellow
    
    docker exec hermes_backend python3 /app/test_upsc.py 2>&1 | Out-String
    
    Write-Host "  ✅ Test complete" -ForegroundColor Green
}

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Setup Complete! 🎉" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Quick commands:" -ForegroundColor Cyan
Write-Host "    .\start.ps1          # Start services" -ForegroundColor White
Write-Host "    .\start.ps1 stop     # Stop services" -ForegroundColor White
Write-Host "    .\start.ps1 test     # Run tests" -ForegroundColor White
Write-Host "    .\start.ps1 logs     # View logs" -ForegroundColor White
Write-Host ""
Write-Host "  Service URLs:" -ForegroundColor Cyan
Write-Host "    API:      http://localhost:8000/api" -ForegroundColor White
Write-Host "    Docs:     http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "    Traefik:  http://localhost:8080" -ForegroundColor White
Write-Host "    MinIO:    http://localhost:9001" -ForegroundColor White
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
