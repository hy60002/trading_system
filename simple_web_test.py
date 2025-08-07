#!/usr/bin/env python3
"""
Test if we can actually connect to the trading system web server
"""
import sys
import asyncio
import uvicorn
sys.path.append('trading_system')

from config.config import TradingConfig
from engine.advanced_trading_engine import AdvancedTradingEngine
from api.app import get_app, set_trading_engine

async def start_web_server():
    """Start the actual web server with proper initialization"""
    print("[INIT] Starting trading system web server...")
    
    # Initialize trading engine
    config = TradingConfig()
    engine = AdvancedTradingEngine(config)
    await engine.initialize()
    
    # Set engine for API
    set_trading_engine(engine)
    
    # Get FastAPI app
    app = get_app()
    
    print("[WEB] Starting web server on http://127.0.0.1:8001")
    print("[INFO] Dashboard will be available at: http://127.0.0.1:8001")
    
    # Create uvicorn config
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1", 
        port=8001,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(start_web_server())
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Server error: {e}")