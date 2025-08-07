#!/usr/bin/env python3
"""
디버그용 간단 서버 - 에러 상세 로깅
"""
import traceback
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Debug Server")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def root():
    """메인 페이지"""
    return HTMLResponse("""
    <html>
    <head>
        <title>Debug Server</title>
        <style>
            body { 
                font-family: Arial; 
                background: #1a1a1a; 
                color: white; 
                padding: 20px; 
                margin: 0;
            }
            .status { 
                background: #2a2a2a; 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 8px; 
            }
            .success { color: #4CAF50; }
            .error { color: #f44336; }
            .info { color: #2196F3; }
        </style>
    </head>
    <body>
        <h1>🔧 GPTBITCOIN Debug Server</h1>
        
        <div class="status">
            <h3>서버 상태</h3>
            <p class="success">✅ 서버 정상 실행 중</p>
            <p class="info">🌐 포트: 8000</p>
            <p class="info">🕒 시작 시간: 방금 전</p>
        </div>
        
        <div class="status">
            <h3>테스트 API</h3>
            <ul>
                <li><a href="/status" style="color: #4CAF50;">/status</a> - 시스템 상태</li>
                <li><a href="/test" style="color: #4CAF50;">/test</a> - 테스트 엔드포인트</li>
            </ul>
        </div>
        
        <div class="status">
            <h3>실시간 상태</h3>
            <p id="current-time"></p>
        </div>
        
        <script>
            function updateTime() {
                document.getElementById('current-time').innerHTML = 
                    '🕒 현재 시각: ' + new Date().toLocaleString('ko-KR');
            }
            setInterval(updateTime, 1000);
            updateTime();
        </script>
    </body>
    </html>
    """)

@app.get("/status")
async def status():
    """상태 확인"""
    try:
        return JSONResponse({
            "ok": True,
            "status": "running",
            "server": "debug_server",
            "message": "서버가 정상적으로 작동하고 있습니다"
        })
    except Exception as e:
        print(f"[ERROR] Status endpoint error: {e}")
        print(f"[TRACE] {traceback.format_exc()}")
        return JSONResponse({
            "ok": False,
            "error": str(e)
        }, status_code=500)

@app.get("/test")
async def test():
    """테스트 엔드포인트"""
    try:
        return JSONResponse({
            "ok": True,
            "message": "테스트 성공",
            "data": {
                "test_number": 12345,
                "test_string": "Hello World",
                "test_array": [1, 2, 3, 4, 5]
            }
        })
    except Exception as e:
        print(f"[ERROR] Test endpoint error: {e}")
        print(f"[TRACE] {traceback.format_exc()}")
        return JSONResponse({
            "ok": False,
            "error": str(e)
        }, status_code=500)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """글로벌 예외 처리"""
    print(f"[GLOBAL ERROR] {request.method} {request.url}")
    print(f"[ERROR] {str(exc)}")
    print(f"[TRACE] {traceback.format_exc()}")
    
    return JSONResponse({
        "ok": False,
        "error": f"서버 에러: {str(exc)}",
        "path": str(request.url)
    }, status_code=500)

if __name__ == "__main__":
    print("=" * 50)
    print("[DEBUG] 디버그 서버 시작...")
    print("[INFO] 주소: http://localhost:8000")
    print("[INFO] 모든 에러가 콘솔에 출력됩니다")
    print("=" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="debug"
    )