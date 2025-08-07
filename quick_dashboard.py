#!/usr/bin/env python3
"""
빠른 대시보드 - 초기화 없이 바로 웹 서버 실행
"""
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="GPTBITCOIN Quick Dashboard")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GPTBITCOIN Trading Dashboard</title>
        <style>
            body { font-family: Arial; background: #1a1a1a; color: white; padding: 20px; }
            .status { background: #2a2a2a; padding: 20px; border-radius: 10px; margin: 10px 0; }
            .success { color: #4CAF50; }
            .warning { color: #ff9800; }
        </style>
    </head>
    <body>
        <h1>🚀 GPTBITCOIN Trading System</h1>
        
        <div class="status">
            <h3>시스템 상태</h3>
            <p class="success">✅ 웹 서버: 정상 실행</p>
            <p class="warning">⚠️ 거래 엔진: 초기화 중</p>
            <p class="success">✅ ML 예측: 기술적 분석 모드</p>
        </div>
        
        <div class="status">
            <h3>잔고 정보</h3>
            <p><strong>총 잔고:</strong> $1,000.00</p>
            <p><strong>사용 가능:</strong> $1,000.00</p>
            <p><strong>할당 한도:</strong> 100%</p>
        </div>
        
        <div class="status">
            <h3>접속 정보</h3>
            <p>🌐 <strong>현재 주소:</strong> http://0.0.0.0:8000 (모든 인터페이스)</p>
            <p>💻 <strong>로컬 접속:</strong> http://localhost:8000</p>
            <p>🔗 <strong>IP 접속:</strong> http://127.0.0.1:8000</p>
        </div>
        
        <div class="status">
            <h3>빠른 액션</h3>
            <button onclick="location.reload()">새로고침</button>
            <button onclick="window.open('/status')">시스템 상태</button>
        </div>
        
        <p><small>GPTBITCOIN Trading System v3.0 - Quick Dashboard</small></p>
    </body>
    </html>
    """

@app.get("/status")
async def status():
    return {
        "status": "running",
        "server": "quick_dashboard",
        "host": "0.0.0.0",
        "port": 8000,
        "message": "웹 서버가 정상적으로 실행 중입니다"
    }

if __name__ == "__main__":
    print("[QUICK] 빠른 대시보드 시작...")
    print("[INFO] 주소: http://localhost:8000")
    print("[INFO] 모든 인터페이스: http://0.0.0.0:8000")
    
    uvicorn.run(
        app,
        host="0.0.0.0",  # 모든 인터페이스에서 접근 가능
        port=8001,
        log_level="info"
    )