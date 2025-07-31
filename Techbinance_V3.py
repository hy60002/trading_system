import os
import time
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
import pandas as pd
import numpy as np
import logging
import json
import uuid
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import pytz
import feedparser
import asyncio
import aiohttp

# ==============================
# 전역 상수 및 설정 (Configuration & Constants)
# ==============================
CHECK_INTERVAL = 60          # 메인 루프 체크 간격 (초)
ORDER_POLLING_MAX_ATTEMPTS = 20
ORDER_POLLING_SLEEP = 0.5    # 주문 체결 확인 시 sleep 시간 (초)
TELEGRAM_RATE_LIMIT_MAX = 20
TELEGRAM_RATE_LIMIT_INTERVAL = 60  # 1분당 최대 메시지 수
RETRY_DELAY_ORDER = 2        # 주문 재시도 대기 시간 (초)
RETRY_COUNT_GPT = 3          # GPT 보고서 재시도 횟수

# ==============================
# 전역 로깅 설정
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("binance_bot")

# ==============================
# AsyncWorker: 단일 이벤트 루프 관리 (비동기 I/O 개선)
# ==============================
class AsyncWorker:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._start_loop, daemon=True)
        self.thread.start()
    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

# 전역 AsyncWorker 인스턴스 생성
async_worker = AsyncWorker()

