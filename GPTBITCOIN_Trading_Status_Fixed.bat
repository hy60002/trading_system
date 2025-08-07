@echo off
cd /d "C:\GPTBITCOIN"

echo.
echo ==========================================
echo    GPTBITCOIN Trading System - STATUS
echo ==========================================
echo.

echo [INFO] Project directory: %CD%
echo.

echo [INFO] Directory structure:
if exist "trading_system" (
    echo [SUCCESS] trading_system directory found
    if exist "trading_system\run_trading_system.py" (
        echo [SUCCESS] run_trading_system.py found
    ) else (
        echo [ERROR] run_trading_system.py NOT found
    )
    if exist "trading_system\main.py" (
        echo [SUCCESS] main.py found
    ) else (
        echo [ERROR] main.py NOT found
    )
) else (
    echo [ERROR] trading_system directory NOT found
)

echo.
echo [INFO] Virtual environment:
if exist ".venv\Scripts\python.exe" (
    echo [SUCCESS] Virtual environment found
    ".venv\Scripts\python.exe" --version
) else (
    echo [ERROR] Virtual environment NOT found
)

echo.
echo [INFO] Running Python processes:
tasklist /fi "imagename eq python.exe" /fo table 2>nul | findstr "python.exe"
if %errorlevel% neq 0 (
    echo [INFO] No Python processes running
)

echo.
echo [INFO] Ports in use:
netstat -ano | findstr ":8000\|:3000" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] No trading system ports in use
)

echo.
echo [INFO] Database files:
if exist "trading_system\advanced_trading_v3.db" (
    echo [SUCCESS] Database file exists
    dir "trading_system\advanced_trading_v3.db" | findstr /v "Directory"
) else (
    echo [INFO] Database file not created yet
)

echo.
pause