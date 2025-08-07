@echo off
chcp 65001 >nul
title Install Trading System Requirements

echo.
echo ================================================
echo 📦 Bitget Trading System v3.0 의존성 설치
echo ================================================
echo.

:: 현재 디렉토리를 trading_system으로 변경
cd /d "%~dp0"

:: Python 설치 확인
echo 🔍 Python 설치 확인...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python이 설치되지 않았습니다.
    echo    https://python.org에서 Python을 다운로드하여 설치해주세요.
    pause
    exit /b 1
)

python --version
echo ✅ Python 설치 확인됨
echo.

:: pip 업그레이드
echo 🔄 pip 업그레이드...
python -m pip install --upgrade pip
echo.

:: 필수 라이브러리 설치
echo 📦 필수 라이브러리 설치 중...
echo.

echo [1/12] asyncio (내장 모듈)
echo [2/12] ccxt 설치 중...
pip install ccxt

echo [3/12] fastapi 설치 중...
pip install fastapi

echo [4/12] uvicorn 설치 중...
pip install uvicorn

echo [5/12] openai 설치 중...
pip install openai

echo [6/12] pandas 설치 중...
pip install pandas

echo [7/12] numpy 설치 중...
pip install numpy

echo [8/12] websockets 설치 중...
pip install websockets

echo [9/12] aiohttp 설치 중...
pip install aiohttp

echo [10/12] python-dotenv 설치 중...
pip install python-dotenv

echo [11/12] cachetools 설치 중...
pip install cachetools

echo [12/12] feedparser 설치 중...
pip install feedparser

echo.
echo ================================================
echo ✅ 모든 라이브러리 설치 완료!
echo ================================================
echo.

:: 설치 확인
echo 🔍 설치 확인 중...
python test_imports.py

if errorlevel 1 (
    echo ❌ 일부 라이브러리 설치에 실패했습니다.
    echo    위의 오류 메시지를 확인하고 수동으로 설치해주세요.
) else (
    echo.
    echo 🚀 이제 start_trading_system.bat을 실행하여 거래 시스템을 시작할 수 있습니다!
)

echo.
echo ================================================
pause