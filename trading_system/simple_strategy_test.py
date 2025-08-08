#!/usr/bin/env python3
"""
Simple Strategy Test
BTC/ETH/XRP 전략 수정사항 간단 테스트
"""

import os
import sys
import asyncio
import logging

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Import 테스트"""
    print("=== Testing Imports ===")
    
    try:
        from strategies.base_strategy import BaseTradingStrategy
        print("[OK] BaseTradingStrategy imported successfully")
    except Exception as e:
        print(f"[FAIL] BaseTradingStrategy import failed: {e}")
        return False
    
    try:
        from strategies.btc_strategy import BTCTradingStrategy
        print("[OK] BTCTradingStrategy imported successfully")
    except Exception as e:
        print(f"[FAIL] BTCTradingStrategy import failed: {e}")
        return False
    
    try:
        from strategies.eth_strategy import ETHTradingStrategy
        print("[OK] ETHTradingStrategy imported successfully")
    except Exception as e:
        print(f"[FAIL] ETHTradingStrategy import failed: {e}")
        return False
    
    # XRP strategy removed from trading system
    print("[INFO] XRP strategy excluded from trading system")
    
    return True

def test_methods():
    """메서드 존재 테스트"""
    print("\\n=== Testing Methods ===")
    
    try:
        from config.config import TradingConfig
        from strategies.btc_strategy import BTCTradingStrategy
        
        config = TradingConfig()
        strategy = BTCTradingStrategy(config)
        
        required_methods = ['analyze', 'analyze_market', 'generate_signal', 'should_buy', 'should_sell']
        
        for method in required_methods:
            if hasattr(strategy, method):
                print(f"[OK] {method} method exists")
            else:
                print(f"[FAIL] {method} method missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Method test failed: {e}")
        return False

async def test_basic_analysis():
    """기본 분석 테스트"""
    print("\\n=== Testing Basic Analysis ===")
    
    try:
        import pandas as pd
        import numpy as np
        from config.config import TradingConfig
        from strategies.btc_strategy import BTCTradingStrategy
        
        # 더미 데이터 생성
        config = TradingConfig()
        strategy = BTCTradingStrategy(config)
        
        # 충분한 더미 데이터 (200+ 데이터 포인트로 기술적 지표 요구사항 충족)
        data_length = 250  # RSI, SMA 등의 계산을 위한 충분한 데이터
        
        df = pd.DataFrame({
            'open': [50000] * data_length,
            'high': [51000] * data_length,
            'low': [49000] * data_length,
            'close': [50500] * data_length,
            'volume': [1000] * data_length
        })
        
        indicators = {
            'rsi': pd.Series([50] * data_length),
            'ema_20': pd.Series([50000] * data_length),
            'ema_50': pd.Series([49800] * data_length),
            'sma_200': pd.Series([49500] * data_length),
            'macd': pd.Series([10] * data_length),
            'macd_signal': pd.Series([8] * data_length),
            'macd_hist': pd.Series([2] * data_length),
            'adx': pd.Series([30] * data_length),
            'price_position': pd.Series([0.5] * data_length),
            'stoch_rsi': pd.Series([50] * data_length),
            'volume_ratio': pd.Series([1.2] * data_length),
            'obv': pd.Series([1000] * data_length),
            'ichimoku_cloud_top': pd.Series([51000] * data_length),
            'ichimoku_cloud_bottom': pd.Series([49000] * data_length),
            'vwap': pd.Series([50250] * data_length),
            'trend_strength': pd.Series([0.6] * data_length),
            'atr_percent': pd.Series([2.5] * data_length)
        }
        
        # 분석 실행
        result = await strategy.analyze('BTCUSDT', df, indicators)
        
        if isinstance(result, dict) and 'direction' in result:
            print(f"[OK] Analysis successful: {result['direction']}, Score: {result.get('score', 0):.3f}")
            return True
        else:
            print("[FAIL] Analysis failed: Invalid result format")
            return False
            
    except Exception as e:
        print(f"[FAIL] Analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트"""
    print("Starting Simple Strategy Test...")
    
    success = True
    
    # 1. Import 테스트
    if not test_imports():
        success = False
    
    # 2. 메서드 테스트
    if not test_methods():
        success = False
    
    # 3. 기본 분석 테스트
    if not asyncio.run(test_basic_analysis()):
        success = False
    
    print("\\n=== Test Results ===")
    if success:
        print("[SUCCESS] ALL TESTS PASSED!")
        print("Strategy fixes are working correctly.")
    else:
        print("[ERROR] SOME TESTS FAILED!")
        print("Please check the errors above.")
    
    return success

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()