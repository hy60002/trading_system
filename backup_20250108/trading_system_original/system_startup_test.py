#!/usr/bin/env python3
"""
System Startup Test
Tests the complete system initialization without starting actual trading
"""

import asyncio
import logging
import sys
from datetime import datetime

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_system_startup():
    """Test complete system startup"""
    print("="*60)
    print("GPTBITCOIN System Startup Test")
    print("="*60)
    
    try:
        # Test 1: Import all modules
        print("1. Module Import Test...")
        from main_trading_system import TradingSystemOrchestrator
        from config.config import TradingConfig
        print("   [SUCCESS] All modules imported")
        
        # Test 2: Configuration loading
        print("\n2. Configuration Loading Test...")
        config = TradingConfig.from_env()
        missing_config = config.validate()
        if missing_config:
            print(f"   [WARNING] Missing config: {missing_config}")
        else:
            print("   [SUCCESS] All required config loaded")
        print(f"   - API Key loaded: {'YES' if config.BITGET_API_KEY else 'NO'}")
        print(f"   - Secret Key loaded: {'YES' if config.BITGET_SECRET_KEY else 'NO'}")
        print(f"   - Passphrase loaded: {'YES' if config.BITGET_PASSPHRASE else 'NO'}")
        
        # Test 3: System orchestrator creation
        print("\n3. System Orchestrator Creation Test...")
        system = TradingSystemOrchestrator()
        print("   [SUCCESS] System orchestrator created")
        
        # Test 4: Basic system status
        print("\n4. Basic System Status Test...")
        status = system.get_system_status()
        print(f"   System status: {status.get('status', 'unknown')}")
        if status.get('status') == 'not_initialized':
            print("   [INFO] System not yet initialized (normal)")
        
        # Test 5: Trading engine components (without full initialization)
        print("\n5. Trading Engine Components Test...")
        try:
            from engine.advanced_trading_engine import AdvancedTradingEngine
            from exchange.bitget_manager import EnhancedBitgetExchangeManager
            from database.db_manager import EnhancedDatabaseManager
            print("   [SUCCESS] All core components imported")
        except ImportError as e:
            print(f"   [ERROR] Component import failed: {e}")
            return False
        
        print("\n" + "="*60)
        print("System Startup Test Completed Successfully!")
        print("All core modules loaded successfully.")
        print("To start actual trading, run main_trading_system.py")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] System test failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_system_startup())
    sys.exit(0 if result else 1)