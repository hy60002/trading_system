@echo off
chcp 65001 >nul
title Simple Install - Trading System

echo.
echo ================================================
echo 📦 간단 설치 - Bitget Trading System v3.0
echo ================================================
echo.

cd /d "%~dp0"

echo 🔍 Python 확인...
python --version
if errorlevel 1 (
    echo ❌ Python이 설치되지 않았습니다.
    pause
    exit /b 1
)

echo.
echo 📦 한 번에 모든 라이브러리 설치...
pip install ccxt fastapi uvicorn openai pandas numpy websockets aiohttp python-dotenv cachetools feedparser

echo.
echo 🔍 설치 확인...
python test_imports.py

echo.
echo ================================================
echo 설치 완료! start_trading_system.bat을 실행하세요.
echo ================================================
pause