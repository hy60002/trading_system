#!/usr/bin/env python3
import sys
import os
import asyncio

# Add path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'trading_system'))

from config.config import TradingConfig
from exchange.bitget_manager import EnhancedBitgetExchangeManager

async def test_real_balance():
    print('[TEST] 실제 잔고 조회 테스트...')
    
    try:
        config = TradingConfig()
        exchange = EnhancedBitgetExchangeManager(config)
        
        await exchange.initialize()
        balance = await exchange.get_balance()
        
        print(f'[BALANCE] API 응답: {balance}')
        
        # USDT 잔고 추출
        if 'USDT' in balance and isinstance(balance['USDT'], dict):
            usdt_balance = balance['USDT'].get('free', 0) or balance['USDT'].get('available', 0)
            print(f'[USDT] 사용 가능 잔고: ${usdt_balance:,.2f}')
        elif 'total' in balance:
            print(f'[TOTAL] 총 잔고: ${balance["total"]:,.2f}')
        else:
            print('[ERROR] 잔고 형식을 파싱할 수 없음')
            print(f'[RAW] 원시 응답: {balance}')
            
    except Exception as e:
        print(f'[ERROR] API 연결 실패: {type(e).__name__}: {e}')
        print(f'[FALLBACK] 설정된 기본값: ${config.FALLBACK_BALANCE}')

if __name__ == "__main__":
    asyncio.run(test_real_balance())