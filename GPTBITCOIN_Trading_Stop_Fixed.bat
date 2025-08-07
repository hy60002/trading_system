@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================
echo    GPTBITCOIN Trading System - STOP
echo ==========================================
echo.

echo [INFO] Step 1: Terminating Python processes...

:: Kill specific trading system processes
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    set "pid=%%~i"
    for /f "delims=" %%j in ('wmic process where "processid=!pid!" get commandline /value 2^>nul ^| findstr CommandLine') do (
        echo %%j | findstr /i "trading_system\|run_trading_system\|main_trading_system" >nul
        if !errorlevel!==0 (
            echo [INFO] Killing trading system process PID: !pid!
            taskkill /pid !pid! /f /t >nul 2>&1
        )
    )
)

echo [INFO] Step 2: Terminating port processes...

:: Kill processes on specific ports
for /f "tokens=5" %%i in ('netstat -ano 2^>nul ^| findstr ":8000.*LISTENING"') do (
    echo [INFO] Killing process on port 8000, PID: %%i
    taskkill /pid %%i /f /t >nul 2>&1
)

for /f "tokens=5" %%i in ('netstat -ano 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo [INFO] Killing process on port 3000, PID: %%i
    taskkill /pid %%i /f /t >nul 2>&1
)

echo [INFO] Step 3: Cleaning up...
timeout /t 2 /nobreak >nul

echo [INFO] Final check:
netstat -ano | findstr ":8000\|:3000" >nul
if %errorlevel%==0 (
    echo [WARNING] Some ports may still be in use
) else (
    echo [SUCCESS] All ports released
)

echo.
echo [SUCCESS] GPTBITCOIN Trading System stopped!
echo [INFO] Dashboard should be inaccessible at http://localhost:8000
echo.

pause