#!/usr/bin/env python3
import sys
import os
import asyncio

# Add path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'trading_system'))

from config.config import TradingConfig
from database.db_manager import EnhancedDatabaseManager
from engine.advanced_trading_engine import AdvancedTradingEngine
from api.app import get_app, set_trading_engine
import uvicorn

async def initialize_engine():
    """Initialize trading engine"""
    print('[INIT] 거래 엔진 초기화 중...')
    
    config = TradingConfig()
    db = EnhancedDatabaseManager('advanced_trading_v3.db')
    await db.initialize()
    
    # Create trading engine
    engine = AdvancedTradingEngine(config)
    await engine.initialize()
    
    # Set engine for API
    set_trading_engine(engine)
    
    print('[OK] 거래 엔진 초기화 완료')
    return engine

def run_dashboard():
    """Run dashboard server"""
    print('[DASHBOARD] 대시보드 서버 시작 중...')
    
    # Initialize engine first
    engine = asyncio.run(initialize_engine())
    
    # Get FastAPI app
    app = get_app()
    
    print('[SERVER] FastAPI 서버 시작: http://localhost:8080')
    
    # Run server on port 8080 (8000 might be blocked)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8080,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    try:
        run_dashboard()
    except KeyboardInterrupt:
        print('\n[EXIT] 서버 종료')
    except Exception as e:
        print(f'[ERROR] 서버 실행 오류: {e}')
        import traceback
        traceback.print_exc()