# ==============================
# 거래 봇 클래스 (Trading Bot)
# ==============================
class BinanceFuturesBot:
    def __init__(self, env_path: str, symbol: str = "BTCUSDT", leverage: int = 10):
        self.symbol = symbol
        self.leverage = leverage
        self.active_trades = []   # 개별 거래 건별 익절/손절 추적
        # 기준봉 탐색 관련 변수
        self.buy_signal = None           # 기준봉 감지 시 기준 윌리엄 %R 값 저장
        self.last_baseline_candle_time = None  # 마지막 기준봉으로 사용한 캔들 종료 시각
        self.last_warning_candle_time = None  # 동일 캔들에 대해 경고를 한 번만 출력하기 위한 변수

        # 기존 변수들
        self.buy_setup_triggered = False
        self.baseline_william = None
        self.last_gpt_report_time = 0
        self.gpt_report_interval = 14400  # 4시간(초 단위)
        self.last_status_update_time = 0
        self.status_update_interval = 900  # 15분(초 단위)
        self.running = False
        self.last_df = None
        self.last_price = None
        self.telegram_rate_limit = {"count": 0, "reset_time": time.time() + TELEGRAM_RATE_LIMIT_INTERVAL}
        self.telegram_max_rate = TELEGRAM_RATE_LIMIT_MAX
        self.trade_lock = threading.Lock()  # 거래 관련 동기화 락
        self.data_lock = threading.Lock()   # 데이터 관련 동기화 락

        # 리스크 관리 파라미터
        self.max_daily_loss_pct = 20.0  # 일일 최대 손실 허용 비율(%)
        self.stop_loss_pct = 100.0      # 현재는 미사용
        self.max_position_usdt = 1000000  # 최대 포지션 크기(USDT)
        self.daily_stats = {
            "start_balance": 0.0,
            "current_balance": 0.0,
            "trades_today": 0,
            "profit_today": 0.0,
            "date": datetime.now(pytz.timezone('Asia/Seoul')).strftime("%Y-%m-%d")
        }
        # 매매 목표 수익률 (GUI에서 설정)
        self.first_target_profit_pct = 11.0
        self.second_target_profit_pct = 22.0
        # 거래 히스토리 저장
        self.trade_history = []
        # 한국 시간대 설정
        self.KST = pytz.timezone('Asia/Seoul')

        # API 및 환경 설정 로드
        self._load_env(env_path)
        self._init_client()
        # 기존 거래 내역 및 히스토리 로드
        self._load_trades()
        self._load_trade_history()
        # 일일 통계 초기화
        self._init_daily_stats()

        self.log("✅ 프로그램 초기화 완료. 최초 GPT 보고서 요청 중...")
        self.generate_gpt_report_with_retry()

        # 기준봉 탐색 모듈 시작 (별도 스레드)
        threading.Thread(target=self.baseline_detection_loop, daemon=True).start()

    # ------------------------------
    # 유틸리티 및 로그 관련 함수
    # ------------------------------
    def log(self, message: str):
        logger.info(message)
        print(message)
        self._rate_limited_telegram(message)
        if hasattr(self, 'telegram_callback') and callable(self.telegram_callback):
            self.telegram_callback(f"[로그] {message}")

    def gui_is_alive(self):
        try:
            if hasattr(self.telegram_callback, '__self__'):
                widget = self.telegram_callback.__self__
                if hasattr(widget, 'winfo_exists'):
                    return widget.winfo_exists()
            return True
        except Exception:
            return True

    def _rate_limited_telegram(self, message: str):
        if not (self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID):
            return
        current_time = time.time()
        if current_time > self.telegram_rate_limit["reset_time"]:
            self.telegram_rate_limit = {"count": 0, "reset_time": current_time + TELEGRAM_RATE_LIMIT_INTERVAL}
        if self.telegram_rate_limit["count"] >= self.telegram_max_rate:
            logger.warning("텔레그램 메시지 속도 제한 도달, 메시지 전송 건너뜀")
            return
        self.telegram_rate_limit["count"] += 1
        async_worker.run(self.async_send_telegram_message(message))

    async def async_send_telegram_message(self, message: str, retry: int = 3):
        if not (self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID):
            return
        url = f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": self.TELEGRAM_CHAT_ID, "text": message}
        for attempt in range(retry):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.post(url, data=data) as response:
                        if response.status != 200:
                            text = await response.text()
                            raise Exception(f"Telegram API 응답 코드: {response.status}, 내용: {text}")
                        return
            except Exception as e:
                logger.error(f"Telegram 전송 오류 (시도 {attempt+1}/{retry}): {e}")
                if attempt < retry - 1:
                    await asyncio.sleep(2)

    # ------------------------------
    # 환경 및 API 초기화
    # ------------------------------
    def _load_env(self, env_path: str):
        if not os.path.exists(env_path):
            self.log(f"⚠️ 환경 설정 파일을 찾을 수 없습니다: {env_path}")
            raise FileNotFoundError(f"환경 설정 파일을 찾을 수 없습니다: {env_path}")
        load_dotenv(env_path)
        self.API_KEY = os.getenv("BINANCE_API_KEY")
        self.API_SECRET = os.getenv("BINANCE_SECRET_KEY")
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        self.GPT_API_URL = os.getenv("GPT_API_URL")
        self.GPT_API_KEY = os.getenv("GPT_API_KEY")
        self.ALLOWED_IP = os.getenv("ALLOWED_IP", "")
        if not self.API_KEY or not self.API_SECRET:
            self.log("⚠️ API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
            raise ValueError("API 키가 설정되지 않았습니다.")
        if not self.GPT_API_URL or not self.GPT_API_KEY:
            self.log("⚠️ GPT API 설정이 누락되었습니다. GPT 보고서 기능이 제한될 수 있습니다.")

    def _init_client(self):
        try:
            self.client = Client(self.API_KEY, self.API_SECRET)
            account_status = self.client.get_account_status()
            if account_status.get('data') != 'Normal':
                self.log(f"⚠️ 계정 상태가 정상이 아닙니다: {account_status}")
            self.client.ping()
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            try:
                self.client.futures_change_margin_type(symbol=self.symbol, marginType='CROSSED')
            except BinanceAPIException as e:
                if e.code == -4046:
                    self.log("⚠️ 마진 타입이 이미 CROSSED로 설정되어 있습니다.")
                else:
                    raise
            self.log(f"✅ 바이낸스 선물 API 연결 및 레버리지 {self.leverage}배 설정 완료")
        except BinanceAPIException as e:
            self.log(f"⚠️ Binance API 오류: {e}")
            raise
        except BinanceRequestException as e:
            self.log(f"⚠️ Binance 요청 오류: {e}")
            raise
        except Exception as e:
            self.log(f"⚠️ Binance API 연결/레버리지 설정 실패: {e}")
            raise

    # ------------------------------
    # 거래 내역 및 통계 관련 함수
    # ------------------------------
    def _load_trades(self):
        try:
            if os.path.exists("active_trades.json"):
                with open("active_trades.json", "r") as f:
                    self.active_trades = json.load(f)
                self.log(f"✅ 기존 거래 내역 로드 완료: {len(self.active_trades)}개")
        except Exception as e:
            self.log(f"⚠️ 거래 내역 로드 실패: {e}")
            self.active_trades = []

    def _load_trade_history(self):
        try:
            if os.path.exists("trade_history.json"):
                with open("trade_history.json", "r") as f:
                    self.trade_history = json.load(f)
                self.log(f"✅ 기존 거래 히스토리 로드 완료: {len(self.trade_history)}개")
        except Exception as e:
            self.log(f"⚠️ 거래 히스토리 로드 실패: {e}")
            self.trade_history = []

    def _save_trades(self):
        try:
            with self.trade_lock:
                with open("active_trades.json", "w") as f:
                    json.dump(self.active_trades, f)
        except Exception as e:
            self.log(f"⚠️ 거래 내역 저장 실패: {e}")

    def _save_trade_history(self):
        try:
            with open("trade_history.json", "w") as f:
                json.dump(self.trade_history, f)
        except Exception as e:
            self.log(f"⚠️ 거래 히스토리 저장 실패: {e}")

    def _init_daily_stats(self):
        today = datetime.now(self.KST).strftime("%Y-%m-%d")
        if self.daily_stats["date"] != today:
            balance = self.get_balance()
            self.daily_stats = {
                "start_balance": balance,
                "current_balance": balance,
                "trades_today": 0,
                "profit_today": 0.0,
                "date": today
            }
            self.log(f"✅ 일일 통계 초기화 완료: {today} 잔고 {balance} USDT")

    def _update_daily_stats(self, profit=0.0):
        balance = self.get_balance()
        self.daily_stats["current_balance"] = balance
        self.daily_stats["trades_today"] += 1
        self.daily_stats["profit_today"] += profit
        if self.daily_stats["profit_today"] < 0:
            loss_pct = abs(self.daily_stats["profit_today"]) / self.daily_stats["start_balance"] * 100
            if loss_pct >= self.max_daily_loss_pct:
                self.log(f"⚠️ 일일 최대 손실 한도 도달: {loss_pct:.2f}%. 자동매매를 중지합니다.")
                self.running = False
                return False
        return True

    def get_balance(self) -> float:
        try:
            balances = self.client.futures_account_balance()
            for asset in balances:
                if asset["asset"] == "USDT":
                    return float(asset["balance"])
            return 0.0
        except BinanceAPIException as e:
            self.log(f"⚠️ Binance API 오류 (잔고 조회): {e}")
            return 0.0
        except Exception as e:
            self.log(f"⚠️ 잔고 조회 오류: {e}")
            return 0.0

    # ------------------------------
    # 데이터 수집 및 지표 계산
    # ------------------------------
    def get_data(self):
        try:
            with self.data_lock:
                klines = self.client.futures_klines(
                    symbol=self.symbol,
                    interval=Client.KLINE_INTERVAL_15MINUTE,
                    limit=200
                )
                if not klines or len(klines) < 14:
                    self.log("⚠️ 충분한 데이터가 없습니다. 최소 14개 캔들이 필요합니다.")
                    return None

                df = pd.DataFrame(klines, columns=[
                    "time", "open", "high", "low", "close", "volume",
                    "close_time", "quote_asset_volume", "trades",
                    "taker_base", "taker_quote", "ignore"
                ])
                df["time"] = pd.to_datetime(df["time"], unit='ms', utc=True).dt.tz_convert(self.KST)
                df["close_time"] = pd.to_datetime(df["close_time"], unit='ms', utc=True).dt.tz_convert(self.KST)
                df["open"] = df["open"].astype(float)
                df["close"] = df["close"].astype(float)
                df["high"] = df["high"].astype(float)
                df["low"] = df["low"].astype(float)
                df["volume"] = df["volume"].astype(float)

                latest_candle_time = df["close_time"].iloc[-1]
                current_time = datetime.now(self.KST)
                buffer_seconds = 60  # 캔들 마감 후 최소 60초 대기
                if (current_time - latest_candle_time).total_seconds() < buffer_seconds:
                    if self.last_warning_candle_time != latest_candle_time:
                        self.log(f"⚠️ 최신 캔들이 아직 완성되지 않았습니다. 현재: {current_time.strftime('%Y-%m-%d %H:%M:%S')}, 캔들 종료: {latest_candle_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        self.last_warning_candle_time = latest_candle_time
                    if len(df) >= 4:
                        df = df.iloc[:-1]
                    else:
                        self.log("⚠️ 충분한 완성된 캔들 데이터가 없습니다.")
                        return None
                else:
                    self.last_warning_candle_time = None

                # RSI 계산 (Wilder's smoothing 방식 적용)
                delta = df["close"].diff()
                gain = delta.clip(lower=0)
                loss = -delta.clip(upper=0)
                window = 14
                avg_gain = gain.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
                rs = avg_gain / avg_loss.replace(0, np.nan)
                df["rsi"] = 100 - (100 / (1 + rs))
                df["rsi"] = df["rsi"].fillna(100)

                # 윌리엄 %R 계산
                high14 = df["high"].rolling(window=14).max()
                low14 = df["low"].rolling(window=14).min()
                range_val = high14 - low14
                df["william"] = np.where(range_val == 0, 0, (high14 - df["close"]) / range_val * -100)

                # 이동평균 및 볼린저 밴드 계산
                df["ma20"] = df["close"].rolling(window=20).mean()
                df["ma50"] = df["close"].rolling(window=50).mean()
                df["ma20_std"] = df["close"].rolling(window=20).std()
                df["upper_band"] = df["ma20"] + (df["ma20_std"] * 2)
                df["lower_band"] = df["ma20"] - (df["ma20_std"] * 2)

                # MACD 계산
                df["ema12"] = df["close"].ewm(span=12).mean()
                df["ema26"] = df["close"].ewm(span=26).mean()
                df["macd"] = df["ema12"] - df["ema26"]
                df["signal"] = df["macd"].ewm(span=9).mean()
                df["macd_histogram"] = df["macd"] - df["signal"]

                return df
        except BinanceAPIException as e:
            self.log(f"⚠️ Binance API 오류 (get_data): {e}")
            return None
        except Exception as e:
            self.log(f"⚠️ 데이터 가져오기 오류: {e}")
            return None

    def calculate_order_quantity(self, current_price: float, amount_usdt: float) -> float:
        try:
            exchange_info = self.client.futures_exchange_info()
            symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == self.symbol), None)
            if not symbol_info:
                self.log(f"⚠️ 심볼 정보를 찾을 수 없음: {self.symbol}")
                return 0
            quantity_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            if not quantity_filter:
                self.log(f"⚠️ LOT_SIZE 필터를 찾을 수 없음: {self.symbol}")
                return 0

            min_qty = float(quantity_filter['minQty'])
            max_qty = float(quantity_filter['maxQty'])
            step_size = float(quantity_filter['stepSize'])

            raw_quantity = amount_usdt / current_price
            decimal_places = self._get_decimal_places(step_size)
            quantity = round(raw_quantity - (raw_quantity % step_size), decimal_places)

            if quantity < min_qty:
                self.log(f"⚠️ 계산된 수량이 최소 수량보다 작음: {quantity} < {min_qty}")
                return 0
            if quantity > max_qty:
                quantity = max_qty
                self.log(f"⚠️ 계산된 수량이 최대 수량보다 큼. 최대 수량으로 제한: {max_qty}")
            return quantity
        except Exception as e:
            self.log(f"⚠️ 주문 수량 계산 오류: {e}")
            return 0

    def _get_decimal_places(self, step_size: float) -> int:
        step_str = "{:g}".format(step_size)
        if '.' in step_str:
            return len(step_str.split('.')[1])
        return 0

    # ------------------------------
    # 매수/매도 주문 및 거래 실행
    # ------------------------------
    def safe_buy(self, amount_usdt: float):
        try:
            ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
            current_price = float(ticker["price"])
            quantity = self.calculate_order_quantity(current_price, amount_usdt)
            if quantity <= 0:
                self.log("⚠️ 계산된 매수 수량이 0보다 작거나 같음. 매수 취소.")
                return None

            self.log(f"🛒 매수 주문 시도: {quantity} BTC (약 {amount_usdt} USDT)")
            with self.trade_lock:
                order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_MARKET,
                    quantity=quantity,
                    positionSide="LONG"
                )
            order_id = order.get('orderId')
            if not order_id:
                self.log("⚠️ 주문 ID를 받지 못함. 주문 상태를 확인할 수 없음.")
                return None

            for i in range(ORDER_POLLING_MAX_ATTEMPTS):
                order_status = self.client.futures_get_order(symbol=self.symbol, orderId=order_id)
                status = order_status.get('status')
                if status == ORDER_STATUS_FILLED:
                    avg_price = float(order_status.get('avgPrice', current_price))
                    executed_qty = float(order_status.get('executedQty', quantity))
                    self.log(f"✅ 매수 주문 체결: {executed_qty} BTC at {avg_price} USDT")
                    return {
                        "order_id": order_id,
                        "price": avg_price,
                        "quantity": executed_qty,
                        "side": "BUY",
                        "time": datetime.now(self.KST).strftime("%Y-%m-%d %H:%M:%S")
                    }
                elif status == "PARTIALLY_FILLED":
                    executed_qty = float(order_status.get('executedQty', 0))
                    if executed_qty >= 0.8 * quantity:
                        self.log("⚠️ 주문이 부분 체결되었으나 충분한 비율로 매수로 간주")
                        avg_price = float(order_status.get('avgPrice', current_price))
                        return {
                            "order_id": order_id,
                            "price": avg_price,
                            "quantity": executed_qty,
                            "side": "BUY",
                            "time": datetime.now(self.KST).strftime("%Y-%m-%d %H:%M:%S")
                        }
                time.sleep(ORDER_POLLING_SLEEP)
            self.log(f"⚠️ 주문 체결 확인 시간 초과. 주문 ID: {order_id}")
            return None
        except BinanceAPIException as e:
            self.log(f"⚠️ Binance API 오류 (매수): {e}")
            return None
        except Exception as e:
            self.log(f"⚠️ 매수 주문 실패: {e}")
            return None

    def safe_sell(self, sell_quantity: float):
        try:
            self.log(f"🛒 매도 주문 시도: {sell_quantity} BTC")
            with self.trade_lock:
                order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_MARKET,
                    quantity=sell_quantity,
                    reduceOnly=True,
                    positionSide="LONG"
                )
            order_id = order.get('orderId')
            if not order_id:
                self.log("⚠️ 주문 ID를 받지 못함. 주문 상태를 확인할 수 없음.")
                return None

            for i in range(ORDER_POLLING_MAX_ATTEMPTS):
                order_status = self.client.futures_get_order(symbol=self.symbol, orderId=order_id)
                status = order_status.get('status')
                if status == ORDER_STATUS_FILLED:
                    avg_price = float(order_status.get('avgPrice', self.last_price))
                    executed_qty = float(order_status.get('executedQty', sell_quantity))
                    self.log(f"✅ 매도 주문 체결: {executed_qty} BTC at {avg_price} USDT")
                    return {
                        "order_id": order_id,
                        "price": avg_price,
                        "quantity": executed_qty,
                        "side": "SELL",
                        "time": datetime.now(self.KST).strftime("%Y-%m-%d %H:%M:%S")
                    }
                elif status == "PARTIALLY_FILLED":
                    executed_qty = float(order_status.get('executedQty', 0))
                    if executed_qty >= 0.8 * sell_quantity:
                        self.log("⚠️ 주문이 부분 체결되었으나 충분한 비율로 매도로 간주")
                        avg_price = float(order_status.get('avgPrice', self.last_price))
                        return {
                            "order_id": order_id,
                            "price": avg_price,
                            "quantity": executed_qty,
                            "side": "SELL",
                            "time": datetime.now(self.KST).strftime("%Y-%m-%d %H:%M:%S")
                        }
                time.sleep(ORDER_POLLING_SLEEP)
            self.log(f"⚠️ 주문 체결 확인 시간 초과. 주문 ID: {order_id}")
            return None
        except BinanceAPIException as e:
            self.log(f"⚠️ Binance API 오류 (매도): {e}")
            return None
        except Exception as e:
            self.log(f"⚠️ 매도 주문 실패: {e}")
            return None

    # ------------------------------
    # 기준봉 탐색 모듈 (별도 스레드에서 실행)
    # ------------------------------
    def baseline_detection_loop(self):
        """
        새로운 15분봉 데이터가 완성되었을 때, check_conditions()를 통해
        기준봉(매수 신호)을 탐색합니다.
        [수정사항]
          - 최신 캔들이 완성되지 않은 경우, 이미 출력한 경고는 중복 출력하지 않습니다.
          - 그리고 새로운 완성 캔들이 없더라도, 마지막 완성된 캔들에 대해 조건이 충족되었고 buy_signal이 아직 없으면
            재검증하여 기준봉을 확정하도록 합니다.
        """
        while self.running:
            df = self.get_data()  # 완성된 캔들 데이터 반환 (없으면 None)
            if df is not None and len(df) >= 3:
                # 최신 캔들의 종료 시각(완성된 캔들 중 마지막)을 기준으로 함
                latest_candle_time = df["close_time"].iloc[-1]
                # 만약 새로운 캔들이 도착했거나, 아직 기준봉이 확정되지 않은 상태라면 조건 재검증
                if (self.last_baseline_candle_time is None or 
                    latest_candle_time > self.last_baseline_candle_time or 
                    self.buy_signal is None):
                    should_buy, baseline = self.check_conditions(df)
                    if should_buy:
                        self.buy_signal = baseline
                        self.last_baseline_candle_time = latest_candle_time
                        self.log(f"⚡ 매수 조건 감지! 기준선: {baseline:.2f} (캔들 종료: {latest_candle_time.strftime('%Y-%m-%d %H:%M:%S')})")
            time.sleep(CHECK_INTERVAL)

    # ------------------------------
    # 자동 매매 실행 및 상태 업데이트, 주문 실행 모듈
    # ------------------------------
    def execute_trade(self):
        """
        - 상태 업데이트, 포지션 관리, GPT 보고서 갱신 등은 계속 진행합니다.
        - baseline_detection_loop에서 설정된 self.buy_signal가 있으면,
          최신 완성 캔들 데이터(df)를 기반으로 재검증 후 매수 주문(safe_buy)을 실행합니다.
        """
        self.running = True
        self._init_daily_stats()
        self.log(f"✅ 자동매매 시작: 심볼={self.symbol}, 레버리지={self.leverage}배")
        self.log(f"📊 리스크 관리: 일일 최대 손실={self.max_daily_loss_pct}%, 최대 포지션={self.max_position_usdt} USDT")
        last_check_time = 0

        while self.running:
            try:
                current_time = time.time()
                if current_time - last_check_time < CHECK_INTERVAL:
                    time.sleep(1)
                    continue
                last_check_time = current_time

                today = datetime.now(self.KST).strftime("%Y-%m-%d")
                if self.daily_stats["date"] != today:
                    self._init_daily_stats()

                df = self.get_data()
                if df is None or len(df) < 14:
                    self.log("⚠️ 충분한 시장 데이터를 가져오지 못했습니다. 3분 후 재시도합니다.")
                    time.sleep(60)
                    continue

                ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
                self.last_price = float(ticker["price"])
                self.last_df = df

                self.manage_active_trades()

                if self.buy_signal is not None:
                    current_william = df["william"].iloc[-1]
                    if current_william <= self.buy_signal or current_william <= -90:
                        balance = self.get_balance()
                        buy_amount = balance * 0.25 * self.leverage
                        if buy_amount < 10:
                            self.log(f"⚠️ 매수 금액이 너무 작습니다: {buy_amount:.2f} USDT")
                        else:
                            buy_order = self.safe_buy(buy_amount)
                            if buy_order:
                                trade_info = {
                                    "id": str(uuid.uuid4()),
                                    "entry_price": buy_order["price"],
                                    "entry_quantity": buy_order["quantity"],
                                    "remaining_quantity": buy_order["quantity"],
                                    "entry_time": buy_order["time"],
                                    "entry_order_id": buy_order["order_id"],
                                    "sell_stage": 0,
                                    "status": "ACTIVE"
                                }
                                with self.trade_lock:
                                    self.active_trades.append(trade_info)
                                    self._save_trades()
                                self.log(f"✅ 새로운 매수 포지션 생성: {buy_order['quantity']} BTC at {buy_order['price']} USDT")
                                self.buy_signal = None
                if time.time() - self.last_status_update_time > self.status_update_interval:
                    self.update_status()
                    self.last_status_update_time = time.time()
                if time.time() - self.last_gpt_report_time > self.gpt_report_interval:
                    self.generate_gpt_report_with_retry()
                    self.last_gpt_report_time = time.time()

            except BinanceAPIException as e:
                self.log(f"⚠️ Binance API 오류: {e}")
                time.sleep(30)
            except Exception as e:
                self.log(f"⚠️ 거래 실행 중 오류 발생: {e}")
                time.sleep(30)

        self.log("❌ 자동매매 종료됨")

    def check_conditions(self, df):
        """
        최근 3개 15분봉에 대해:
         - 마지막 봉의 RSI가 35 이하 및 윌리엄 %R이 -70 이하
         - 3봉에 걸쳐 RSI가 연속 하락 (rsi_2 > rsi_1 > rsi_0)
         - 윌리엄 %R은 직전 봉에서 저점을 찍고, 마지막 봉에서 반등 (will_2 > will_1 and will_1 < will_0)
        조건이 충족되면 True와 기준값(will_1)을 반환합니다.
        """
        if len(df) < 3:
            return False, None
        rsi_2 = df["rsi"].iloc[-3]
        rsi_1 = df["rsi"].iloc[-2]
        rsi_0 = df["rsi"].iloc[-1]
        will_2 = df["william"].iloc[-3]
        will_1 = df["william"].iloc[-2]
        will_0 = df["william"].iloc[-1]

        if not (rsi_0 <= 35 and will_0 <= -70):
            return False, None
        if not (rsi_2 > rsi_1 > rsi_0):
            return False, None
        if not (will_2 > will_1 and will_1 < will_0):
            return False, None
        return True, will_1

    def manage_active_trades(self):
        if not self.active_trades:
            return
        with self.trade_lock:
            updated_trades = []
            for trade in self.active_trades:
                if trade["status"] != "ACTIVE":
                    updated_trades.append(trade)
                    continue
                entry_price = trade["entry_price"]
                current_price = self.last_price
                profit_pct = (current_price - entry_price) / entry_price * 100 * self.leverage
                first_target = 1 + (self.first_target_profit_pct / 100)
                second_target = 1 + (self.second_target_profit_pct / 100)
                if trade.get("sell_stage", 0) == 0 and current_price >= entry_price * first_target:
                    sell_qty = trade["remaining_quantity"] / 2
                    sell_order = self.safe_sell(sell_qty)
                    if sell_order:
                        trade["first_sell"] = sell_order
                        trade["sell_stage"] = 1
                        trade["remaining_quantity"] -= sell_qty
                        self.log(f"💰 {self.first_target_profit_pct}% 목표 달성: 절반 매도, 남은 수량: {trade['remaining_quantity']} BTC")
                elif trade.get("sell_stage", 0) == 1 and current_price >= entry_price * second_target:
                    sell_qty = trade["remaining_quantity"]
                    sell_order = self.safe_sell(sell_qty)
                    if sell_order:
                        trade["second_sell"] = sell_order
                        trade["sell_stage"] = 2
                        trade["exit_price"] = sell_order["price"]
                        trade["exit_time"] = sell_order["time"]
                        trade["status"] = "CLOSED"
                        trade["profit_pct"] = (sell_order["price"] - entry_price) / entry_price * 100 * self.leverage
                        trade["profit_usdt"] = (sell_order["price"] - entry_price) * trade["entry_quantity"]
                        self.log(f"💰 {self.second_target_profit_pct}% 목표 달성: 남은 수량 매도, 거래 종료")
                        self.trade_history.append(trade)
                        self._save_trade_history()
                        self._update_daily_stats(trade["profit_usdt"])
                updated_trades.append(trade)
            self.active_trades = updated_trades
            self._save_trades()

    # ------------------------------
    # GPT 보고서 생성 (비동기 I/O 개선)
    # ------------------------------
    def generate_gpt_report_with_retry(self, max_retries=RETRY_COUNT_GPT):
        for attempt in range(max_retries):
            try:
                report = self.generate_gpt_report()
                if report:
                    return report
            except Exception as e:
                self.log(f"⚠️ GPT 보고서 생성 실패 (시도 {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)
        self.log("❌ GPT 보고서 생성 실패: 최대 재시도 횟수 초과")
        return None

    def generate_gpt_report(self):
        df = self.last_df
        if df is None or len(df) < 14:
            self.log("거래 데이터가 부족합니다. 기본 보고서를 생성합니다.")
            basic_news = self.get_market_news()
            basic_strategy = "기본 전략: 시장 상황에 따라 포지션을 점진적으로 축소합니다."
            now = datetime.now(self.KST).strftime('%Y-%m-%d %H:%M:%S')
            report = (
                f"🧠 GPT 기본 시장 분석 보고서 ({now})\n"
                "---------------------------------------------------\n"
                "거래 데이터가 부족합니다.\n\n"
                f"시장 뉴스:\n{basic_news}\n\n{basic_strategy}\n"
                "---------------------------------------------------"
            )
            self.log(report)
            return report

        try:
            recent_candles = df.iloc[-5:][["time", "open", "high", "low", "close", "volume", "rsi", "william"]].to_dict('records')
            for candle in recent_candles:
                if isinstance(candle["time"], pd.Timestamp):
                    candle["time"] = candle["time"].isoformat()
            indicators = {
                "rsi": df["rsi"].iloc[-1],
                "william": df["william"].iloc[-1],
                "macd": df["macd"].iloc[-1],
                "signal": df["signal"].iloc[-1],
                "macd_histogram": df["macd_histogram"].iloc[-1],
                "ma20": df["ma20"].iloc[-1],
                "ma50": df["ma50"].iloc[-1],
                "upper_band": df["upper_band"].iloc[-1],
                "lower_band": df["lower_band"].iloc[-1],
                "current_price": self.last_price
            }
            candle_info = ""
            if self.last_df is not None and len(self.last_df) >= 3:
                last_three = self.last_df.tail(3)
                candle_info += "🔍 최근 3개 15분봉 지표:\n"
                for idx, row in last_three.iterrows():
                    try:
                        candle_time = row['time'].astimezone(self.KST).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        candle_time = row['time'].strftime('%Y-%m-%d %H:%M:%S')
                    candle_info += (f"  - {candle_time}: RSI {row['rsi']:.2f}, 윌리엄 %R {row['william']:.2f}\n")
            active_trades_count = len([t for t in self.active_trades if t["status"] == "ACTIVE"])
            market_news = self.get_market_news()
            trade_summary = self.analyze_trade_data()
            trade_history_detail = ""
            for trade in self.trade_history:
                trade_history_detail += (
                    f"\n거래 ID: {trade['id']}\n"
                    f"매수 가격: {trade['entry_price']:.2f} USDT\n"
                    f"매도 가격: {trade.get('exit_price', 0):.2f} USDT\n"
                    f"수량: {trade['entry_quantity']:.4f} BTC\n"
                    f"수익률: {trade['profit_pct']:.2f}%\n"
                    f"수익금: {trade['profit_usdt']:.2f} USDT\n"
                    f"거래 시간: {trade['entry_time']} ~ {trade.get('exit_time', '')}\n"
                )
            account = self.client.futures_account()
            positions = account["positions"]
            btc_position = next((pos for pos in positions if pos["symbol"] == self.symbol), None)
            positions_info = ""
            if btc_position:
                position_size = float(btc_position["positionAmt"])
                entry_price = float(btc_position["entryPrice"])
                positions_info = (
                    f"\n현재 포지션:\n"
                    f"포지션 수량: {position_size} BTC\n"
                    f"진입가: {entry_price} USDT\n"
                )
            request_data = {
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "대답은 한글로 반드시 하세요. You are a trading assistant. "
                            "Provide detailed analysis and insights based on the following data. "
                            "Do NOT suggest automatic changes to the trading strategy; just provide advice."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"\n+아래 데이터를 기반으로, 트레이딩 전략을 평가하고 개선점을 제안하는 트레이딩 분석가 역할을 수행합니다. "
                            f"매매 전략을 자동으로 변경하지 말고, 조언과 제안을 제공합니다.\n"
                            f"\n+현재 매매 전략:\n"
                            f"+1. RSI와 윌리엄 %R을 사용하여 매수 신호를 확인합니다.\n"
                            f"+2. RSI가 35 이하, 윌리엄 %R이 -70 이하일 때 매수 가능성이 있습니다.\n"
                            f"+3. RSI는 3개의 캔들을 비교하여 감소하는 패턴을 찾습니다.\n"
                            f"+4. 윌리엄 %R은 2개의 캔들을 비교하여 특정 패턴을 찾습니다.\n"
                            f"+5. 위 조건이 충족되고, 윌리엄%R이 이전에 설정된 기준선을 돌파하거나 -90 이하로 떨어지면 매수를 진행합니다.\n"
                            f"+6. 잔고의 25%에 레버리지를 곱하여 매수 금액을 결정합니다.\n"
                            f"+7. 목표 수익률에 따라 매도를 분할하여 진행합니다.\n"
                            f"+8. 일일 최대 손실률은 {self.max_daily_loss_pct}%입니다.\n"
                            f"+9. 첫번째 목표수익률은 {self.first_target_profit_pct}%이고, 두번째 목표수익률은 {self.second_target_profit_pct}%입니다.\n"
                            f"\nHere is the latest market data:\n"
                            f"\n📊 Recent 2-hour Trade Summary:\n{trade_summary}\n"
                            f"\n🔹 Recent Candles:\n{recent_candles}\n"
                            f"\n🔹 Key Indicators:\n{indicators}\n"
                            f"\n🔹 Active Trades Count: {active_trades_count}\n"
                            f"🔹 Market News: {market_news}\n"
                            f"\n📉 상세 거래 내역:\n{trade_history_detail}\n"
                            f"{positions_info}\n"
                            f"\n👉 **거래 내역이 없을 경우**:\n"
                            f"- 현재 시장 뉴스와 시장 흐름을 상세히 검색하고 분석하여 상세 보고서를 제공하십시오.\n"
                            f"- 주요 지표를 바탕으로 시장 전망을 근거와 예시, 뉴스 등을 상세 분석하여 평가하십시오.\n"
                            f"\n👉 **거래 내역이 있을 경우**:\n"
                            f"- 각 거래를 평가하고 시장 흐름과 비교하여 분석을 제공하십시오.\n"
                            f"- 향후 시장 흐름에 대한 예측을 제시하십시오.\n"
                            f"- 현재 전략에 대한 개선 제안을 제시하십시요.\n"
                        )
                    }
                ],
                "temperature": 0.7
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.GPT_API_KEY}"
            }
            self.log("🧠 GPT 분석 요청 중...")
            report = async_worker.run(self._async_generate_gpt_report(request_data, headers))
            if report:
                final_report = (
                    f"🧠 GPT 시장 분석 보고서 ({datetime.now(self.KST).strftime('%Y-%m-%d %H:%M:%S')})\n"
                    "---------------------------------------------------\n"
                    f"{report}\n"
                    "---------------------------------------------------"
                )
                self.log(final_report)
                return final_report
            else:
                self.log("⚠️ GPT 분석 결과를 받지 못했습니다.")
                return None
        except Exception as e:
            self.log(f"⚠️ GPT 보고서 생성 중 오류 발생: {e}")
            return None

    async def _async_generate_gpt_report(self, request_data: dict, headers: dict):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(self.GPT_API_URL, headers=headers, data=json.dumps(request_data)) as response:
                    if response.status == 200:
                        result = await response.json()
                        analysis = result.get("choices", [{}])[0].get("message", {}).get("content", "분석 결과를 받지 못했습니다.")
                        return analysis
                    elif response.status == 403:
                        self.log("⚠️ GPT API 403 오류: 권한이 없거나 API 키가 올바르지 않습니다.")
                        return None
                    else:
                        text = await response.text()
                        self.log(f"⚠️ GPT API 오류: HTTP {response.status}, {text}")
                        return None
        except Exception as e:
            self.log(f"⚠️ GPT API 요청 중 오류 발생: {e}")
            return None

    def get_market_news(self):
        try:
            feed_url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                self.log(f"⚠️ RSS 피드 파싱 오류: {feed.bozo_exception}")
                return "시장 뉴스 데이터를 가져오는 데 실패했습니다. (RSS 피드 오류)"
            news_items = []
            for entry in feed.entries[:5]:
                news_items.append(f"- {entry.title}: {entry.link}")
            if not news_items:
                return "최근 시장 뉴스가 없습니다."
            return "최근 시장 뉴스:\n" + "\n".join(news_items)
        except Exception as e:
            self.log(f"⚠️ 시장 뉴스 가져오기 실패: {e}")
            return "시장 뉴스 데이터를 가져오는 데 실패했습니다."

    def analyze_trade_data(self):
        try:
            if len(self.trade_history) == 0:
                return "⚠️ 거래 내역이 없습니다."
            df = pd.DataFrame(self.trade_history)
            if df.empty:
                return "⚠️ 최근 2시간 동안 거래가 없습니다."
            if "entry_time" in df.columns:
                df["entry_time"] = pd.to_datetime(df["entry_time"])
            last_2_hours = datetime.now(self.KST) - timedelta(hours=2)
            df_recent = df[df["entry_time"] > last_2_hours]
            total_trades = len(df_recent)
            if total_trades == 0:
                return "⚠️ 최근 2시간 동안 거래가 없습니다."
            win_trades = len(df_recent[df_recent["profit_pct"] > 0])
            lose_trades = len(df_recent[df_recent["profit_pct"] < 0])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            avg_profit = df_recent["profit_pct"].mean() if total_trades > 0 else 0
            summary = (
                f"📊 최근 2시간 매매 요약\n"
                f"- 총 거래 횟수: {total_trades}\n"
                f"- 승리 횟수: {win_trades}\n"
                f"- 패배 횟수: {lose_trades}\n"
                f"- 승률: {win_rate:.2f}%\n"
                f"- 평균 손익: {avg_profit:.3f}%"
            )
            return summary
        except Exception as e:
            return f"⚠️ 거래 데이터 분석 오류: {e}"

    def update_status(self):
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                account = self.client.futures_account()
                balance = float(next((asset.get("walletBalance", 0)
                                      for asset in account.get("assets", [])
                                      if asset.get("asset") == "USDT"), 0))
                available_balance = float(next((asset.get("availableBalance", 0)
                                                for asset in account.get("assets", [])
                                                if asset.get("asset") == "USDT"), 0))
                unrealized_pnl = float(next((asset["unrealizedProfit"]
                                             for asset in account["assets"]
                                             if asset["asset"] == "USDT"), 0))
                positions = account["positions"]
                btc_position = next((pos for pos in positions if pos["symbol"] == self.symbol), None)
                position_size = 0
                leverage = self.leverage
                entry_price = 0
                if btc_position:
                    position_size = float(btc_position["positionAmt"])
                    leverage = int(btc_position["leverage"])
                    entry_price = float(btc_position["entryPrice"])
                status_message = (
                    f"📊 상태 업데이트 ({datetime.now(self.KST).strftime('%Y-%m-%d %H:%M:%S')})\n"
                    f"----------------------------\n"
                    f"💰 계정 잔고: {balance:.2f} USDT\n"
                    f"💵 사용 가능 잔고 (availableBalance): {available_balance:.2f} USDT\n"
                    f"📈 미실현 손익: {unrealized_pnl:.2f} USDT\n"
                    f"🔄 포지션: {position_size} BTC\n"
                    f"⚙️ 레버리지: {leverage}배\n"
                    f"💵 진입가: {entry_price:.2f} USDT\n"
                    f"💹 현재가: {self.last_price:.2f} USDT\n"
                    f"----------------------------\n"
                    f"📉 일일 성과:\n"
                    f"    시작 잔고: {self.daily_stats['start_balance']:.2f} USDT\n"
                    f"    현재 잔고: {self.daily_stats['current_balance']:.2f} USDT\n"
                    f"    거래 횟수: {self.daily_stats['trades_today']}\n"
                    f"    손익: {self.daily_stats['profit_today']:.2f} USDT\n"
                    f"    수익률: {(self.daily_stats['profit_today'] / self.daily_stats['start_balance'] * 100) if self.daily_stats['start_balance'] > 0 else 0:.2f}%\n"
                    f"----------------------------\n"
                )
                candle_info = ""
                if self.last_df is not None and len(self.last_df) >= 3:
                    last_three = self.last_df.tail(3)
                    candle_info += "🔍 최근 3개 15분봉 지표:\n"
                    for idx, row in last_three.iterrows():
                        candle_info += (f"  - {row['time'].strftime('%Y-%m-%d %H:%M:%S')}: "
                                        f"RSI {row['rsi']:.2f}, 윌리엄 %R {row['william']:.2f}\n")
                status_message += candle_info
                self.log(status_message)
                break
            except Exception as e:
                attempt += 1
                self.log(f"⚠️ 상태 업데이트 오류 발생 (재시도 {attempt}/{max_attempts}): {e}")
                time.sleep(2)
                if attempt == max_attempts:
                    self.log("⚠️ 상태 업데이트 재시도 실패")
                    break

    def stop(self):
        self._save_trade_history()
        self._save_trades()
        self.running = False
        self.log("🛑 자동매매 중지 요청 처리됨. 거래 내역 저장 완료.")

    def set_telegram_callback(self, callback):
        self.telegram_callback = callback

