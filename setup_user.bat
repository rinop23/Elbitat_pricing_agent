@echo off
echo ========================================
echo   Hotel Pricing Agent - User Setup
echo ========================================
echo.
echo Installing for user: %USERNAME%
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo.
    echo Please install Python 3.8 or higher from:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo Python found! Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies!
    echo Please contact IT support.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Creating Desktop Shortcut
echo ========================================

REM Get current directory
set APP_DIR=%~dp0

REM Create shortcut on desktop
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\Hotel Pricing Agent.lnk'); $s.TargetPath = '%APP_DIR%launch.bat'; $s.WorkingDirectory = '%APP_DIR%'; $s.IconLocation = 'shell32.dll,21'; $s.Description = 'Hotel Pricing Agent'; $s.Save()"

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo A shortcut has been created on your desktop.
echo Double-click it to launch the Hotel Pricing Agent.
echo.
pause
