# Hotel Pricing Agent - PowerShell Startup Script

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "  Hotel Pricing Agent - Startup"  -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

# Resolve script directory to make relative paths robust
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start Backend API in new window
Write-Host "Starting Backend API..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoProfile",
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "cd '$AppDir'; `$env:PYTHONPATH='$AppDir'; cd backend; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

# Wait a moment for backend to start
Start-Sleep -Seconds 3

# Start Streamlit UI in new window
Write-Host "Starting Streamlit UI..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoProfile",
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command",
    "cd '$AppDir'; `$env:PYTHONPATH='$AppDir'; streamlit run ui/streamlit_app.py"
)

Write-Host ""
Write-Host "========================================"  -ForegroundColor Green
Write-Host "  Application Starting..."  -ForegroundColor Green
Write-Host "========================================"  -ForegroundColor Green
Write-Host ""
Write-Host "Backend API: http://127.0.0.1:8000" -ForegroundColor White
Write-Host "Streamlit UI: http://localhost:8501" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to close this window..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
