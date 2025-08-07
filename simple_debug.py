#!/usr/bin/env python3
"""
Simple System Debug
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.append(os.path.join(os.getcwd(), 'trading_system'))
load_dotenv()

async def test_exchange():
    print("=== Exchange Test ===")
    try:
        from trading_system.config.config import TradingConfig
        from trading_system.exchange.bitget_manager import EnhancedBitgetExchangeManager
        
        config = TradingConfig()
        exchange = EnhancedBitgetExchangeManager(config)
        
        print("1. Exchange created")
        
        await exchange.initialize()
        print("2. Exchange initialized")
        
        balance = await exchange.get_balance()
        print("3. Balance fetched:", balance)
        
        if 'USDT' in balance:
            usdt = balance['USDT']
            print(f"   USDT Free: ${usdt.get('free', 0):.2f}")
            print(f"   USDT Total: ${usdt.get('total', 0):.2f}")
        
        await exchange.shutdown()
        print("4. Exchange shutdown")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_capital_tracker():
    print("\n=== Capital Tracker Test ===")
    try:
        from trading_system.config.config import TradingConfig
        from trading_system.database.db_manager import EnhancedDatabaseManager
        from trading_system.notifications.notification_manager import NotificationManager
        from trading_system.managers.capital_tracker import CapitalTracker
        
        config = TradingConfig()
        db = EnhancedDatabaseManager(config.DATABASE_PATH)
        db.initialize_database()
        
        notifier = NotificationManager(config)
        await notifier.initialize()
        
        # Test without exchange object first
        capital_tracker = CapitalTracker(config, db, notifier, None)
        await capital_tracker.initialize()
        
        balance = await capital_tracker._get_total_balance()
        print(f"Capital Tracker Balance: ${balance:.2f}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def run_debug():
    print("=== System Debug Started ===\n")
    
    # Test 1: Exchange
    exchange_ok = await test_exchange()
    
    # Test 2: Capital Tracker
    tracker_ok = await test_capital_tracker()
    
    if exchange_ok and tracker_ok:
        print("\n=== All Tests Passed ===")
        return True
    else:
        print("\n=== Some Tests Failed ===")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_debug())
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")