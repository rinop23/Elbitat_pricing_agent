@echo off
echo ========================================
echo   Hotel Pricing Agent - Startup
echo ========================================
echo.

echo Starting Backend API...
start "Pricing Agent Backend" cmd /k "set PYTHONPATH=%CD% && cd backend && uvicorn app.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo Starting Streamlit UI...
start "Pricing Agent UI" cmd /k "set PYTHONPATH=%CD% && streamlit run ui/streamlit_app.py"

echo.
echo ========================================
echo   Application Starting...
echo ========================================
echo.
echo Backend API: http://localhost:8000
echo Streamlit UI: http://localhost:8501
echo.
echo Press any key to close this window...
pause >nul
