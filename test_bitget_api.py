#!/usr/bin/env python3
"""
Bitget API 연결 테스트
"""
import os
import sys
import ccxt
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def test_bitget_connection():
    """Bitget API 연결 테스트"""
    print("=== Bitget API 연결 테스트 ===")
    
    # API 키 확인
    api_key = os.getenv('BITGET_API_KEY')
    secret_key = os.getenv('BITGET_SECRET_KEY')
    passphrase = os.getenv('BITGET_PASSPHRASE')
    
    print(f"API Key: {api_key[:10]}..." if api_key else "API Key: Not found")
    print(f"Secret: {secret_key[:10]}..." if secret_key else "Secret: Not found")
    print(f"Passphrase: {passphrase[:5]}..." if passphrase else "Passphrase: Not found")
    
    if not all([api_key, secret_key, passphrase]):
        print("❌ API 키가 설정되지 않았습니다.")
        return False
    
    try:
        # Bitget 거래소 초기화
        exchange = ccxt.bitget({
            'apiKey': api_key,
            'secret': secret_key,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # futures 거래
                'adjustForTimeDifference': True
            }
        })
        
        print("\n🔄 연결 테스트 중...")
        
        # 1. 서버 시간 확인
        try:
            server_time = exchange.fetch_time()
            print(f"✅ 서버 시간: {server_time}")
        except Exception as e:
            print(f"❌ 서버 시간 조회 실패: {e}")
            return False
        
        # 2. 잔고 조회
        try:
            balance = exchange.fetch_balance()
            print(f"✅ 잔고 조회 성공")
            
            # USDT 잔고 표시
            usdt_balance = balance.get('USDT', {})
            print(f"   💰 USDT 잔고:")
            print(f"      - 사용 가능: ${usdt_balance.get('free', 0):.2f}")
            print(f"      - 사용 중: ${usdt_balance.get('used', 0):.2f}")
            print(f"      - 총액: ${usdt_balance.get('total', 0):.2f}")
            
            return True
            
        except Exception as e:
            print(f"❌ 잔고 조회 실패: {e}")
            print(f"   에러 타입: {type(e).__name__}")
            
            # 상세 에러 분석
            if "Invalid" in str(e):
                print("   📝 API 키가 유효하지 않을 수 있습니다.")
            elif "Unauthorized" in str(e):
                print("   📝 인증 실패. API 키 권한을 확인하세요.")
            elif "IP" in str(e).upper():
                print("   📝 IP 주소 제한이 있을 수 있습니다.")
            
            return False
            
    except Exception as e:
        print(f"❌ 거래소 초기화 실패: {e}")
        return False

def test_network_connection():
    """네트워크 연결 테스트"""
    import requests
    
    print("\n=== 네트워크 연결 테스트 ===")
    
    try:
        # Bitget API 엔드포인트 테스트
        response = requests.get('https://api.bitget.com/api/spot/v1/public/time', timeout=10)
        if response.status_code == 200:
            print("✅ Bitget API 엔드포인트 접근 가능")
            return True
        else:
            print(f"❌ Bitget API 응답 코드: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 네트워크 연결 실패: {e}")
        return False

if __name__ == "__main__":
    # 네트워크 연결 테스트
    network_ok = test_network_connection()
    
    if network_ok:
        # API 연결 테스트
        api_ok = test_bitget_connection()
        
        if api_ok:
            print("\n🎉 모든 테스트 통과!")
            print("Bitget API가 정상적으로 작동하고 있습니다.")
        else:
            print("\n❌ API 연결 실패")
            print("API 키와 설정을 확인해주세요.")
    else:
        print("\n❌ 네트워크 연결 실패")
        print("인터넷 연결을 확인해주세요.")