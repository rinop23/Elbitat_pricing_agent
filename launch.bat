@echo off
title Hotel Pricing Agent

echo ========================================
echo   HOTEL PRICING AGENT
echo   Starting application...
echo ========================================
echo.

REM Kill any existing Python processes to free up ports
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

REM Get the directory where this script is located
set APP_DIR=%~dp0
cd /d "%APP_DIR%"

REM Check if virtual environment exists, activate it
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

echo.
echo [1/2] Starting Backend API on port 8000...
start "Pricing Agent Backend - PORT 8000" /MIN cmd /c "cd /d "%APP_DIR%backend" && python -m uvicorn app.main:app --reload --port 8000"

echo Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

echo.
echo [2/2] Starting User Interface on port 8501...
start "Pricing Agent UI - PORT 8501" cmd /c "cd /d "%APP_DIR%" && streamlit run ui/streamlit_app.py --server.port 8501 --server.address localhost && echo. && echo Application closed. && pause"

echo Waiting for UI to start...
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   APPLICATION READY!
echo ========================================
echo.
echo Backend API: http://localhost:8000
echo User Interface: http://localhost:8501
echo.
echo Opening browser...
start http://localhost:8501

echo.
echo IMPORTANT NOTES:
echo - Two terminal windows have opened (Backend and UI)
echo - DO NOT close those windows while using the app
echo - To stop the application, close both terminal windows
echo - This window can be closed now
echo.
echo ========================================
pause
