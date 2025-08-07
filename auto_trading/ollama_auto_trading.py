import os
import json
import pyupbit
import time
import ollama
import pandas as pd
from dotenv import load_dotenv
import winsound
from plyer import notification

# 1️⃣ 환경 변수 로드
load_dotenv("C:/GPTBITCOIN/.env")

# 2️⃣ 업비트 API 연결
access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")

if not access or not secret:
    print("⚠️ API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
    exit()

upbit = pyupbit.Upbit(access, secret)
print("✅ 업비트 API 연결 완료!")

# 3️⃣ 안전한 잔고 조회 함수
def get_balance_with_exception_handling(ticker):
    try:
        balance = upbit.get_balance(ticker)
        if balance is None:
            print(f"⚠️ {ticker} 잔고 정보를 가져올 수 없습니다. API 문제 가능성 있음.")
            return 0
        return balance
    except Exception as e:
        print(f"⚠️ 잔고 조회 오류 발생: {e}")
        return 0

# 4️⃣ 지표 계산 함수
def get_data():
    df = pyupbit.get_ohlcv("KRW-BTC", count=60, interval="minute15")
    if df is None:
        print("❌ 업비트 데이터 가져오기 실패")
        return None
    
    df['middle_band'] = df['close'].rolling(window=20).mean()
    df['rsi'] = 100 - (100 / (1 + df['close'].pct_change().rolling(window=14).mean() / df['close'].pct_change().rolling(window=14).std()))
    df['william'] = (df['high'].rolling(window=14).max() - df['close']) / (df['high'].rolling(window=14).max() - df['low'].rolling(window=14).min()) * -100
    
    return df

# 5️⃣ Ollama AI를 사용한 매매 판단 함수
def ask_ollama():
    prompt = """
    너는 비트코인 트레이딩 전문가야.
    다음과 같은 형식으로만 응답해.
    {"decision": "buy" / "sell" / "hold", "reason": "설명"}
    다음은 현재 비트코인 시장 데이터야:
    """
    df = get_data()
    if df is None:
        return "hold", "데이터 없음"

    prompt += df.tail(5).to_json()

    try:
        response = ollama.chat("mistral", messages=[{"role": "user", "content": prompt}])
        response_content = response['message']['content']
        result = json.loads(response_content)

        if not isinstance(result, dict):
            return "hold", "AI 응답이 올바른 JSON 형식이 아닙니다."
        
        decision = result.get("decision", "hold")
        reason = result.get("reason", "AI 응답 오류: 이유 없음")

        if decision not in ["buy", "sell", "hold"]:
            return "hold", "AI 응답 오류: 잘못된 판단 값"

        return decision, reason

    except json.JSONDecodeError:
        return "hold", "AI 응답이 JSON 형식이 아닙니다."
    except KeyError:
        return "hold", "AI 응답 데이터에서 필요한 값이 없습니다."
    except Exception as e:
        return "hold", f"AI 요청 실패: {str(e)}"

# 6️⃣ 소리 알림 함수
def alert_sound():
    winsound.Beep(1000, 500)

# 7️⃣ 팝업 알림 함수
def send_notification(title, message):
    notification.notify(
        title=title,
        message=message,
        app_name="자동매매 프로그램",
        timeout=5
    )

# 8️⃣ 자동매매 실행
entry_price = None

def execute_trade():
    global entry_price

    while True:
        print("\n🔍 매매 조건 확인 중...")
        decision, reason = ask_ollama()
        my_krw = get_balance_with_exception_handling("KRW")
        my_btc = get_balance_with_exception_handling("KRW-BTC")
        current_price = pyupbit.get_current_price("KRW-BTC") or 0

        print(f"💰 현재 보유 KRW: {my_krw:.2f} 원")
        print(f"₿ 현재 보유 BTC: {my_btc:.6f} BTC")

        if decision == "buy" and my_krw >= 100000:
            print("🛒 100,000원 매수 실행...")
            upbit.buy_market_order("KRW-BTC", 100000)
            entry_price = current_price
            alert_sound()
            send_notification("매수 완료", f"100,000원 매수 실행됨! (가격: {entry_price})")

        if entry_price is not None:
            profit_pct = (current_price - entry_price) / entry_price * 100
            
            if profit_pct <= -5 and my_krw >= 100000:
                print("⚠️ 손실 -5% 도달! 100,000원 추가 매수 실행...")
                upbit.buy_market_order("KRW-BTC", 100000)
                alert_sound()
                send_notification("추가 매수", "손실 -5% 도달! 100,000원 추가 매수 실행됨!")
                
            if profit_pct <= -10 and my_btc > 0:
                print("⚠️ 손실 -10% 도달! 전량 매도 실행...")
                upbit.sell_market_order("KRW-BTC", my_btc)
                alert_sound()
                send_notification("손절 매도", "손실 -10% 도달! 전량 매도 완료!")

        if my_btc > 0 and decision == "sell":
            print(f"✅ AI 승인 후 매도 실행 (현재 가격: {current_price})")
            upbit.sell_market_order("KRW-BTC", my_btc)
            alert_sound()
            send_notification("매도 완료", "보유 BTC 전량 매도 완료!")

        time.sleep(60)

if __name__ == "__main__":
    print("🚀 Ollama 기반 자동매매 시작!")
    execute_trade()
