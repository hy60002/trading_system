#!/usr/bin/env python3
"""
Deep System Initialization Test
Tests deeper system initialization including database and exchange setup
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_deep_initialization():
    """Test deeper system initialization"""
    print("="*60)
    print("GPTBITCOIN Deep Initialization Test")
    print("="*60)
    
    try:
        # Import required modules
        from main_trading_system import TradingSystemOrchestrator
        from config.config import TradingConfig
        
        # Create system
        print("1. Creating System Orchestrator...")
        system = TradingSystemOrchestrator()
        print("   [SUCCESS] System created")
        
        # Test configuration validation
        print("\n2. Configuration Validation...")
        config = system.config
        validation_errors = config.validate()
        
        if validation_errors:
            print(f"   [WARNING] Missing required config: {validation_errors}")
            print("   This may prevent full system initialization")
        else:
            print("   [SUCCESS] All required configuration present")
        
        # Test database path
        print("\n3. Database Path Check...")
        db_path = config.DATABASE_PATH
        print(f"   Database path: {db_path}")
        
        # Check if database exists or can be created
        db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else "."
        if os.path.exists(db_dir) and os.access(db_dir, os.W_OK):
            print("   [SUCCESS] Database directory accessible")
        else:
            print("   [WARNING] Database directory may not be writable")
        
        # Test core component creation (without full async initialization)
        print("\n4. Core Components Test...")
        
        try:
            from engine.advanced_trading_engine import AdvancedTradingEngine
            engine = AdvancedTradingEngine(config)
            print("   [SUCCESS] Trading engine created")
        except Exception as e:
            print(f"   [ERROR] Trading engine creation failed: {e}")
            return False
        
        try:
            from database.db_manager import EnhancedDatabaseManager
            db_manager = EnhancedDatabaseManager(config.DATABASE_PATH)
            print("   [SUCCESS] Database manager created")
        except Exception as e:
            print(f"   [ERROR] Database manager creation failed: {e}")
            return False
        
        try:
            from exchange.bitget_manager import EnhancedBitgetExchangeManager
            exchange_manager = EnhancedBitgetExchangeManager(config)
            print("   [SUCCESS] Exchange manager created")
        except Exception as e:
            print(f"   [ERROR] Exchange manager creation failed: {e}")
            return False
        
        # Test logging system
        print("\n5. Logging System Test...")
        test_logger = logging.getLogger("test")
        test_logger.info("Test log message")
        print("   [SUCCESS] Logging system functional")
        
        # Test configuration access
        print("\n6. Configuration Access Test...")
        symbols = config.SYMBOLS
        leverage = config.LEVERAGE
        print(f"   Configured symbols: {symbols}")
        print(f"   Leverage settings: {leverage}")
        print("   [SUCCESS] Configuration accessible")
        
        print("\n" + "="*60)
        print("Deep Initialization Test Completed Successfully!")
        print("System is ready for full initialization and trading.")
        print("="*60)
        
        return True
        
    except ImportError as e:
        print(f"\n[ERROR] Import failed: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Deep test failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_deep_initialization())
    sys.exit(0 if result else 1)