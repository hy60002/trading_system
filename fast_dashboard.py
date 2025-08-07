#!/usr/bin/env python3
"""
빠른 대시보드 - HTML 파일 직접 서빙
"""
import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="GPTBITCOIN Dashboard")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """메인 대시보드"""
    html_path = "static/index.html"
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    else:
        return HTMLResponse("""
        <html>
        <head><title>Dashboard Loading...</title></head>
        <body>
            <h1>🚀 GPTBITCOIN Trading System</h1>
            <p>대시보드를 로드하는 중...</p>
            <p>HTML 파일 경로: {}</p>
        </body>
        </html>
        """.format(os.path.abspath(html_path)))

@app.get("/api")
async def api_status():
    return {"message": "Bitget Trading System v3.0", "status": "running"}

@app.get("/status")
async def status():
    return {
        "status": "running",
        "server": "fast_dashboard",
        "html_exists": os.path.exists("static/index.html"),
        "html_path": os.path.abspath("static/index.html")
    }

if __name__ == "__main__":
    print("[FAST] 빠른 대시보드 시작...")
    print(f"[INFO] HTML 파일 존재: {os.path.exists('static/index.html')}")
    print(f"[INFO] HTML 경로: {os.path.abspath('static/index.html')}")
    print("[INFO] 주소: http://localhost:8000")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )