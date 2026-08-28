# BookCraft AI — Start Both Servers (Windows PowerShell)
# Run from the project root: .\scripts\start-all.ps1
# Opens two PowerShell windows — one for backend, one for frontend.

$Root = Split-Path -Parent $PSScriptRoot

Write-Host "=== BookCraft AI — Starting All Services ===" -ForegroundColor Cyan

# Start backend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$Root\scripts\start-backend.ps1`"" -WindowStyle Normal

Start-Sleep -Seconds 2

# Start frontend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$Root\scripts\start-frontend.ps1`"" -WindowStyle Normal

Write-Host "`nBoth servers are starting in separate windows." -ForegroundColor Green
Write-Host "  Backend  → http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Frontend → http://localhost:3000" -ForegroundColor White
