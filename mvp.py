import os
import json
import pyupbit
import requests
from dotenv import load_dotenv
from openai import OpenAI

# 1️⃣ 환경 변수 로드
load_dotenv("C:/GPTBITCOIN/.env")

# 2️⃣ 업비트 차트 데이터 가져오기 (15시간 데이터)
df = pyupbit.get_ohlcv("KRW-BTC", count=60, interval="minute15")
if df is None:
    print("❌ 업비트 데이터 가져오기 실패")
    exit()

# 3️⃣ OpenAI API를 이용한 매매 판단
client = OpenAI()
try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert in Bitcoin analysis. Respond strictly in JSON format: {\"decision\": \"buy\", \"reason\": \"some reason\"}"},
            {"role": "user", "content": df.to_json()}
        ],
        response_format={"type": "json_object"},
        timeout=10  # 10초 초과 시 오류 발생
    )
    
    response_content = response.choices[0].message.content
    if not response_content:
        raise ValueError("AI 응답이 비어 있습니다.")
    
    result = json.loads(response_content)
    
    if result["decision"] not in {"buy", "sell", "hold"}:
        raise ValueError(f"잘못된 AI 응답: {result['decision']}")

except (json.JSONDecodeError, ValueError, requests.exceptions.Timeout) as e:
    print(f"❌ AI 응답 오류: {e}")
    exit()
except Exception as e:
    print(f"❌ AI 매매 판단 요청 실패: {e}")
    exit()

# 4️⃣ 업비트 API 연결
access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")

if not access or not secret:
    print("⚠️ API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
    exit()

upbit = pyupbit.Upbit(access, secret)

# 5️⃣ 매매 실행 로직
try:
    my_krw = upbit.get_balance("KRW")
    my_btc = upbit.get_balance("KRW-BTC")
    current_price = pyupbit.get_orderbook(ticker="KRW-BTC")["orderbook_units"][0]["ask_price"]
    
    if my_krw is None or my_btc is None:
        raise ValueError("업비트 API 응답 오류: 잔고 조회 실패")
    
    if result["decision"] == "buy" and my_krw * 0.95 > 5000:
        order = upbit.buy_market_order("KRW-BTC", my_krw * 0.95)
        print("✅ 매수 주문 실행:", order)
    elif result["decision"] == "sell" and my_btc * current_price > 5000:
        order = upbit.sell_market_order("KRW-BTC", my_btc)
        print("✅ 매도 주문 실행:", order)
    else:
        print("📌 AI 판단: HOLD 유지")
        print("📌 이유:", result["reason"])
except Exception as e:
    print(f"❌ 매매 오류 발생: {e}")

