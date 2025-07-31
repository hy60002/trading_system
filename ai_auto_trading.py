import os
import time
import json
import requests
import pandas as pd
import talib
import threading
import traceback
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

# ✅ 1. 환경 변수 로드 및 기본 설정
load_dotenv()
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

LOG_FILE = "trade_log.csv"
STRATEGY_FILE = "strategy.json"
LEVERAGE = 10  # 레버리지 10배 고정

# ✅ 2. 전략 파라미터 동기화용 전역 변수 및 락
strategy = {}
strategy_lock = threading.Lock()

# 포지션 상태 관리
current_position = None  # None, "LONG", "SHORT"
entry_price = None
# 트레일링 스탑 적용을 위한 최고/최저 가격 변수
max_price_since_entry = None  # LONG 진입 후 최고가 기록
min_price_since_entry = None  # SHORT 진입 후 최저가 기록

# ✅ 3. 텔레그램 알림 함수 (콘솔 출력도 같이 진행)
def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.get(url, params=params)
    except Exception as e:
        print(f"⚠️ 텔레그램 전송 오류: {e}")
    print(message)  # 콘솔에도 출력

# ✅ 4. 레버리지 설정 함수
def set_leverage():
    try:
        client.futures_change_leverage(symbol="BTCUSDT", leverage=LEVERAGE)
        send_telegram_alert(f"✅ 레버리지를 {LEVERAGE}배로 설정 완료")
    except Exception as e:
        send_telegram_alert(f"⚠️ 레버리지 설정 오류: {e}")

# ✅ 5. 전략 파일 자동 로드 (10초마다 갱신)
def load_strategy():
    global strategy
    while True:
        try:
            with open(STRATEGY_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            with strategy_lock:
                # 키를 소문자로, 값을 float형으로 변환
                strategy = {k.lower(): float(v) for k, v in loaded.items()}
            # 전략 갱신 알림 (콘솔과 텔레그램 모두)
            send_telegram_alert("🔄 전략 파일 갱신 완료")
        except Exception as e:
            print(f"⚠️ 전략 로드 오류: {e}")
        time.sleep(600)  # 혹은 1800초로 변경 가능 (30분)

strategy_thread = threading.Thread(target=load_strategy, daemon=True)
strategy_thread.start()

# ✅ 6. 사용 가능 잔고 조회 (잔고의 90% 사용)
def get_trade_quantity():
    try:
        balance = client.futures_account_balance()
        usdt_balance = next(item for item in balance if item["asset"] == "USDT")["availableBalance"]
        trade_amount = float(usdt_balance) * 0.9
        return round(trade_amount, 2)
    except Exception as e:
        print(f"🚨 잔고 조회 오류: {e}")
        return None

# ✅ 7. 주문 실행 함수 (거래 가능 금액 부족 시 잔액까지 함께 알림)
def execute_order(symbol, side, reduce_only=False):
    quantity = get_trade_quantity()
    if quantity is None or quantity <= 0:
        try:
            balance = client.futures_account_balance()
            usdt_balance = next(item for item in balance if item["asset"] == "USDT")["availableBalance"]
        except Exception:
            usdt_balance = "확인 불가"
        message = f"⚠️ 거래 가능 금액 부족 - 주문 실행 불가\n💰 현재 잔액: {float(usdt_balance):.2f} USDT"
        send_telegram_alert(message)
        return None

    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity,
            reduceOnly=reduce_only
        )
        send_telegram_alert(f"✅ {side} 주문 실행 | 거래량: {quantity} USDT")
        return order
    except BinanceAPIException as e:
        send_telegram_alert(f"🚨 주문 실행 오류: {e}")
        return None

# ✅ 8. VWAP 계산
def calculate_vwap(df):
    return (df["close"] * df["volume"]).sum() / df["volume"].sum()

# ✅ 9. RSI 계산
def calculate_rsi(df, period=14):
    rsi_values = talib.RSI(df["close"], timeperiod=period)
    return rsi_values.dropna().iloc[-1] if not rsi_values.isna().all() else None

# ✅ 10. 변동성 필터 (ATR) 계산
def calculate_atr(df, period=14):
    df["TR"] = df[["high", "low", "close"]].diff().abs().max(axis=1)
    return df["TR"].rolling(window=period).mean().iloc[-1]

# ✅ 11. 시장 트렌드 감지 (단기/장기 이동평균 비교)
def detect_market_trend(df):
    short_avg = df["close"].rolling(window=3).mean().iloc[-1]
    long_avg = df["close"].rolling(window=12).mean().iloc[-1]
    if short_avg > long_avg:
        return "상승장"
    elif short_avg < long_avg:
        return "하락장"
    else:
        return "횡보장"

