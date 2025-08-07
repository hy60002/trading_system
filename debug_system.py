#!/usr/bin/env python3
"""
Debug script to find where the system is hanging
"""
import sys
import asyncio
import traceback
sys.path.append('trading_system')

from config.config import TradingConfig
from engine.advanced_trading_engine import AdvancedTradingEngine

async def debug_initialization():
    """Debug each initialization step"""
    print("[DEBUG] Starting system debug...")
    
    try:
        print("[DEBUG] 1. Creating config...")
        config = TradingConfig()
        print("[DEBUG] OK Config created")
        
        print("[DEBUG] 2. Creating engine...")
        engine = AdvancedTradingEngine(config)
        print("[DEBUG] OK Engine created")
        
        print("[DEBUG] 3. Starting engine initialization...")
        await engine.initialize()
        print("[DEBUG] OK Engine initialized")
        
        print("[DEBUG] 4. Getting system status...")
        status = engine.get_system_status()
        print(f"[DEBUG] Status: {status}")
        
        print("[DEBUG] 5. Testing API app import...")
        from api.app import get_app
        app = get_app()
        print("[DEBUG] OK API app imported")
        
        print("[DEBUG] System is ready!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Debug failed at step: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_initialization())
    if result:
        print("[SUCCESS] All components are working!")
    else:
        print("[FAIL] System has issues!")