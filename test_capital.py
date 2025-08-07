#!/usr/bin/env python3
import sys
import os
import asyncio

# Add path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'trading_system'))

from config.config import TradingConfig
from database.db_manager import EnhancedDatabaseManager  
from managers.capital_tracker import CapitalTracker
from notifications.notification_manager import NotificationManager

async def test_capital_tracker():
    print('[TEST] Capital Tracker 값 확인 중...')
    
    try:
        config = TradingConfig()
        db = EnhancedDatabaseManager('test.db')
        notif = NotificationManager(config)
        
        # Capital Tracker 생성 (exchange 없이)
        tracker = CapitalTracker(config, db, notif, exchange=None)
        
        print(f'[CONFIG] FALLBACK_BALANCE: ${config.FALLBACK_BALANCE}')
        print(f'[CONFIG] CAPITAL_ALLOCATION_LIMIT: {config.CAPITAL_ALLOCATION_LIMIT:.0%}')
        print(f'[TRACKER] fallback_balance: ${tracker.fallback_balance}')
        print(f'[TRACKER] allocation_limit: {tracker.allocation_limit:.0%}')
        
        # 실제 잔고 조회 테스트
        balance = await tracker._get_total_balance()
        print(f'[BALANCE] 조회된 잔고: ${balance:,.2f}')
        
    except Exception as e:
        print(f'[ERROR] {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_capital_tracker())