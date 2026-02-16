# Enterprise Tool Router - Database Shutdown Script
# Commit 09: Postgres local environment

param(
    [switch]$Volumes  # Also remove volumes (wipes data)
)

$ErrorActionPreference = "Stop"

Write-Host "Stopping Enterprise Tool Router Postgres database..." -ForegroundColor Cyan

# Check if Docker is running
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Docker is not running. Nothing to stop."
        exit 0
    }
} catch {
    Write-Warning "Docker is not running. Nothing to stop."
    exit 0
}

if ($Volumes) {
    Write-Warning "WARNING: This will remove all database data!" -ForegroundColor Red
    $confirm = Read-Host "Type 'yes' to confirm data deletion"
    if ($confirm -ne "yes") {
        Write-Host "Aborted. Data was not removed." -ForegroundColor Yellow
        exit 0
    }

    docker compose down -v
    Write-Host "Database stopped and volumes removed." -ForegroundColor Green
} else {
    docker compose down
    Write-Host "Database stopped (data preserved)." -ForegroundColor Green
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to stop Docker Compose services."
    exit 1
}

Write-Host "Done." -ForegroundColor Green
