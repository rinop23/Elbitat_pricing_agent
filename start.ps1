# Hotel Pricing Agent - PowerShell Startup Script

Write-Host "========================================"  -ForegroundColor Cyan
Write-Host "  Hotel Pricing Agent - Startup"  -ForegroundColor Cyan
Write-Host "========================================"  -ForegroundColor Cyan
Write-Host ""

# Start Backend API in new window
Write-Host "Starting Backend API..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; uvicorn app.main:app --reload --port 8000"

# Wait a moment for backend to start
Start-Sleep -Seconds 3

# Start Streamlit UI in new window
Write-Host "Starting Streamlit UI..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "streamlit run ui/streamlit_app.py"

Write-Host ""
Write-Host "========================================"  -ForegroundColor Green
Write-Host "  Application Starting..."  -ForegroundColor Green
Write-Host "========================================"  -ForegroundColor Green
Write-Host ""
Write-Host "Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "Streamlit UI: http://localhost:8501" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to close this window..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
