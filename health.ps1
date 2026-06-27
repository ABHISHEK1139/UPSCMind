# ═══════════════════════════════════════════════════════════════
# Hermes V2 — Health Check Script
# ═══════════════════════════════════════════════════════════════
# Verifies all services are running and healthy.
# ═══════════════════════════════════════════════════════════════

$ErrorActionPreference = "SilentlyContinue"

function Write-Ok    { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Fail  { param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red }
function Write-Info  { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Cyan }

$containers = @(
    @{ Name = "hermes_traefik";    Url = "http://localhost:8080" },
    @{ Name = "hermes_postgres";   Url = $null },
    @{ Name = "hermes_redis";      Url = $null },
    @{ Name = "hermes_qdrant";     Url = "http://localhost:6333/health" },
    @{ Name = "hermes_neo4j";      Url = "http://localhost:7474" },
    @{ Name = "hermes_minio";      Url = "http://localhost:9000/minio/health/live" },
    @{ Name = "hermes_backend";    Url = "http://localhost:8000/api/health" },
    @{ Name = "hermes_frontend";   Url = "http://localhost:5173" }
)

$failures = 0

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Hermes V2 — Health Check" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

foreach ($c in $containers) {
    $running = & docker inspect --format='{{.State.Running}}' $c.Name 2>$null

    if ($running -ne "true") {
        Write-Fail "$c.Name — not running"
        $failures++
        continue
    }

    if ($c.Url) {
        try {
            $response = Invoke-WebRequest -Uri $c.Url -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Ok "$c.Name — healthy"
            } else {
                Write-Fail "$c.Name — HTTP $($response.StatusCode)"
                $failures++
            }
        } catch {
            Write-Fail "$c.Name — not responding"
            $failures++
        }
    } else {
        Write-Ok "$c.Name — running"
    }
}

Write-Host ""

# Check disk space
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$freeGB = [math]::Round($disk.FreeSpace / 1GB, 1)
if ($freeGB -lt 10) {
    Write-Fail "Low disk space: ${freeGB}GB free (need 10GB+)"
    $failures++
} else {
    Write-Ok "Disk space: ${freeGB}GB free"
}

Write-Host ""

if ($failures -gt 0) {
    Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "  $failures service(s) unhealthy" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host ""
    Write-Host "Fix: .\start.ps1" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  All systems healthy!" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
    exit 0
}
