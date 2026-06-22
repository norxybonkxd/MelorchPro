@echo off
REM MelOrch-Pro Backend Launcher for Windows

echo.
echo ========================================
echo   MelOrch-Pro Backend Launcher
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo [OK] Python installed
echo.

REM Install dependencies
echo Installing dependencies...
pip install -r requirements-backend.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo [OK] Dependencies installed
echo.

REM Start server
echo.
echo ========================================
echo Starting MelOrch-Pro Backend Server...
echo ========================================
echo.
echo Server URL: http://localhost:5000
echo Web UI: Open index.html in your browser
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py

pause
