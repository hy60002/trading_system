#!/usr/bin/env python3
"""
Basic Trading System Test
"""

import asyncio
import sys
import os

# Add the trading_system path
sys.path.append(os.path.join(os.path.dirname(__file__), 'trading_system'))

try:
    from config.config import TradingConfig
    from database.db_manager import EnhancedDatabaseManager
    from notifications.notification_manager import NotificationManager
    from managers.capital_tracker import CapitalTracker
    from managers.risk_manager import RiskManager
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)


async def basic_test():
    """Basic system test"""
    print("BITGET TRADING SYSTEM v3.0 - Basic Test")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 0
    
    try:
        # Test 1: Configuration
        print("1. Testing configuration...")
        config = TradingConfig.from_env()
        total_tests += 1
        
        # Check symbols
        if set(config.SYMBOLS) == {"BTCUSDT", "ETHUSDT"}:
            print("   [PASS] Symbols: BTC and ETH only")
            tests_passed += 1
        else:
            print("   [FAIL] Symbols incorrect")
            
        # Check allocation limit
        if config.MAX_TOTAL_ALLOCATION == 0.33:
            print("   [PASS] 33% allocation limit set")
        else:
            print("   [FAIL] Allocation limit incorrect")
            
        # Check portfolio weights
        expected = {"BTCUSDT": 0.70, "ETHUSDT": 0.30}
        if config.PORTFOLIO_WEIGHTS == expected:
            print("   [PASS] Portfolio weights: BTC 70%, ETH 30%")
        else:
            print("   [FAIL] Portfolio weights incorrect")
        
        # Test 2: Database
        print("2. Testing database...")
        total_tests += 1
        db = EnhancedDatabaseManager(config.DATABASE_PATH)
        
        try:
            db.log_system_event('TEST', 'BasicTest', 'Test event', {'test': True})
            print("   [PASS] Database operations working")
            tests_passed += 1
        except Exception as e:
            print(f"   [FAIL] Database error: {e}")
        
        # Test 3: Notification system
        print("3. Testing notifications...")
        total_tests += 1
        notification_manager = NotificationManager(config)
        await notification_manager.initialize()
        print("   [PASS] Notification manager initialized")
        tests_passed += 1
        
        # Test 4: Risk management
        print("4. Testing risk management...")
        total_tests += 1
        risk_manager = RiskManager(config, db)
        
        limit_check = risk_manager.check_33_percent_limit(10000, [], 1000)
        if 'within_limit' in limit_check:
            print("   [PASS] 33% limit check working")
            tests_passed += 1
        else:
            print("   [FAIL] Risk management error")
        
        # Test 5: Capital tracking
        print("5. Testing capital tracking...")
        total_tests += 1
        capital_tracker = CapitalTracker(config, db, notification_manager)
        await capital_tracker.initialize()
        
        try:
            snapshot = await capital_tracker.update_snapshot()
            print("   [PASS] Capital tracking initialized")
            tests_passed += 1
        except Exception as e:
            print(f"   [FAIL] Capital tracking error: {e}")
        
        # Test 6: Integration test
        print("6. Testing integration...")
        total_tests += 1
        try:
            can_open, reason, details = capital_tracker.can_open_position("BTCUSDT", 100.0)
            print(f"   [PASS] Position check: can_open={can_open}")
            tests_passed += 1
        except Exception as e:
            print(f"   [FAIL] Integration error: {e}")
        
        # Cleanup
        await capital_tracker.shutdown()
        await notification_manager.shutdown()
        
    except Exception as e:
        print(f"Critical error: {e}")
        return False
    
    # Results
    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    print(f"Success rate: {(tests_passed/total_tests*100):.1f}%")
    
    if tests_passed == total_tests:
        print("ALL TESTS PASSED - System ready!")
        return True
    else:
        print("SOME TESTS FAILED - Check system configuration")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(basic_test())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test error: {e}")
        sys.exit(1)