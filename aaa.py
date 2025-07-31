import os
import time
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from tkinter import ttk
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
import traceback

# ==============================
# 전역 상수 및 설정 (Configuration & Constants)
# ==============================
CHECK_INTERVAL = 1          # 메인 루프 폴링 간격 (초)
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

async_worker = AsyncWorker()

# ==============================
# 거래 봇 클래스 (Trading Bot)
# ==============================
class BinanceFuturesBot:
    def __init__(self, env_path: str, symbol: str = "BTCUSDT", leverage: int = 10, trailing_stop_pct: float = 15.0):
        self.symbol = symbol
        self.leverage = leverage
        self.trailing_stop_pct = trailing_stop_pct  # 1차 매도 후 하락률 기준
        self.active_trades = []   # 개별 거래 건별 익절/손절 추적

        # 진입 조건 관련 변수 (롱/숏 모두 사용)
        self.entry_signal = None         # 기준선 값 (롱: 1봉전 윌리엄 %R, 숏: 반대)
        self.entry_close = None          # 0봉전 종가 (추가 기준)
        self.signal_type = None          # "LONG" 또는 "SHORT"

        # 마지막 기준봉 캔들 시각 및 경고 기록
        self.last_baseline_candle_time = None  
        self.last_warning_candle_time = None

        # 포지션 관리 (현재 진입된 포지션: "LONG", "SHORT" 또는 None)
        self.current_position = None

        # 기타 기존 변수들
        self.last_gpt_report_time = 0
        self.gpt_report_interval = 14400  # 4시간(초)
        self.last_status_update_time = 0
        self.status_update_interval = 900  # 15분(초) - 봉 완성 시마다 업데이트
        self.running = False
        self.last_df = None
        self.last_price = None
        self.telegram_rate_limit = {"count": 0, "reset_time": time.time() + TELEGRAM_RATE_LIMIT_INTERVAL}
        self.telegram_max_rate = TELEGRAM_RATE_LIMIT_MAX
        self.trade_lock = threading.Lock()
        self.data_lock = threading.Lock()
        self.file_lock = threading.Lock()

        # 리스크 관리
        self.max_daily_loss_pct = 20.0
        self.stop_loss_pct = 100.0      # 현재 미사용
        self.max_position_usdt = 1000000
        self.daily_stats = {
            "start_balance": 0.0,
            "current_balance": 0.0,
            "trades_today": 0,
            "profit_today": 0.0,
            "date": datetime.now(pytz.timezone('Asia/Seoul')).strftime("%Y-%m-%d")
        }
        # 매매 목표 (GUI에서 설정)
        self.first_target_profit_pct = 11.0
        self.second_target_profit_pct = 22.0
        # 거래 히스토리
        self.trade_history = []
        # 한국 시간대
        self.KST = pytz.timezone('Asia/Seoul')

        # API 및 환경 설정 로드
        self._load_env(env_path)
        self._init_client()
        self._load_trades()
        self._load_trade_history()
        self._init_daily_stats()

        self.log("✅ 프로그램 초기화 완료. 최초 GPT 보고서 요청 중...")
        self.generate_gpt_report_with_retry()

    # ------------- 유틸리티 및 로그 -------------
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
        except Exception as e:
            logger.error(f"GUI alive check 오류: {e}")
            return True

    def _rate_limited_telegram(self, message: str):
        if not (self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID):
            return
        current_time = time.time()
        if current_time > self.telegram_rate_limit["reset_time"]:
            self.telegram_rate_limit = {"count": 0, "reset_time": current_time + TELEGRAM_RATE_LIMIT_INTERVAL}
        if self.telegram_rate_limit["count"] >= self.telegram_max_rate:
            logger.warning("텔레그램 메시지 속도 제한 도달, 전송 건너뜀")
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

    # ------------- 심볼 처리 -------------
    def coin_name(self):
        return self.symbol.replace("USDT", "").upper()

    # ------------- 환경 및 API 초기화 -------------
    def _load_env(self, env_path: str):
        try:
            if not os.path.exists(env_path):
                self.log(f"⚠️ 환경 설정 파일 없음: {env_path}")
                raise FileNotFoundError(f"환경 설정 파일 없음: {env_path}")
            load_dotenv(env_path)
            self.API_KEY = os.getenv("BINANCE_API_KEY")
            self.API_SECRET = os.getenv("BINANCE_SECRET_KEY")
            self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
            self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
            self.GPT_API_URL = os.getenv("GPT_API_URL")
            self.GPT_API_KEY = os.getenv("GPT_API_KEY")
            self.ALLOWED_IP = os.getenv("ALLOWED_IP", "")
            if not self.API_KEY or not self.API_SECRET:
                self.log("⚠️ API 키 미설정 (.env 파일 확인)")
                raise ValueError("API 키 미설정")
            if not self.GPT_API_URL or not self.GPT_API_KEY:
                self.log("⚠️ GPT API 설정 누락, 보고서 기능 제한 가능")
        except Exception as e:
            self.log(f"⚠️ _load_env 오류: {traceback.format_exc()}")
            raise

    def _init_client(self):
        try:
            self.client = Client(self.API_KEY, self.API_SECRET)
            account_status = self.client.get_account_status()
            if account_status.get('data') != 'Normal':
                self.log(f"⚠️ 계정 상태 비정상: {account_status}")
            self.client.ping()
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            try:
                self.client.futures_change_margin_type(symbol=self.symbol, marginType='CROSSED')
            except BinanceAPIException as e:
                if e.code == -4046:
                    self.log("⚠️ 마진 타입 이미 CROSSED")
                else:
                    raise
            self.log(f"✅ 바이낸스 선물 API 연결, 레버리지 {self.leverage}배 설정 완료")
        except Exception as e:
            self.log(f"⚠️ _init_client 오류: {traceback.format_exc()}")
            raise

    # ------------- 거래 내역 및 통계 관리 -------------
    def _load_trades(self):
        try:
            if os.path.exists("active_trades.json"):
                with self.file_lock, open("active_trades.json", "r") as f:
                    self.active_trades = json.load(f)
                self.log(f"✅ 기존 거래 내역 로드: {len(self.active_trades)}건")
        except Exception as e:
            self.log(f"⚠️ _load_trades 오류: {traceback.format_exc()}")
            self.active_trades = []

    def _load_trade_history(self):
        try:
            if os.path.exists("trade_history.json"):
                with self.file_lock, open("trade_history.json", "r") as f:
                    self.trade_history = json.load(f)
                self.log(f"✅ 기존 거래 히스토리 로드: {len(self.trade_history)}건")
        except Exception as e:
            self.log(f"⚠️ _load_trade_history 오류: {traceback.format_exc()}")
            self.trade_history = []

    def _save_trades(self):
        try:
            with self.file_lock, self.trade_lock, open("active_trades.json", "w") as f:
                json.dump(self.active_trades, f)
        except Exception as e:
            self.log(f"⚠️ _save_trades 오류: {traceback.format_exc()}")

    def _save_trade_history(self):
        try:
            with self.file_lock, open("trade_history.json", "w") as f:
                json.dump(self.trade_history, f)
        except Exception as e:
            self.log(f"⚠️ _save_trade_history 오류: {traceback.format_exc()}")

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
            self.log(f"✅ 일일 통계 초기화: {today}, 잔고 {balance} USDT")

    def _update_daily_stats(self, profit=0.0):
        balance = self.get_balance()
        self.daily_stats["current_balance"] = balance
        self.daily_stats["trades_today"] += 1
        self.daily_stats["profit_today"] += profit
        if self.daily_stats["profit_today"] < 0:
            loss_pct = abs(self.daily_stats["profit_today"]) / self.daily_stats["start_balance"] * 100
            if loss_pct >= self.max_daily_loss_pct:
                self.log(f"⚠️ 일일 최대 손실 한도 도달: {loss_pct:.2f}%. 자동매매 중지")
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
        except Exception as e:
            self.log(f"⚠️ get_balance 오류: {traceback.format_exc()}")
            return 0.0

    # ------------- 데이터 수집 및 지표 계산 -------------
    def get_data(self, remove_incomplete_candle=False):
        """
        remove_incomplete_candle:
          True  -> 최신 캔들이 아직 종료되지 않았다면 해당 봉을 제거하고 사용
          False -> 모든 캔들을 사용 (버퍼 제거)
        """
        try:
            with self.data_lock:
                klines = self.client.futures_klines(
                    symbol=self.symbol,
                    interval=Client.KLINE_INTERVAL_15MINUTE,
                    limit=200
                )
                if not klines or len(klines) < 14:
                    self.log("⚠️ 충분한 데이터 없음 (최소 14개 필요)")
                    return None

                df = pd.DataFrame(klines, columns=[
                    "time", "open", "high", "low", "close", "volume",
                    "close_time", "quote_asset_volume", "trades",
                    "taker_base", "taker_quote", "ignore"
                ])
                df["time"] = pd.to_datetime(df["time"], unit='ms', utc=True).dt.tz_convert(self.KST)
                df["close_time"] = pd.to_datetime(df["close_time"], unit='ms', utc=True).dt.tz_convert(self.KST)
                for col in ["open", "close", "high", "low", "volume"]:
                    df[col] = df[col].astype(float)

                if remove_incomplete_candle:
                    latest_candle_time = df["close_time"].iloc[-1]
                    current_time = datetime.now(self.KST)
                    # 만약 현재 시간이 마지막 캔들의 종료시간보다 15분 이상 지났는데 데이터가 업데이트되지 않았다면 대기
                    expected_next_candle_close = latest_candle_time + timedelta(minutes=15)
                    if current_time >= expected_next_candle_close:
                        self.log(f"🕒 새로운 15분봉 대기 중: 현재 시간 {current_time.strftime('%H:%M:%S')}, 예상 마감 {expected_next_candle_close.strftime('%H:%M:%S')}")
                        wait_start = time.time()
                        while True:
                            new_df = self.get_data(remove_incomplete_candle=False)
                            if new_df is None or len(new_df) < 1:
                                time.sleep(1)
                                continue
                            new_latest_candle_time = new_df["close_time"].iloc[-1]
                            if new_latest_candle_time > latest_candle_time:
                                df = new_df.copy()
                                break
                            if time.time() - wait_start > 60:
                                self.log("⚠️ 15분봉 업데이트 대기 시간 초과, 기존 데이터 사용")
                                break
                            time.sleep(1)
                    if len(df) >= 4 and datetime.now(self.KST) < df["close_time"].iloc[-1]:
                        df = df.iloc[:-1]

                # RSI 계산 (Wilder's smoothing)
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

                # 이동평균, 볼린저 밴드, MACD 계산
                df["ma20"] = df["close"].rolling(window=20).mean()
                df["ma50"] = df["close"].rolling(window=50).mean()
                df["ma20_std"] = df["close"].rolling(window=20).std()
                df["upper_band"] = df["ma20"] + (df["ma20_std"] * 2)
                df["lower_band"] = df["ma20"] - (df["ma20_std"] * 2)
                df["ema12"] = df["close"].ewm(span=12).mean()
                df["ema26"] = df["close"].ewm(span=26).mean()
                df["macd"] = df["ema12"] - df["ema26"]
                df["signal"] = df["macd"].ewm(span=9).mean()
                df["macd_histogram"] = df["macd"] - df["signal"]

                return df
        except Exception as e:
            self.log(f"⚠️ get_data 오류: {traceback.format_exc()}")
            return None

    def _get_decimal_places(self, step_size: float) -> int:
        step_str = "{:g}".format(step_size)
        return len(step_str.split('.')[1]) if '.' in step_str else 0

    # ------------- 통합 주문 진입/청산 함수 -------------
    def safe_entry(self, entry_type: str, amount_usdt: float):
        try:
            ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
            current_price = float(ticker["price"])
            exchange_info = self.client.futures_exchange_info()
            symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == self.symbol), None)
            if not symbol_info:
                self.log(f"⚠️ 심볼 정보 없음: {self.symbol}")
                return None
            quantity_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            if not quantity_filter:
                self.log(f"⚠️ LOT_SIZE 필터 없음: {self.symbol}")
                return None

            min_qty = float(quantity_filter['minQty'])
            max_qty = float(quantity_filter['maxQty'])
            step_size = float(quantity_filter['stepSize'])
            raw_quantity = amount_usdt / current_price
            decimal_places = self._get_decimal_places(step_size)
            quantity = round(raw_quantity - (raw_quantity % step_size), decimal_places)
            if quantity < min_qty:
                self.log(f"⚠️ 수량 {quantity} < 최소 {min_qty}. 최소 수량으로 조정.")
                quantity = min_qty
            if quantity > max_qty:
                quantity = max_qty
                self.log(f"⚠️ 수량 {quantity} > 최대 {max_qty}, 제한됨")
            if quantity <= 0:
                self.log(f"⚠️ {entry_type} 진입 수량 0 이하, 취소")
                return None

            coin = self.coin_name()
            self.log(f"🛒 {entry_type} 진입 주문 시도: {quantity} {coin} (약 {amount_usdt} USDT)")
            with self.trade_lock:
                if entry_type == "LONG":
                    order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side=SIDE_BUY,
                        type=ORDER_TYPE_MARKET,
                        quantity=quantity,
                        positionSide="LONG"
                    )
                elif entry_type == "SHORT":
                    order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side=SIDE_SELL,
                        type=ORDER_TYPE_MARKET,
                        quantity=quantity,
                        positionSide="SHORT"
                    )
                else:
                    self.log("⚠️ safe_entry: 잘못된 entry_type")
                    return None

            order_id = order.get('orderId')
            if not order_id:
                self.log(f"⚠️ {entry_type} 주문 ID 없음")
                return None
            for _ in range(ORDER_POLLING_MAX_ATTEMPTS):
                order_status = self.client.futures_get_order(symbol=self.symbol, orderId=order_id)
                if order_status.get('status') == ORDER_STATUS_FILLED:
                    avg_price = float(order_status.get('avgPrice', current_price))
                    executed_qty = float(order_status.get('executedQty', quantity))
                    self.log(f"✅ {entry_type} 주문 체결: {executed_qty} {coin} at {avg_price} USDT")
                    return {"order_id": order_id, "price": avg_price, "quantity": executed_qty, "side": entry_type,
                            "time": datetime.now(self.KST).strftime("%Y-%m-%d %H:%M:%S")}
                time.sleep(ORDER_POLLING_SLEEP)
            self.log(f"⚠️ {entry_type} 주문 체결 시간 초과: {order_id}")
            return None
        except BinanceAPIException as e:
            if e.code == -2019:
                self.log(f"⚠️ safe_entry ({entry_type}) 오류: Margin is insufficient. 주문 금액이 부족하면 매수를 진행하지 않습니다.\n{traceback.format_exc()}")
                return None
            else:
                self.log(f"⚠️ safe_entry ({entry_type}) 오류: {traceback.format_exc()}")
                return None
        except Exception as e:
            self.log(f"⚠️ safe_entry ({entry_type}) 오류: {traceback.format_exc()}")
            return None

    def safe_exit(self, exit_type: str, quantity: float):
        try:
            coin = self.coin_name()
            self.log(f"🛒 {exit_type} 청산 주문 시도: {quantity} {coin}")
            with self.trade_lock:
                if exit_type == "LONG":
                    order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side=SIDE_SELL,
                        type=ORDER_TYPE_MARKET,
                        quantity=quantity,
                        reduceOnly=True,
                        positionSide="LONG"
                    )
                elif exit_type == "SHORT":
                    order = self.client.futures_create_order(
                        symbol=self.symbol,
                        side=SIDE_BUY,
                        type=ORDER_TYPE_MARKET,
                        quantity=quantity,
                        reduceOnly=True,
                        positionSide="SHORT"
                    )
                else:
                    self.log("⚠️ safe_exit: 잘못된 exit_type")
                    return None

            order_id = order.get('orderId')
            if not order_id:
                self.log(f"⚠️ {exit_type} 청산 주문 ID 없음")
                return None
            for _ in range(ORDER_POLLING_MAX_ATTEMPTS):
                order_status = self.client.futures_get_order(symbol=self.symbol, orderId=order_id)
                if order_status.get('status') == ORDER_STATUS_FILLED:
                    avg_price = float(order_status.get('avgPrice', self.last_price))
                    executed_qty = float(order_status.get('executedQty', quantity))
                    self.log(f"✅ {exit_type} 청산 체결: {executed_qty} {coin} at {avg_price} USDT")
                    return {"order_id": order_id, "price": avg_price, "quantity": executed_qty, 
                            "side": "SELL" if exit_type=="LONG" else "BUY",
                            "time": datetime.now(self.KST).strftime("%Y-%m-%d %H:%M:%S")}
                time.sleep(ORDER_POLLING_SLEEP)
            self.log(f"⚠️ {exit_type} 청산 주문 체결 시간 초과: {order_id}")
            return None
        except Exception as e:
            self.log(f"⚠️ safe_exit ({exit_type}) 오류: {traceback.format_exc()}")
            return None

    # ------------- 기준선 조건 판별 -------------
    def check_long_conditions(self, df):
        if len(df) < 3:
            return False, None
        rsi_2, rsi_1, rsi_0 = df["rsi"].iloc[-3], df["rsi"].iloc[-2], df["rsi"].iloc[-1]
        will_2, will_1, will_0 = df["william"].iloc[-3], df["william"].iloc[-2], df["william"].iloc[-1]
        if not (rsi_0 <= 35 and will_0 <= -70):
            return False, None
        if not (rsi_2 > rsi_1 > rsi_0):
            return False, None
        if not (will_2 > will_1 and will_1 < will_0):
            return False, None
        return True, will_1

    def check_short_conditions(self, df):
        if len(df) < 3:
            return False, None
        rsi_2, rsi_1, rsi_0 = df["rsi"].iloc[-3], df["rsi"].iloc[-2], df["rsi"].iloc[-1]
        will_2, will_1, will_0 = df["william"].iloc[-3], df["william"].iloc[-2], df["william"].iloc[-1]
        if not (rsi_0 >= 65 and will_0 >= -30):
            return False, None
        if not (rsi_2 < rsi_1 < rsi_0):
            return False, None
        if not (will_2 < will_1 and will_1 > will_0):
            return False, None
        return True, will_1

    # ------------- 자동 매매 실행 및 포지션 전환 -------------
    def execute_trade(self):
        self.running = True
        self._init_daily_stats()
        self.log(f"✅ 자동매매 시작: 심볼={self.symbol}, 레버리지={self.leverage}배")
        self.log(f"📊 리스크: 일일 최대 손실={self.max_daily_loss_pct}%, 최대 포지션={self.max_position_usdt} USDT")
        while self.running:
            try:
                df = self.get_data(remove_incomplete_candle=True)
                if df is None or len(df) < 14:
                    time.sleep(CHECK_INTERVAL)
                    continue

                latest_candle_time = df["close_time"].iloc[-1]
                current_time = datetime.now(self.KST)
                expected_next_candle_close = latest_candle_time + timedelta(minutes=15)
                if current_time >= expected_next_candle_close:
                   self.log(f"🕒 15분봉 업데이트 확인: 현재 시간 {current_time.strftime('%H:%M:%S')}, 예상 캔들 마감 {expected_next_candle_close.strftime('%H:%M:%S')}")
  
                # 🔹 캔들 마감 후 10초 대기 (API 업데이트 지연 방지)
                time.sleep(10)

                max_wait_time = 30  # 최대 30초 대기
                wait_start = time.time()

                while True:
                    new_df = self.get_data(remove_incomplete_candle=True)
                    if new_df is None or len(new_df) < 14:
                        time.sleep(1)
                        continue

                    new_latest_candle_time = new_df["close_time"].iloc[-1]

                     # 새로운 캔들이 감지되면 업데이트
                    if new_latest_candle_time > latest_candle_time:
                        df = new_df.copy()
                        latest_candle_time = new_latest_candle_time
                        break

                     # 30초 초과 시, 강제 종료 (무한 루프 방지)
                    if time.time() - wait_start > max_wait_time:
                        self.log("⚠️ 새로운 캔들 업데이트 지연! 기존 데이터로 진행")
                        break

                    time.sleep(1)

                if current_time >= expected_next_candle_close:
                    self.log(f"🕒 15분봉 업데이트 확인: 현재 시간 {current_time.strftime('%H:%M:%S')}, 예상 캔들 마감 {expected_next_candle_close.strftime('%H:%M:%S')}")
                    while True:
                        new_df = self.get_data(remove_incomplete_candle=True)
                        if new_df is None or len(new_df) < 14:
                            time.sleep(1)
                            continue
                        new_latest_candle_time = new_df["close_time"].iloc[-1]
                        if new_latest_candle_time > latest_candle_time:
                            df = new_df.copy()
                            latest_candle_time = new_latest_candle_time
                            break
                        time.sleep(1)

                if (self.last_baseline_candle_time is None) or (latest_candle_time > self.last_baseline_candle_time):
                    self.last_baseline_candle_time = latest_candle_time
                    self.update_status()
                    long_valid, long_baseline = self.check_long_conditions(df)
                    short_valid, short_baseline = self.check_short_conditions(df)
                    if long_valid:
                        self.entry_signal = long_baseline  # 기준선(1)
                        self.entry_close = df["close"].iloc[-1]  # 기준선(2)
                        self.signal_type = "LONG"
                        self.log(f"✅ 기준선 확정 (롱): 기준선 {long_baseline:.2f}, 종가 {self.entry_close:.2f} (캔들 종료 {latest_candle_time.strftime('%Y-%m-%d %H:%M:%S')})")
                    elif short_valid:
                        self.entry_signal = short_baseline
                        self.entry_close = df["close"].iloc[-1]
                        self.signal_type = "SHORT"
                        self.log(f"✅ 기준선 확정 (숏): 기준선 {short_baseline:.2f}, 종가 {self.entry_close:.2f} (캔들 종료 {latest_candle_time.strftime('%Y-%m-%d %H:%M:%S')})")
                    else:
                        self.entry_signal = None
                        self.entry_close = None
                        self.signal_type = None

                ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
                self.last_price = float(ticker["price"])
                self.last_df = df

                self.manage_active_trades()

                # 추가 진입 조건 확인 (1초 단위)
                if self.entry_signal is not None:
                    previous_close = df["close"].iloc[-2]
                    current_close = df["close"].iloc[-1]
                    if self.signal_type == "LONG":
                        conditionA = (df["william"].iloc[-1] < self.entry_signal and df["william"].iloc[-2] >= self.entry_signal)
                        conditionB = (df["william"].iloc[-1] < -90 and df["william"].iloc[-2] >= -90)
                        conditionC = (current_close < self.entry_close * 0.997)
                        if conditionA or conditionB or conditionC:
                            if self.current_position == "SHORT":
                                qty = sum(t["entry_quantity"] for t in self.active_trades if t["status"] == "ACTIVE")
                                exit_order = self.safe_exit("SHORT", qty)
                                if exit_order:
                                    self.log("✅ 기존 숏 포지션 전량 청산")
                                    self.trade_history.extend(self.active_trades)
                                    self.active_trades = []
                                    self.current_position = None
                            balance = self.get_balance()
                            buy_amount = balance * 0.25 * self.leverage
                            if buy_amount < 10:
                                self.log(f"⚠️ 롱 진입 금액 너무 작음: {buy_amount:.2f} USDT")
                            else:
                                order = self.safe_entry("LONG", buy_amount)
                                if order:
                                    trade_info = {
                                        "id": str(uuid.uuid4()),
                                        "entry_price": order["price"],
                                        "entry_quantity": order["quantity"],
                                        "remaining_quantity": order["quantity"],
                                        "entry_time": order["time"],
                                        "entry_order_id": order["order_id"],
                                        "sell_stage": 0,
                                        "status": "ACTIVE",
                                        "position": "LONG"
                                    }
                                    with self.trade_lock:
                                        self.active_trades.append(trade_info)
                                        self._save_trades()
                                    coin = self.coin_name()
                                    self.log(f"✅ 롱 포지션 진입: {order['quantity']} {coin} at {order['price']} USDT")
                                    self.current_position = "LONG"
                                    self.entry_signal = None
                    elif self.signal_type == "SHORT":
                        conditionA = (df["william"].iloc[-1] > self.entry_signal and df["william"].iloc[-2] <= self.entry_signal)
                        conditionB = (df["william"].iloc[-1] > -10 and df["william"].iloc[-2] <= -10)
                        conditionC = (current_close > self.entry_close * 1.003)
                        if conditionA or conditionB or conditionC:
                            if self.current_position == "LONG":
                                qty = sum(t["entry_quantity"] for t in self.active_trades if t["status"] == "ACTIVE")
                                exit_order = self.safe_exit("LONG", qty)
                                if exit_order:
                                    self.log("✅ 기존 롱 포지션 전량 청산")
                                    self.trade_history.extend(self.active_trades)
                                    self.active_trades = []
                                    self.current_position = None
                            balance = self.get_balance()
                            sell_amount = balance * 0.25 * self.leverage
                            if sell_amount < 10:
                                self.log(f"⚠️ 숏 진입 금액 너무 작음: {sell_amount:.2f} USDT")
                            else:
                                order = self.safe_entry("SHORT", sell_amount)
                                if order:
                                    trade_info = {
                                        "id": str(uuid.uuid4()),
                                        "entry_price": order["price"],
                                        "entry_quantity": order["quantity"],
                                        "remaining_quantity": order["quantity"],
                                        "entry_time": order["time"],
                                        "entry_order_id": order["order_id"],
                                        "sell_stage": 0,
                                        "status": "ACTIVE",
                                        "position": "SHORT"
                                    }
                                    with self.trade_lock:
                                        self.active_trades.append(trade_info)
                                        self._save_trades()
                                    coin = self.coin_name()
                                    self.log(f"✅ 숏 포지션 진입: {order['quantity']} {coin} at {order['price']} USDT")
                                    self.current_position = "SHORT"
                                    self.entry_signal = None

                # 포지션 진입 전까지 1분 단위 메시지 출력 (BTCUSDT 화면 한정)
                if self.symbol.upper() == "BTCUSDT" and self.entry_signal is not None:
                    self.log("비트코인 롱진입조건확인중")
                time.sleep(CHECK_INTERVAL)
            except BinanceAPIException as e:
                self.log(f"⚠️ Binance API 오류: {traceback.format_exc()}")
                time.sleep(30)
            except Exception as e:
                self.log(f"⚠️ execute_trade 오류: {traceback.format_exc()}")
                time.sleep(30)

        self.log("❌ 자동매매 종료됨")

    # ------------- 수정된 매도(청산) 로직 -------------
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
                coin = self.coin_name()
                if trade["position"] == "LONG":
                    # 레버리지 적용한 수익률 계산 (롱)
                    profit_pct = ((current_price - entry_price) / entry_price * 100) * self.leverage
                    if trade.get("sell_stage", 0) == 0 and profit_pct >= self.first_target_profit_pct:
                        sell_qty = trade["remaining_quantity"] / 2
                        sell_order = self.safe_exit("LONG", sell_qty)
                        if sell_order:
                            trade["first_sell"] = sell_order
                            trade["sell_stage"] = 1
                            trade["remaining_quantity"] -= sell_qty
                            self.log(f"💰 {self.first_target_profit_pct}% 목표 달성(롱): 절반 매도, 잔여 {trade['remaining_quantity']} {coin}")
                    elif trade.get("sell_stage", 0) == 1 and profit_pct >= self.second_target_profit_pct:
                        sell_qty = trade["remaining_quantity"]
                        sell_order = self.safe_exit("LONG", sell_qty)
                        if sell_order:
                            trade["second_sell"] = sell_order
                            trade["sell_stage"] = 2
                            trade["exit_price"] = sell_order["price"]
                            trade["exit_time"] = sell_order["time"]
                            trade["status"] = "CLOSED"
                            trade["profit_pct"] = profit_pct
                            trade["profit_usdt"] = (sell_order["price"] - entry_price) * trade["entry_quantity"]
                            self.log(f"💰 {self.second_target_profit_pct}% 목표 달성(롱): 전량 매도, 거래 종료")
                            self.trade_history.append(trade)
                            self._save_trade_history()
                            self._update_daily_stats(trade["profit_usdt"])
                elif trade["position"] == "SHORT":
                    # 레버리지 적용한 수익률 계산 (숏)
                    profit_pct = ((entry_price - current_price) / entry_price * 100) * self.leverage
                    if trade.get("sell_stage", 0) == 0 and profit_pct >= self.first_target_profit_pct:
                        sell_qty = trade["remaining_quantity"] / 2
                        sell_order = self.safe_exit("SHORT", sell_qty)
                        if sell_order:
                            trade["first_sell"] = sell_order
                            trade["sell_stage"] = 1
                            trade["remaining_quantity"] -= sell_qty
                            self.log(f"💰 {self.first_target_profit_pct}% 목표 달성(숏): 절반 청산, 잔여 {trade['remaining_quantity']} {coin}")
                    elif trade.get("sell_stage", 0) == 1 and profit_pct >= self.second_target_profit_pct:
                        sell_qty = trade["remaining_quantity"]
                        sell_order = self.safe_exit("SHORT", sell_qty)
                        if sell_order:
                            trade["second_sell"] = sell_order
                            trade["sell_stage"] = 2
                            trade["exit_price"] = sell_order["price"]
                            trade["exit_time"] = sell_order["time"]
                            trade["status"] = "CLOSED"
                            trade["profit_pct"] = profit_pct
                            trade["profit_usdt"] = (entry_price - sell_order["price"]) * trade["entry_quantity"]
                            self.log(f"💰 {self.second_target_profit_pct}% 목표 달성(숏): 전량 청산, 거래 종료")
                            self.trade_history.append(trade)
                            self._save_trade_history()
                            self._update_daily_stats(trade["profit_usdt"])
                updated_trades.append(trade)
            self.active_trades = updated_trades
            self._save_trades()

    # ------------- GPT 보고서 생성 -------------
    def generate_gpt_report_with_retry(self, max_retries=RETRY_COUNT_GPT):
        for attempt in range(max_retries):
            try:
                report = self.generate_gpt_report()
                if report:
                    return report
            except Exception as e:
                self.log(f"⚠️ GPT 보고서 생성 실패 (시도 {attempt+1}/{max_retries}): {traceback.format_exc()}")
                if attempt < max_retries - 1:
                    time.sleep(10)
        self.log("❌ GPT 보고서 생성 실패: 최대 재시도 횟수 초과")
        return None

    def generate_gpt_report(self):
        df = self.last_df
        if df is None or len(df) < 14:
            self.log("거래 데이터 부족, 기본 보고서 생성")
            basic_news = self.get_market_news()
            basic_strategy = "기본 전략: 시장 상황에 따라 포지션 점진적 축소"
            now = datetime.now(self.KST).strftime('%Y-%m-%d %H:%M:%S')
            report = (
                f"🧠 GPT 기본 보고서 ({now})\n"
                "---------------------------------------------------\n"
                "거래 데이터 부족\n\n"
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
                candle_info += "🔍 최근 3개 15분봉:\n"
                for idx, row in last_three.iterrows():
                    try:
                        ct = row['time'].astimezone(self.KST).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        ct = row['time'].strftime('%Y-%m-%d %H:%M:%S')
                    candle_info += f"  - {ct}: RSI {row['rsi']:.2f}, 윌리엄 %R {row['william']:.2f}\n"
            active_trades_count = len([t for t in self.active_trades if t["status"] == "ACTIVE"])
            market_news = self.get_market_news()
            trade_summary = self.analyze_trade_data()
            trade_history_detail = ""
            coin = self.coin_name()
            for trade in self.trade_history:
                trade_history_detail += (
                    f"\n거래 ID: {trade['id']}\n"
                    f"매수 가격: {trade['entry_price']:.2f} USDT\n"
                    f"매도 가격: {trade.get('exit_price', 0):.2f} USDT\n"
                    f"수량: {trade['entry_quantity']:.4f} {coin}\n"
                    f"수익률: {trade['profit_pct']:.2f}%\n"
                    f"수익금: {trade['profit_usdt']:.2f} USDT\n"
                    f"거래 시간: {trade['entry_time']} ~ {trade.get('exit_time', '')}\n"
                )
            account = self.client.futures_account()
            positions = account["positions"]
            pos = next((p for p in positions if p["symbol"] == self.symbol), None)
            positions_info = ""
            if pos:
                pos_size = float(pos["positionAmt"])
                entry_price = float(pos["entryPrice"])
                coin = self.coin_name()
                positions_info = f"\n현재 포지션:\n포지션 수량: {pos_size} {coin}\n진입가: {entry_price} USDT\n"
            request_data = {
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "system",
                        "content": ("대답은 한글로 반드시 하세요. You are a trading assistant. "
                                    "Provide detailed analysis based on the following data. "
                                    "Do NOT suggest automatic strategy changes; only provide advice.")
                    },
                    {
                        "role": "user",
                        "content": (
                            f"\n+아래 데이터를 기반으로 트레이딩 전략 평가 및 개선점을 제시하세요.\n"
                            f"+현재 전략:\n"
                            f"  - RSI와 윌리엄 %R을 사용하여 매수 신호 확인\n"
                            f"  - 롱 조건: RSI<=35, 윌리엄 %R<=-70, 연속 RSI 하락, 윌리엄 %R 직전 최저 후 반등\n"
                            f"  - 숏 조건: RSI>=65, 윌리엄 %R>=-30, 연속 RSI 상승, 윌리엄 %R 직전 최고 후 하락\n"
                            f"  - 추가 조건: 최신 캔들 종가가 전 캔들 대비 0.3% 이상 변동 시 진입\n"
                            f"  - 반대 신호 발생 시 기존 포지션 전량 청산 후 반대 진입\n"
                            f"+목표: 포지션 분할 매도, 트레일링 스탑, 일일 최대 손실 관리\n"
                            f"\n📊 최근 2시간 거래 요약:\n{trade_summary}\n"
                            f"\n🔹 최근 캔들:\n{recent_candles}\n"
                            f"\n🔹 주요 지표:\n{indicators}\n"
                            f"\n🔹 활성 거래 건수: {active_trades_count}\n"
                            f"🔹 시장 뉴스: {market_news}\n" # 이 부분 추가
                            f"\n📉 상세 거래 내역:\n{trade_history_detail}\n"
                            f"{positions_info}\n"
                            f"\n👉 거래 내역 없을 경우, 상세 보고서를 제공하세요.\n"
                        )
                    }
                ],
                "temperature": 0.7
            }
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.GPT_API_KEY}"}
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
                self.log("⚠️ GPT 분석 결과 없음")
                return None
        except Exception as e:
            self.log(f"⚠️ generate_gpt_report 오류: {traceback.format_exc()}")
            return None

    async def _async_generate_gpt_report(self, request_data: dict, headers: dict):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(self.GPT_API_URL, headers=headers, data=json.dumps(request_data)) as response:
                    if response.status == 200:
                        result = await response.json()
                        analysis = result.get("choices", [{}])[0].get("message", {}).get("content", "분석 결과 없음")
                        return analysis
                    elif response.status == 403:
                        self.log("⚠️ GPT API 403 오류")
                        return None
                    else:
                        text = await response.text()
                        self.log(f"⚠️ GPT API 오류: HTTP {response.status}, {text}")
                        return None
        except Exception as e:
            self.log(f"⚠️ _async_generate_gpt_report 오류: {traceback.format_exc()}")
            return None

    def get_market_news(self):
        try:
            feed_url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                self.log(f"⚠️ RSS 피드 오류: {feed.bozo_exception}")
                return "시장 뉴스 가져오기 실패 (RSS 오류)"
            news_items = [f"- {entry.title}: {entry.link}" for entry in feed.entries[:5]]
            return "최근 시장 뉴스:\n" + "\n".join(news_items) if news_items else "최근 뉴스 없음."
        except Exception as e:
            self.log(f"⚠️ get_market_news 오류: {traceback.format_exc()}")
            return "시장 뉴스 가져오기 실패."

    def analyze_trade_data(self):
        try:
            if len(self.trade_history) == 0:
                return "⚠️ 거래 내역 없음."
            df = pd.DataFrame(self.trade_history)
            if df.empty:
                return "⚠️ 최근 2시간 거래 없음."
            df["entry_time"] = pd.to_datetime(df["entry_time"])
            last_2_hours = datetime.now(self.KST) - timedelta(hours=2)
            df_recent = df[df["entry_time"] > last_2_hours]
            total = len(df_recent)
            if total == 0:
                return "⚠️ 최근 2시간 거래 없음."
            wins = len(df_recent[df_recent["profit_pct"] > 0])
            losses = len(df_recent[df_recent["profit_pct"] < 0])
            win_rate = (wins / total) * 100 if total > 0 else 0
            avg_profit = df_recent["profit_pct"].mean() if total > 0 else 0
            return (f"📊 최근 2시간 거래 요약\n- 총 거래: {total}\n- 승: {wins}\n- 패: {losses}\n"
                    f"- 승률: {win_rate:.2f}%\n- 평균 손익: {avg_profit:.3f}%")
        except Exception as e:
            return f"⚠️ analyze_trade_data 오류: {traceback.format_exc()}"

    def update_status(self):
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                account = self.client.futures_account()
                balance = float(next((asset.get("walletBalance", 0)
                                      for asset in account.get("assets", [])
                                      if asset.get("asset") == "USDT"), 0))
                available = float(next((asset.get("availableBalance", 0)
                                        for asset in account.get("assets", [])
                                        if asset.get("asset") == "USDT"), 0))
                unreal = float(next((asset["unrealizedProfit"]
                                     for asset in account["assets"]
                                     if asset["asset"] == "USDT"), 0))
                positions = account["positions"]
                pos = next((p for p in positions if p["symbol"] == self.symbol), None)
                pos_size = float(pos["positionAmt"]) if pos else 0
                entry_price = float(pos["entryPrice"]) if pos else 0
                coin = self.coin_name()
                current_price_str = f"{self.last_price:.2f}" if self.last_price is not None else "N/A"
                if pos:
                    position_side = pos.get("positionSide", "N/A")
                else:
                    position_side = "없음"
                status_msg = (
                    f"📊 상태 업데이트 ({datetime.now(self.KST).strftime('%Y-%m-%d %H:%M:%S')})\n"
                    f"코인: {coin}\n"
                    "----------------------------\n"
                    f"💰 잔고: {balance:.2f} USDT\n"
                    f"💵 사용 가능: {available:.2f} USDT\n"
                    f"📈 미실현: {unreal:.2f} USDT\n"
                    f"🔄 포지션: {pos_size} {coin} ({position_side})\n"
                    f"⚙️ 레버리지: {self.leverage}배\n"
                    f"💵 진입가: {entry_price:.2f} USDT\n"
                    f"💹 현재가: {current_price_str} USDT\n"
                    "----------------------------\n"
                    f"📉 일일 성과:\n    시작 잔고: {self.daily_stats['start_balance']:.2f} USDT\n"
                    f"    현재 잔고: {self.daily_stats['current_balance']:.2f} USDT\n"
                    f"    거래 횟수: {self.daily_stats['trades_today']}\n"
                    f"    손익: {self.daily_stats['profit_today']:.2f} USDT\n"
                    f"    수익률: {(self.daily_stats['profit_today'] / self.daily_stats['start_balance'] * 100) if self.daily_stats['start_balance'] > 0 else 0:.2f}%\n"
                    "----------------------------\n"
                )
                candle_info = ""
                if self.last_df is not None and len(self.last_df) >= 3:
                    last_three = self.last_df.tail(3)
                    candle_info += "🔍 최근 3개 15분봉:\n"
                    for idx, row in last_three.iterrows():
                        candle_info += f"  - {row['time'].strftime('%Y-%m-%d %H:%M:%S')}: RSI {row['rsi']:.2f}, 윌리엄 %R {row['william']:.2f}\n"
                status_msg += candle_info
                self.log(status_msg)
                break
            except Exception as e:
                attempt += 1
                self.log(f"⚠️ update_status 오류 (재시도 {attempt}/{max_attempts}): {traceback.format_exc()}")
                time.sleep(2)
                if attempt == max_attempts:
                    self.log("⚠️ update_status 재시도 실패")
                    break

    def stop(self):
        self._save_trade_history()
        self._save_trades()
        self.running = False
        self.log("🛑 자동매매 중지 요청됨. 거래 내역 저장 완료.")

    def set_telegram_callback(self, callback):
        self.telegram_callback = callback