# ==============================
# GUI 클래스 (Tkinter 기반)
# ==============================
class BinanceFuturesGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("바이낸스 선물 자동매매 봇")
        self.root.geometry("900x600")
        self.root.resizable(True, True)
        self.bot = None
        self.bot_thread = None
        self._setup_ui()

    def _setup_ui(self):
        top_frame = tk.Frame(self.root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)
        # API 설정 프레임
        api_frame = tk.LabelFrame(top_frame, text="API 설정", padx=10, pady=10)
        api_frame.pack(fill=tk.X)
        tk.Label(api_frame, text="환경 설정 파일 경로:").grid(row=0, column=0, sticky=tk.W)
        self.env_path = tk.StringVar(value=".env")
        tk.Entry(api_frame, textvariable=self.env_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        # 거래 설정 프레임
        settings_frame = tk.LabelFrame(top_frame, text="거래 설정", padx=10, pady=10)
        settings_frame.pack(fill=tk.X, pady=10)
        tk.Label(settings_frame, text="심볼:").grid(row=0, column=0, sticky=tk.W)
        self.symbol = tk.StringVar(value="BTCUSDT")
        tk.Entry(settings_frame, textvariable=self.symbol, width=15).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(settings_frame, text="레버리지:").grid(row=0, column=2, sticky=tk.W)
        self.leverage = tk.IntVar(value=10)
        tk.Spinbox(settings_frame, from_=1, to=125, textvariable=self.leverage, width=5).grid(row=0, column=3, padx=5, pady=5)
        tk.Label(settings_frame, text="최대 일일 손실(%):").grid(row=1, column=0, sticky=tk.W)
        self.max_daily_loss = tk.DoubleVar(value=20.0)
        tk.Spinbox(settings_frame, from_=1, to=20, increment=0.5, textvariable=self.max_daily_loss, width=5).grid(row=1, column=1, padx=5, pady=5)
        tk.Label(settings_frame, text="1차 목표수익(%):").grid(row=2, column=0, sticky=tk.W)
        self.first_target_profit = tk.DoubleVar(value=11.0)
        tk.Spinbox(settings_frame, from_=1, to=100, increment=0.5, textvariable=self.first_target_profit, width=5).grid(row=2, column=1, padx=5, pady=5)
        tk.Label(settings_frame, text="2차 목표수익(%):").grid(row=2, column=2, sticky=tk.W)
        self.second_target_profit = tk.DoubleVar(value=22.0)
        tk.Spinbox(settings_frame, from_=1, to=100, increment=0.5, textvariable=self.second_target_profit, width=5).grid(row=2, column=3, padx=5, pady=5)
        # 일일 통계 표시 프레임
        stats_frame = tk.LabelFrame(top_frame, text="일일 통계", padx=10, pady=10)
        stats_frame.pack(fill=tk.X, pady=10)
        self.daily_profit_label = tk.Label(stats_frame, text="일일 손익: 0.00 USDT")
        self.daily_profit_label.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.trades_today_label = tk.Label(stats_frame, text="거래 횟수: 0")
        self.trades_today_label.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.loss_pct_label = tk.Label(stats_frame, text="손실률: 0.00%")
        self.loss_pct_label.grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        # 버튼 프레임
        button_frame = tk.Frame(top_frame)
        button_frame.pack(fill=tk.X, pady=10)
        self.start_button = tk.Button(button_frame, text="시작", command=self.start_bot, bg="green", fg="white", width=10)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(button_frame, text="중지", command=self.stop_bot, bg="red", fg="white", width=10, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.status_button = tk.Button(button_frame, text="상태 업데이트", command=self.update_status, width=15, state=tk.DISABLED)
        self.status_button.pack(side=tk.LEFT, padx=5)
        self.gpt_button = tk.Button(button_frame, text="GPT 분석", command=self.request_gpt, width=15, state=tk.NORMAL)
        self.gpt_button.pack(side=tk.LEFT, padx=5)
        # 로그 창
        log_frame = tk.LabelFrame(self.root, text="로그", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.status_var = tk.StringVar(value="준비됨")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def add_log(self, message):
        def _update():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, _update)

    def _update_gui_stats(self):
        if self.bot is None:
            return
        daily_stats = self.bot.daily_stats
        self.daily_profit_label.config(text=f"일일 손익: {daily_stats['profit_today']:.2f} USDT")
        self.trades_today_label.config(text=f"거래 횟수: {daily_stats['trades_today']}")
        loss_pct = abs(daily_stats["profit_today"]) / daily_stats["start_balance"] * 100 if daily_stats["start_balance"] > 0 else 0.0
        self.loss_pct_label.config(text=f"손실률: {loss_pct:.2f}%")

    def update_status(self):
        if self.bot and hasattr(self.bot, 'running') and self.bot.running:
            threading.Thread(target=self._update_bot_status, daemon=True).start()

    def _update_bot_status(self):
        try:
            self.bot.update_status()
            self.root.after(0, self._update_gui_stats)
        except Exception as e:
            self.add_log(f"⚠️ GUI 상태 업데이트 오류: {e}")

    def start_bot(self):
        try:
            if self.bot and hasattr(self.bot, 'running') and self.bot.running:
                self.stop_bot()
            env_path = self.env_path.get()
            symbol = self.symbol.get()
            leverage = self.leverage.get()
            max_daily_loss = self.max_daily_loss.get()
            first_target = self.first_target_profit.get()
            second_target = self.second_target_profit.get()
            self.bot = BinanceFuturesBot(env_path, symbol, leverage)
            self.bot.max_daily_loss_pct = max_daily_loss
            self.bot.first_target_profit_pct = first_target
            self.bot.second_target_profit_pct = second_target
            self.bot.set_telegram_callback(self.add_log)
            self.bot_thread = threading.Thread(target=self.bot.execute_trade, daemon=True)
            self.bot_thread.start()
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_button.config(state=tk.NORMAL)
            self.gpt_button.config(state=tk.NORMAL)
            self.status_var.set("실행 중")
            self.add_log("✅ 자동매매 봇 시작됨")
        except Exception as e:
            self.add_log(f"⚠️ 봇 시작 오류: {e}")
            messagebox.showerror("오류", f"봇 시작 중 오류가 발생했습니다.\n{e}")

    def stop_bot(self):
        if self.bot and hasattr(self.bot, 'running') and self.bot.running:
            self.bot.stop()
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_var.set("중지됨")
            self.add_log("🛑 자동매매 봇 중지됨")

    def request_gpt(self):
        if self.bot and hasattr(self.bot, 'running') and self.bot.running:
            threading.Thread(target=self.bot.generate_gpt_report_with_retry, daemon=True).start()

# ==============================
# 메인 실행부
# ==============================
def main():
    root = tk.Tk()
    app = BinanceFuturesGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
