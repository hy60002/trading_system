#!/usr/bin/env python3
"""
Simple Trading System Test
Basic verification of the revised trading system
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

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
    print("Please make sure you're running from the correct directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_system():
    """Simple system test"""
    print("BITGET TRADING SYSTEM v3.0 - Simple Test")
    print("=" * 50)
    
    test_count = 0
    passed_count = 0
    
    try:
        # Test 1: Configuration
        print("Testing configuration...")
        config = TradingConfig.from_env()
        
        if set(config.SYMBOLS) == {"BTCUSDT", "ETHUSDT"}:
            print("✓ Symbols configured correctly (BTC, ETH only)")
            passed_count += 1
        else:
            print("✗ Symbol configuration error")
        test_count += 1
        
        if config.MAX_TOTAL_ALLOCATION == 0.33:
            print("✓ 33% allocation limit configured")
            passed_count += 1
        else:
            print("✗ Allocation limit configuration error")
        test_count += 1
        
        expected_weights = {"BTCUSDT": 0.70, "ETHUSDT": 0.30}
        if config.PORTFOLIO_WEIGHTS == expected_weights:
            print("✓ Portfolio weights configured (BTC 70%, ETH 30%)")
            passed_count += 1
        else:
            print("✗ Portfolio weights configuration error")
        test_count += 1
        
        # Test 2: Database
        print("\nTesting database...")
        db = EnhancedDatabaseManager(config.DATABASE_PATH)
        
        try:
            db.log_system_event('TEST', 'SimpleTest', 'Test event', {'test': True})
            print("✓ Database operations working")
            passed_count += 1
        except Exception as e:
            print(f"✗ Database error: {e}")
        test_count += 1
        
        # Test 3: Notification Manager
        print("\nTesting notification system...")
        notification_manager = NotificationManager(config)
        await notification_manager.initialize()
        
        print("✓ Notification manager initialized")
        passed_count += 1
        test_count += 1
        
        # Test 4: Risk Manager
        print("\nTesting risk management...")
        risk_manager = RiskManager(config, db)
        
        # Test 33% limit check
        limit_check = risk_manager.check_33_percent_limit(
            total_capital=10000,
            current_positions=[],
            requested_amount=1000
        )
        
        if 'within_limit' in limit_check:
            print("✓ 33% limit check working")
            passed_count += 1
        else:
            print("✗ Risk management error")
        test_count += 1
        
        # Test 5: Capital Tracker
        print("\nTesting capital tracking...")
        capital_tracker = CapitalTracker(config, db, notification_manager)
        await capital_tracker.initialize()
        
        try:
            snapshot = await capital_tracker.update_snapshot()
            if snapshot:
                print("✓ Capital tracking working")
                passed_count += 1
            else:
                print("✗ Capital tracking error")
        except Exception as e:
            print(f"✗ Capital tracker error: {e}")
        test_count += 1
        
        # Test 6: Position feasibility
        print("\nTesting position feasibility...")
        try:
            can_open, reason, details = capital_tracker.can_open_position("BTCUSDT", 100.0)
            print(f"✓ Position check working: can_open={can_open}, reason={reason}")
            passed_count += 1
        except Exception as e:
            print(f"✗ Position feasibility error: {e}")
        test_count += 1
        
        # Cleanup
        await capital_tracker.shutdown()
        await notification_manager.shutdown()
        
        # Results
        print("\n" + "=" * 50)
        print("TEST RESULTS")
        print("=" * 50)
        print(f"Total tests: {test_count}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {test_count - passed_count}")
        print(f"Success rate: {(passed_count/test_count*100):.1f}%")
        
        if passed_count == test_count:
            print("\nALL TESTS PASSED! System is ready.")
            return True
        else:
            print(f"\n{test_count - passed_count} TESTS FAILED. Please check the system.")
            return False
            
    except Exception as e:
        print(f"Critical error during testing: {e}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_system())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Test execution error: {e}")
        sys.exit(1)