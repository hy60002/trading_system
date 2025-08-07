@echo off
setlocal enabledelayedexpansion
cd /d "C:\GPTBITCOIN"

echo.
echo ==========================================
echo    GPTBITCOIN Trading System v3.0
echo ==========================================
echo.

echo [INFO] Activating virtual environment...
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv .venv
    pause
    exit /b 1
)

echo [INFO] Moving to trading_system directory...
if exist "trading_system" (
    cd trading_system
) else (
    echo [ERROR] trading_system directory not found!
    echo Current directory: %CD%
    dir /b
    pause
    exit /b 1
)

echo [INFO] Checking system status...
if exist "run_trading_system.py" (
    echo [SUCCESS] run_trading_system.py found
    python run_trading_system.py --status
) else (
    echo [ERROR] run_trading_system.py not found!
    echo Files in current directory:
    dir /b *.py
    pause
    exit /b 1
)

if %errorlevel% neq 0 (
    echo [ERROR] System status check failed!
    echo [INFO] Try installing dependencies with: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo [INFO] Starting trading system...
echo [INFO] Web Dashboard: http://localhost:8000
echo [INFO] Press Ctrl+C to stop or run stop batch file
echo.

python run_trading_system.py

echo.
echo [INFO] Trading system stopped.
pause