# ------------- GUI 클래스 -------------
class BinanceFuturesGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("바이낸스 선물 자동매매 봇")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both')
        self.btc_frame = tk.Frame(self.notebook)
        self.eth_frame = tk.Frame(self.notebook)
        self.notebook.add(self.btc_frame, text="BTC 거래")
        self.notebook.add(self.eth_frame, text="ETH 거래")
        self.btc_gui = SingleCoinGUI(self.btc_frame, "BTCUSDT")
        self.eth_gui = SingleCoinGUI(self.eth_frame, "ETHUSDT")

class SingleCoinGUI:
    def __init__(self, parent, default_symbol):
        self.parent = parent
        self.bot = None
        self.bot_thread = None
        self.symbol = tk.StringVar(value=default_symbol)
        self.leverage = tk.IntVar(value=15)
        self.max_daily_loss = tk.DoubleVar(value=20.0)
        self.first_target_profit = tk.DoubleVar(value=11.0)
        self.second_target_profit = tk.DoubleVar(value=22.0)
        self.trailing_stop = tk.DoubleVar(value=15.0)
        self._setup_ui()

    def _setup_ui(self):
        top_frame = tk.Frame(self.parent, padx=10, pady=10)
        top_frame.pack(fill=tk.X)
        api_frame = tk.LabelFrame(top_frame, text="API 설정", padx=10, pady=10)
        api_frame.pack(fill=tk.X)
        tk.Label(api_frame, text="환경 설정 파일 경로:").grid(row=0, column=0, sticky=tk.W)
        self.env_path = tk.StringVar(value=".env")
        tk.Entry(api_frame, textvariable=self.env_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        settings_frame = tk.LabelFrame(top_frame, text="거래 설정", padx=10, pady=10)
        settings_frame.pack(fill=tk.X, pady=10)
        tk.Label(settings_frame, text="심볼:").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(settings_frame, textvariable=self.symbol, width=15).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(settings_frame, text="레버리지:").grid(row=0, column=2, sticky=tk.W)
        tk.Spinbox(settings_frame, from_=1, to=125, textvariable=self.leverage, width=5).grid(row=0, column=3, padx=5, pady=5)
        tk.Label(settings_frame, text="최대 일일 손실(%):").grid(row=1, column=0, sticky=tk.W)
        tk.Spinbox(settings_frame, from_=1, to=20, increment=0.5, textvariable=self.max_daily_loss, width=5).grid(row=1, column=1, padx=5, pady=5)
        tk.Label(settings_frame, text="1차 목표수익(%):").grid(row=2, column=0, sticky=tk.W)
        tk.Spinbox(settings_frame, from_=1, to=100, increment=0.5, textvariable=self.first_target_profit, width=5).grid(row=2, column=1, padx=5, pady=5)
        tk.Label(settings_frame, text="2차 목표수익(%):").grid(row=2, column=2, sticky=tk.W)
        tk.Spinbox(settings_frame, from_=1, to=100, increment=0.5, textvariable=self.second_target_profit, width=5).grid(row=2, column=3, padx=5, pady=5)
        tk.Label(settings_frame, text="트레일링 스탑(%):").grid(row=3, column=0, sticky=tk.W)
        tk.Spinbox(settings_frame, from_=5, to=50, increment=0.5, textvariable=self.trailing_stop, width=5).grid(row=3, column=1, padx=5, pady=5)
        stats_frame = tk.LabelFrame(top_frame, text="일일 통계", padx=10, pady=10)
        stats_frame.pack(fill=tk.X, pady=10)
        self.daily_profit_label = tk.Label(stats_frame, text="일일 손익: 0.00 USDT")
        self.daily_profit_label.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.trades_today_label = tk.Label(stats_frame, text="거래 횟수: 0")
        self.trades_today_label.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.loss_pct_label = tk.Label(stats_frame, text="손실률: 0.00%")
        self.loss_pct_label.grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
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
        log_frame = tk.LabelFrame(self.parent, text="로그", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.status_var = tk.StringVar(value="준비됨")
        status_bar = tk.Label(self.parent, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.active_var = tk.BooleanVar(value=True)
        self.active_check = tk.Checkbutton(self.parent, text="이 코인 감시", variable=self.active_var)
        self.active_check.pack(anchor=tk.W, padx=10, pady=5)

    def add_log(self, message):
        def _update():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.parent.after(0, _update)

    def _update_gui_stats(self):
        if self.bot is None:
            return
        daily_stats = self.bot.daily_stats
        self.daily_profit_label.config(text=f"일일 손익: {daily_stats['profit_today']:.2f} USDT")
        self.trades_today_label.config(text=f"거래 횟수: {daily_stats['trades_today']}")
        loss_pct = (abs(daily_stats["profit_today"]) / daily_stats["start_balance"] * 100 
                    if daily_stats["start_balance"] > 0 else 0.0)
        self.loss_pct_label.config(text=f"손실률: {loss_pct:.2f}%")

    def update_status(self):
        if self.bot and hasattr(self.bot, 'running') and self.bot.running:
            threading.Thread(target=self._update_bot_status, daemon=True).start()

    def _update_bot_status(self):
        try:
            self.bot.update_status()
            self.parent.after(0, self._update_gui_stats)
        except Exception as e:
            self.add_log(f"⚠️ _update_bot_status 오류: {e}")

    def start_bot(self):
        try:
            if self.bot and hasattr(self.bot, 'running') and self.bot.running:
                self.stop_bot()
            env_path = self.env_path.get()
            leverage = self.leverage.get()
            max_daily_loss = self.max_daily_loss.get()
            first_target = self.first_target_profit.get()
            second_target = self.second_target_profit.get()
            trailing_stop = self.trailing_stop.get()
            self.bot = BinanceFuturesBot(env_path, self.symbol.get(), leverage, trailing_stop)
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
            self.add_log(f"⚠️ start_bot 오류: {e}")
            messagebox.showerror("오류", f"봇 시작 중 오류 발생:\n{e}")

    def stop_bot(self):
        if self.bot and hasattr(self.bot, 'running') and self.bot.running:
            self.bot.stop()
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_var.set("중지됨")
            self.add_log("🛑 자동매매 봇 중지됨")

    def request_gpt(self):
        # GPT 보고서는 오직 BTCUSDT 화면에서만 수행 (ETH 화면에서는 실행하지 않음)
        if self.bot and hasattr(self.bot, 'running') and self.bot.running:
            if self.symbol.get().upper() == "BTCUSDT":
                threading.Thread(target=self.bot.generate_gpt_report_with_retry, daemon=True).start()
            else:
                self.add_log("현재 코인(ETH)은 GPT 보고서 대상이 아님.")

def main():
    root = tk.Tk()
    app = BinanceFuturesGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
