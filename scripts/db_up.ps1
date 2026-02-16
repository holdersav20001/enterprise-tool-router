# Enterprise Tool Router - Database Startup Script
# Commit 09: Postgres local environment

param(
    [switch]$Wait
)

$ErrorActionPreference = "Stop"

Write-Host "Starting Enterprise Tool Router Postgres database..." -ForegroundColor Cyan

# Check if Docker is running
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker is not running. Please start Docker Desktop first."
        exit 1
    }
} catch {
    Write-Error "Docker is not running. Please start Docker Desktop first."
    exit 1
}

# Start the database
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start Docker Compose services."
    exit 1
}

Write-Host "Waiting for Postgres to be ready..." -ForegroundColor Yellow

# Wait for healthcheck
$maxAttempts = 30
$attempt = 0
$healthy = $false

while ($attempt -lt $maxAttempts -and -not $healthy) {
    $attempt++
    Start-Sleep -Seconds 1

    $health = docker inspect --format='{{.State.Health.Status}}' etr-postgres 2>&1

    if ($health -eq "healthy") {
        $healthy = $true
    } else {
        Write-Host "  Attempt $attempt/$maxAttempts - Status: $health" -ForegroundColor Gray
    }
}

if (-not $healthy) {
    Write-Error "Postgres failed to become healthy within timeout."
    exit 1
}

Write-Host "Postgres is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Connection details:" -ForegroundColor Cyan
Write-Host "  Host: localhost" -ForegroundColor White
Write-Host "  Port: 5432" -ForegroundColor White
Write-Host "  Database: etr_db" -ForegroundColor White
Write-Host "  Username: etr_user" -ForegroundColor White
Write-Host "  Password: etr_password" -ForegroundColor White
Write-Host ""
Write-Host "To connect with psql:" -ForegroundColor Cyan
Write-Host "  docker exec -it etr-postgres psql -U etr_user -d etr_db" -ForegroundColor White
Write-Host ""

if ($Wait) {
    Write-Host "Press any key to continue..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
