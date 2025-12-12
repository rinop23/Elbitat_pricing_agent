@echo off
echo ========================================
echo   HOTEL PRICING AGENT - INSTALLATION
echo ========================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo WARNING: Not running as Administrator
    echo Some features may require admin rights
    echo.
)

REM Check Python installation
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ========================================
    echo   ERROR: Python is not installed!
    echo ========================================
    echo.
    echo Please install Python 3.8 or higher:
    echo 1. Go to https://www.python.org/downloads/
    echo 2. Download Python 3.11 or newer
    echo 3. During installation, CHECK "Add Python to PATH"
    echo 4. Restart your computer
    echo 5. Run this installer again
    echo.
    pause
    exit /b 1
)

python --version
echo Python found!
echo.

REM Get application directory
set APP_DIR=%~dp0
cd /d "%APP_DIR%"

echo ========================================
echo   Installing Dependencies
echo ========================================
echo.
echo This may take 2-3 minutes...
echo.

REM Upgrade pip first
python -m pip install --upgrade pip

REM Install requirements
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ========================================
    echo   ERROR: Installation failed!
    echo ========================================
    echo.
    echo Please check your internet connection and try again.
    echo If the problem persists, contact IT support.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Creating Desktop Shortcut
echo ========================================
echo.

REM Create desktop shortcut
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\Hotel Pricing Agent.lnk'); $s.TargetPath = '%APP_DIR%launch.bat'; $s.WorkingDirectory = '%APP_DIR%'; $s.IconLocation = 'shell32.dll,21'; $s.Description = 'Hotel Pricing Agent - Smart Pricing Recommendations'; $s.Save()"

echo Desktop shortcut created!
echo.

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo Creating .env configuration file...
    echo LIGHTHOUSE_PROPERTY_ID=>> .env
    echo LIGHTHOUSE_API_KEY=>> .env
    echo SB_PROPERTY_ID=>> .env
    echo SB_RATE_PLAN_ID=BAR>> .env
    echo CURRENCY=EUR>> .env
    echo DRY_RUN=true>> .env
    echo API_BASE_URL=http://localhost:8000>> .env
    echo.
    echo NOTE: Please edit .env file with your API credentials
)

echo.
echo ========================================
echo   INSTALLATION COMPLETE!
echo ========================================
echo.
echo Next steps:
echo 1. Edit the .env file with your API credentials
echo 2. Launch using the desktop shortcut
echo    OR
echo    Run launch.bat from this folder
echo.
echo The application will start automatically in your browser.
echo.
echo For help, see:
echo - INSTALL_GUIDE.md (Installation instructions)
echo - USER_GUIDE.md (How to use the application)
echo - QUICK_START.md (Quick reference)
echo.
pause
