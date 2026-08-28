# BookCraft AI — Start Backend (Windows PowerShell)
# Run from the project root: .\scripts\start-backend.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"

Write-Host "=== BookCraft AI — Backend ===" -ForegroundColor Cyan
Write-Host "Backend dir: $BackendDir"

# Create virtual environment if it doesn't exist
$VenvDir = Join-Path $BackendDir ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "`nCreating Python virtual environment..." -ForegroundColor Yellow
    python -m venv $VenvDir
    Write-Host "Virtual environment created." -ForegroundColor Green
}

# Activate venv
$Activate = Join-Path $VenvDir "Scripts\Activate.ps1"
& $Activate

# Install dependencies
Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
pip install -r (Join-Path $BackendDir "requirements.txt") --quiet
Write-Host "Dependencies installed." -ForegroundColor Green

# Copy .env if needed
$EnvFile = Join-Path $Root ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.template") $EnvFile
    Write-Host ".env created from template. Fill in your OPENROUTER_API_KEY." -ForegroundColor Yellow
}

# Start FastAPI with uvicorn
Write-Host "`nStarting FastAPI server at http://localhost:8000 ..." -ForegroundColor Cyan
Set-Location $BackendDir
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
