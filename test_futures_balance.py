#!/usr/bin/env python3
"""
Bitget 선물 계좌 잔고 테스트
"""
import os
import sys
import ccxt
from dotenv import load_dotenv

load_dotenv()

def test_futures_balance():
    print("=== Bitget 선물 계좌 잔고 테스트 ===")
    
    api_key = os.getenv('BITGET_API_KEY')
    secret_key = os.getenv('BITGET_SECRET_KEY')
    passphrase = os.getenv('BITGET_PASSPHRASE')
    
    print(f"API Key: {api_key[:15]}..." if api_key else "API Key: Missing")
    
    if not all([api_key, secret_key, passphrase]):
        print("ERROR: Missing API credentials")
        return False
    
    try:
        # 선물 계좌 설정
        exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': secret_key,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # 선물 거래
                'adjustForTimeDifference': True
            }
        })
        
        print("\n1. 선물 계좌 잔고 조회 중...")
        
        # 선물 계좌 잔고
        balance = exchange.fetch_balance()
        print("SUCCESS: 선물 계좌 잔고 조회 성공")
        
        # 상세 잔고 정보 출력
        print(f"\n=== 선물 계좌 잔고 상세 ===")
        
        # USDT 잔고 확인
        if 'USDT' in balance:
            usdt = balance['USDT']
            print(f"USDT:")
            print(f"  Free: ${usdt.get('free', 0):.2f}")
            print(f"  Used: ${usdt.get('used', 0):.2f}")
            print(f"  Total: ${usdt.get('total', 0):.2f}")
        
        # 전체 잔고 구조 확인
        print(f"\n=== 잔고 데이터 구조 ===")
        print(f"Available keys: {list(balance.keys())}")
        
        # info 섹션 확인
        if 'info' in balance:
            info = balance['info']
            print(f"Info type: {type(info)}")
            if isinstance(info, list) and len(info) > 0:
                print(f"Info[0]: {info[0]}")
            elif isinstance(info, dict):
                print(f"Info keys: {list(info.keys())}")
        
        # free/used/total 확인
        for key in ['free', 'used', 'total']:
            if key in balance:
                data = balance[key]
                print(f"{key}: {data}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        print(f"Error Type: {type(e).__name__}")
        
        # 에러 분석
        if "Invalid" in str(e):
            print("→ API 키가 유효하지 않을 수 있습니다.")
        elif "Unauthorized" in str(e):
            print("→ 선물 거래 권한이 없을 수 있습니다.")
        elif "permission" in str(e).lower():
            print("→ 선물 계좌 접근 권한을 확인하세요.")
        
        return False

if __name__ == "__main__":
    success = test_futures_balance()
    if success:
        print("\n✓ 선물 계좌 접속 성공!")
    else:
        print("\n✗ 선물 계좌 접속 실패")