# ✅ 12. 매매 실행 (VWAP + RSI + ATR(변동성 필터) + 트레일링 스탑 + 동적 RSI 적용)
def trade_execution():
    global current_position, entry_price, max_price_since_entry, min_price_since_entry
    symbol = "BTCUSDT"
    
    while True:
        try:
            # 최신 캔들 20개 및 주문서 조회
            klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=20)
            order_book = client.get_order_book(symbol=symbol)
            
            df = pd.DataFrame(klines, columns=["timestamp", "open", "high", "low", "close", "volume"] + ["_"] * 6)
            df["close"] = df["close"].astype(float)
            df["volume"] = df["volume"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            current_price = df["close"].iloc[-1]
            
            vwap = calculate_vwap(df)
            rsi = calculate_rsi(df)
            atr = calculate_atr(df)
            trend = detect_market_trend(df)
            
            # 주문서 내 매수/매도 벽 계산
            buy_wall = sum(float(bid[1]) for bid in order_book["bids"][:10])
            sell_wall = sum(float(ask[1]) for ask in order_book["asks"][:10])
            
            with strategy_lock:
                local_strategy = strategy.copy()
            
            # 전략 파라미터 (전략파일에 정의된 값, 없으면 기본값)
            stop_loss_value = local_strategy.get("stop_loss", 0.5)       # %
            take_profit_value = local_strategy.get("take_profit", 0.75)    # %
            rsi_long = local_strategy.get("rsi_long", 30)
            rsi_short = local_strategy.get("rsi_short", 70)
            atr_min = local_strategy.get("atr_min", 10)                  # ATR 최소 임계치
            trailing_stop_percent = local_strategy.get("trailing_stop_percent", 0.5)  # %
            rsi_adjustment = local_strategy.get("rsi_adjustment", 5)       # RSI 기준 조정값

            # 시장 트렌드에 따른 동적 RSI 기준 조정
            if trend == "상승장":
                adjusted_rsi_long = rsi_long + rsi_adjustment  # 상승장에서는 매수 기준 완화
                adjusted_rsi_short = rsi_short - rsi_adjustment
            elif trend == "하락장":
                adjusted_rsi_long = rsi_long - rsi_adjustment
                adjusted_rsi_short = rsi_short + rsi_adjustment  # 하락장에서는 매도 기준 완화
            else:  # 횡보장에서는 기본값 사용
                adjusted_rsi_long = rsi_long
                adjusted_rsi_short = rsi_short

            # 신규 진입 조건 (포지션 없음)
            if current_position is None:
                # 변동성 필터: ATR이 기준 이상일 때만 진입
                if atr < atr_min:
                    send_telegram_alert(f"현재 ATR({atr:.2f})이 최소 기준({atr_min}) 미달 → 진입 조건 미충족")
                else:
                    # LONG 진입 조건
                    if current_price < vwap and (rsi is not None and rsi < adjusted_rsi_long) and (buy_wall > sell_wall * 1.5):
                        order = execute_order(symbol, "BUY")
                        if order:
                            current_position = "LONG"
                            entry_price = current_price
                            max_price_since_entry = current_price
                            send_telegram_alert(f"📈 LONG 진입 | 가격: {current_price}")
                    # SHORT 진입 조건
                    elif current_price > vwap and (rsi is not None and rsi > adjusted_rsi_short) and (sell_wall > buy_wall * 1.5):
                        order = execute_order(symbol, "SELL")
                        if order:
                            current_position = "SHORT"
                            entry_price = current_price
                            min_price_since_entry = current_price
                            send_telegram_alert(f"📉 SHORT 진입 | 가격: {current_price}")
            else:
                # 포지션이 있는 경우 (진입 후 청산 조건)
                if current_position == "LONG":
                    static_stop_loss = entry_price * (1 - stop_loss_value / 100)
                    take_profit = entry_price * (1 + take_profit_value / 100)
                    # 트레일링 스탑 업데이트 (유리한 방향으로 움직인 최고가 갱신)
                    max_price_since_entry = max(max_price_since_entry, current_price)
                    trailing_stop = max_price_since_entry * (1 - trailing_stop_percent / 100)
                    if current_price <= static_stop_loss or current_price <= trailing_stop or current_price >= take_profit:
                        order = execute_order(symbol, "SELL", reduce_only=True)
                        if order:
                            send_telegram_alert(f"🚪 LONG 포지션 청산 | 가격: {current_price}")
                            current_position = None
                            entry_price = None
                            max_price_since_entry = None
                elif current_position == "SHORT":
                    static_stop_loss = entry_price * (1 + stop_loss_value / 100)
                    take_profit = entry_price * (1 - take_profit_value / 100)
                    # 트레일링 스탑 업데이트 (유리하게 움직인 최저가 갱신)
                    min_price_since_entry = min(min_price_since_entry, current_price)
                    trailing_stop = min_price_since_entry * (1 + trailing_stop_percent / 100)
                    if current_price >= static_stop_loss or current_price >= trailing_stop or current_price <= take_profit:
                        order = execute_order(symbol, "BUY", reduce_only=True)
                        if order:
                            send_telegram_alert(f"🚪 SHORT 포지션 청산 | 가격: {current_price}")
                            current_position = None
                            entry_price = None
                            min_price_since_entry = None

            time.sleep(60)
        except Exception as e:
            send_telegram_alert(f"🚨 자동매매 중지됨: {e}")
            traceback.print_exc()
            time.sleep(60)

# ✅ 13. 5분마다 실행 상태 확인 (heartbeat)
def heartbeat_alert():
    while True:
        message = "✅ 프로그램 정상 실행 중 (5분 주기)"
        print(message)
        send_telegram_alert(message)
        time.sleep(300)  # 5분 간격

# ✅ 14. 프로그램 실행
send_telegram_alert("🚀 자동매매 프로그램 시작")
set_leverage()

# heartbeat 스레드 시작 (텔레그램과 콘솔 모두에 상태 알림)
heartbeat_thread = threading.Thread(target=heartbeat_alert, daemon=True)
heartbeat_thread.start()

trade_execution()
