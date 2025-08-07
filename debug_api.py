#!/usr/bin/env python3
"""
API 연동 디버그 테스트
"""
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# 프로젝트 경로 추가
sys.path.append(os.path.join(os.getcwd(), 'trading_system'))

# 환경 변수 로드
load_dotenv()

async def test_system_components():
    """시스템 구성 요소별 테스트"""
    print("=== 시스템 구성 요소 테스트 ===\n")
    
    # 1. 설정 테스트
    print("1. 설정 테스트...")
    try:
        from trading_system.config.config import TradingConfig
        config = TradingConfig()
        print(f"   ✓ 설정 로드 성공")
        print(f"   - FALLBACK_BALANCE: ${config.FALLBACK_BALANCE}")
        print(f"   - CAPITAL_ALLOCATION_LIMIT: {config.CAPITAL_ALLOCATION_LIMIT}")
        print(f"   - API 키 존재: {bool(config.BITGET_API_KEY)}")
    except Exception as e:
        print(f"   ✗ 설정 로드 실패: {e}")
        return False
    
    # 2. 거래소 매니저 테스트
    print("\n2. 거래소 매니저 테스트...")
    try:
        from trading_system.exchange.bitget_manager import EnhancedBitgetExchangeManager
        exchange = EnhancedBitgetExchangeManager(config)
        print(f"   ✓ 거래소 매니저 생성 성공")
        
        # 초기화 테스트
        await exchange.initialize()
        print(f"   ✓ 거래소 초기화 성공")
        
        # 잔고 테스트
        balance = await exchange.get_balance()
        print(f"   ✓ 잔고 조회 성공: {balance}")
        
        if 'USDT' in balance:
            usdt_balance = balance['USDT']
            print(f"   - USDT Free: ${usdt_balance.get('free', 0):.2f}")
            print(f"   - USDT Total: ${usdt_balance.get('total', 0):.2f}")
        
        await exchange.shutdown()
        
    except Exception as e:
        print(f"   ✗ 거래소 매니저 실패: {e}")
        print(f"   에러 타입: {type(e).__name__}")
        return False
    
    # 3. 데이터베이스 테스트
    print("\n3. 데이터베이스 테스트...")
    try:
        from trading_system.database.db_manager import EnhancedDatabaseManager
        db = EnhancedDatabaseManager(config.DATABASE_PATH)
        db.initialize_database()
        print(f"   ✓ 데이터베이스 초기화 성공")
        
        # 잔고 저장/조회 테스트
        test_balance = {'total_balance': 2000.0, 'free_balance': 2000.0}
        db.save_balance_snapshot(test_balance)
        saved_balance = db.get_latest_balance()
        print(f"   ✓ 잔고 저장/조회 테스트 성공: {saved_balance}")
        
    except Exception as e:
        print(f"   ✗ 데이터베이스 테스트 실패: {e}")
        return False
    
    # 4. 자본 추적 시스템 테스트
    print("\n4. 자본 추적 시스템 테스트...")
    try:
        from trading_system.managers.capital_tracker import CapitalTracker
        from trading_system.notifications.notification_manager import NotificationManager
        
        notifier = NotificationManager(config)
        await notifier.initialize()
        
        capital_tracker = CapitalTracker(config, db, notifier, exchange)
        await capital_tracker.initialize()
        print(f"   ✓ 자본 추적 시스템 초기화 성공")
        
        # 잔고 조회 테스트
        balance = await capital_tracker._get_total_balance()
        print(f"   ✓ 자본 추적 잔고 조회: ${balance:.2f}")
        
    except Exception as e:
        print(f"   ✗ 자본 추적 시스템 실패: {e}")
        print(f"   에러 타입: {type(e).__name__}")
        return False
    
    print("\n=== 모든 테스트 통과! ===")
    return True

async def test_api_endpoints():
    """API 엔드포인트 테스트"""
    print("\n=== API 엔드포인트 테스트 ===")
    
    try:
        from trading_system.api.app import get_app, set_trading_engine
        from trading_system.engine.advanced_trading_engine import AdvancedTradingEngine
        from trading_system.config.config import TradingConfig
        
        # 엔진 생성 및 설정
        config = TradingConfig()
        engine = AdvancedTradingEngine(config)
        await engine.initialize()
        
        set_trading_engine(engine)
        app = get_app()
        
        print("✓ API 앱 초기화 성공")
        print("✓ 거래 엔진 연결 성공")
        
        return True
        
    except Exception as e:
        print(f"✗ API 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    
    async def run_tests():
        print("🔧 시스템 진단 시작...\n")
        
        # 시스템 구성 요소 테스트
        component_test = await test_system_components()
        
        if component_test:
            # API 엔드포인트 테스트
            api_test = await test_api_endpoints()
            
            if api_test:
                print("\n🎉 모든 시스템이 정상 작동합니다!")
                return True
        
        print("\n❌ 시스템에 문제가 발견되었습니다.")
        return False
    
    # 테스트 실행
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)