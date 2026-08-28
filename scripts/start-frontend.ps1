# BookCraft AI — Start Frontend (Windows PowerShell)
# Run from the project root: .\scripts\start-frontend.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"

Write-Host "=== BookCraft AI — Frontend ===" -ForegroundColor Cyan
Write-Host "Frontend dir: $FrontendDir"

Set-Location $FrontendDir

# Install node_modules if needed
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "`nInstalling npm dependencies..." -ForegroundColor Yellow
    npm install
    Write-Host "Dependencies installed." -ForegroundColor Green
}

Write-Host "`nStarting Next.js dev server at http://localhost:3000 ..." -ForegroundColor Cyan
npm run dev
