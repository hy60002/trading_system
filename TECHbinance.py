import os
import time
import pandas as pd
import numpy as np
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv

# 1️⃣ 환경 변수 로드
load_dotenv("C:/GPTBITCOIN/.env")

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")

if not API_KEY or not API_SECRET:
    print("⚠️ API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
    exit()

# 2️⃣ 바이낸스 API 연결
try:
    client = Client(API_KEY, API_SECRET)
    print("✅ 바이낸스 선물 API 연결 완료!")

    # 3️⃣ 레버리지 설정 (오류 방지)
    try:
        client.futures_change_leverage(symbol="BTCUSDT", leverage=5)
        print("✅ 레버리지 5배로 설정 완료")
    except Exception as e:
        print(f"⚠️ 레버리지 설정 오류: {e}")

except Exception as e:
    print(f"⚠️ 바이낸스 API 연결 실패: {e}")
    exit()

# 4️⃣ 잔고 조회 함수
def get_balance():
    """USDT 선물 계좌 잔고를 조회하는 함수"""
    try:
        balances = client.futures_account_balance()
        for asset in balances:
            if asset["asset"] == "USDT":
                return float(asset["balance"])
        return 0.0
    except Exception as e:
        print(f"⚠️ 잔고 조회 오류: {e}")
        return 0.0

# 5️⃣ 지표 계산 함수
def get_data():
    try:
        klines = client.futures_klines(symbol="BTCUSDT", interval=Client.KLINE_INTERVAL_15MINUTE, limit=100)
        if not klines:
            print("⚠️ 바이낸스에서 데이터를 가져올 수 없습니다.")
            return None

        df = pd.DataFrame(klines, columns=["time", "open", "high", "low", "close", "volume", "close_time",
                                           "quote_asset_volume", "trades", "taker_base", "taker_quote", "ignore"])
        df["close"] = df["close"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)

        df["middle_band"] = df["close"].rolling(window=20).mean()

        # RSI 계산
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # William %R 계산
        high14 = df["high"].rolling(window=14).max()
        low14 = df["low"].rolling(window=14).min()
        df["william"] = (high14 - df["close"]) / (high14 - low14) * -100

        return df
    except Exception as e:
        print(f"⚠️ 데이터 가져오기 오류: {e}")
        return None

# 6️⃣ 안전한 매매 실행 함수
def safe_buy(amount):
    try:
        order = client.futures_create_order(
            symbol="BTCUSDT",
            side=SIDE_BUY,
            type=ORDER_TYPE_MARKET,
            quantity=amount
        )
        print(f"🛒 매수 주문 실행: {amount} BTC")
        return order
    except Exception as e:
        print(f"⚠️ 매수 주문 실패: {e}")
        return None

def safe_sell(amount):
    try:
        order = client.futures_create_order(
            symbol="BTCUSDT",
            side=SIDE_SELL,
            type=ORDER_TYPE_MARKET,
            quantity=amount,
            reduceOnly=True  # 기존 포지션만 정리
        )
        print(f"✅ 매도 주문 실행: {amount} BTC")
        return order
    except Exception as e:
        print(f"⚠️ 매도 주문 실패: {e}")
        return None

# 7️⃣ 자동매매 실행
entry_price = None
condition_met_time = None
btc_position = 0  # 보유 BTC 수량

def execute_trade():
    global entry_price, condition_met_time, btc_position

    while True:
        try:
            df = get_data()
            if df is None:
                time.sleep(60)
                continue

            balance = get_balance()
            current_price = float(client.futures_symbol_ticker(symbol="BTCUSDT")["price"])

            print("\n=======================")
            print(f"현재 가격: {current_price} USDT")
            print(f"잔고: {balance} USDT")
            print(f"BTC 포지션: {btc_position} BTC")
            print("=======================\n")

            # 매수 조건 체크
            if (
                df["close"].iloc[-1] < df["middle_band"].iloc[-1] and
                df["rsi"].iloc[-1] < 35 and
                (df["rsi"].iloc[-3] > df["rsi"].iloc[-2] > df["rsi"].iloc[-1]) and
                df["william"].iloc[-1] < -75 and
                (df["william"].iloc[-3] > df["william"].iloc[-2] < df["william"].iloc[-1]) and
                balance >= 100
            ):
                print("🛎️ 매수 조건 완성! 30분 후 & 45분 후 매수 예정")
                condition_met_time = time.time()

            # 매수 실행 (30분 후 & 45분 후)
            if condition_met_time:
                elapsed_time = time.time() - condition_met_time
                amount_to_buy = 100 / current_price  # 100 USDT 어치 매수
                if 1800 <= elapsed_time < 1810 and balance >= 100:
                    safe_buy(amount_to_buy)
                    btc_position += amount_to_buy
                    entry_price = current_price
                if 2700 <= elapsed_time < 2710 and balance >= 100:
                    safe_buy(amount_to_buy)
                    btc_position += amount_to_buy
                    condition_met_time = None  # 매수 완료 후 조건 초기화

            # 익절 및 추가 매수 조건 체크
            if entry_price is not None and btc_position > 0:
                profit_pct = ((current_price - entry_price) / entry_price) * 5 * 100  # 레버리지 5배 적용

                if profit_pct >= 25:
                    safe_sell(btc_position * 0.5)  # 50% 익절
                elif profit_pct >= 20 or profit_pct <= -10:
                    safe_sell(btc_position)  # 전량 익절
                    entry_price = None
                    btc_position = 0
                elif profit_pct <= -20 and balance >= 100:
                    safe_buy(amount_to_buy)  # 10만원 추가 매수
                    btc_position += amount_to_buy

            time.sleep(300)  # 5분 간격 실행

        except Exception as e:
            print(f"⚠️ 루프 내 오류 발생: {e}")
            time.sleep(60)

if __name__ == "__main__":
    print("🚀 바이낸스 선물 자동매매 프로그램 시작!")
    execute_trade()
