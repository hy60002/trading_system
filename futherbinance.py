#!/usr/bin/env python3
import os
import sys
import time
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
import pandas as pd
import numpy as np
import requests
import logging
import json
import uuid
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceRequestException
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

# ─────────────────────────────────────────────────────────────
# 로깅 설정: 로그는 log.txt 파일과 콘솔에 기록됩니다.
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("log.txt", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("futherbinance")

# ─────────────────────────────────────────────────────────────
# [트레이딩 봇 클래스]
# EC2나 항상 켜진 서버에서 백그라운드로 실행하여 24시간 자동매매 및
# 텔레그램 메시지, GPT 분석(설정된 API를 이용) 등을 처리합니다.
# ─────────────────────────────────────────────────────────────
class FutherbinanceBot:
    def __init__(self, env_path: str = ".env", symbol: str = "BTCUSDT", leverage: int = 10):
        # config.json 파일이 존재하면 그 값으로 초기화, 없으면 기본값을 config.json에 저장
        self.config_file = "config.json"
        if os.path.exists(self.config_file):
            self.load_config()
        else:
            default_config = {
                "env_path": env_path,
                "symbol": symbol,
                "leverage": leverage,
                "max_daily_loss_pct": 20.0,
                "first_target_profit_pct": 11.0,
                "second_target_profit_pct": 22.0
            }
            with open(self.config_file, "w") as f:
                json.dump(default_config, f, indent=4)
            self.env_path = env_path
            self.symbol = symbol
            self.leverage = leverage
            self.max_daily_loss_pct = 20.0
            self.first_target_profit_pct = 11.0
            self.second_target_profit_pct = 22.0

        self.active_trades = []
        self.buy_setup_triggered = False
        self.baseline_william = None
        self.last_gpt_report_time = 0
        self.gpt_report_interval = 7200  # 2시간 (초 단위)
        self.last_status_update_time = 0
        self.status_update_interval = 900  # 15분 (초 단위)
        self.running = False
        self.last_df = None
        self.last_price = None
        self.telegram_rate_limit = {"count": 0, "reset_time": time.time() + 60}
        self.telegram_max_rate = 20
        self.trade_lock = threading.Lock()  # 거래 관련 락
        self.data_lock = threading.Lock()   # 데이터 관련 락

        self.daily_stats = {
            "start_balance": 0.0,
            "current_balance": 0.0,
            "trades_today": 0,
            "profit_today": 0.0,
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        self.trade_history = []  # 거래 히스토리 저장 리스트
        self.KST = pytz.timezone('Asia/Seoul')  # 한국 시간대

        # 환경변수 로드 (.env 파일)
        self._load_env(self.env_path)
        self._init_client()
        self._load_trades()
        self._init_daily_stats()

        self.log("✅ 프로그램 초기화 완료. 최초 GPT 보고서 요청 중...")
        self.generate_gpt_report_with_retry()

    def load_config(self):
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
            self.env_path = config.get("env_path", ".env")
            self.symbol = config.get("symbol", "BTCUSDT")
            self.leverage = config.get("leverage", 10)
            self.max_daily_loss_pct = config.get("max_daily_loss_pct", 20.0)
            self.first_target_profit_pct = config.get("first_target_profit_pct", 11.0)
            self.second_target_profit_pct = config.get("second_target_profit_pct", 22.0)
            self.log("✅ config.json 로드 완료")
        except Exception as e:
            self.log(f"⚠️ config.json 로드 오류: {e}")

    def log(self, message: str):
        logger.info(message)
        print(message)
        self._rate_limited_telegram(message)
        if hasattr(self, 'telegram_callback') and callable(self.telegram_callback):
            try:
                if self.gui_is_alive():
                    self.telegram_callback(f"[로그] {message}")
            except Exception:
                pass

    def gui_is_alive(self):
        try:
            if hasattr(self, 'telegram_callback') and hasattr(self.telegram_callback, '__self__'):
                widget = self.telegram_callback.__self__
                if hasattr(widget, 'winfo_exists'):
                    return widget.winfo_exists()
            return True
        except Exception:
            return True

    def _rate_limited_telegram(self, message: str):
        if not (hasattr(self, "TELEGRAM_BOT_TOKEN") and hasattr(self, "TELEGRAM_CHAT_ID") and self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID):
            return
        current_time = time.time()
        if current_time > self.telegram_rate_limit["reset_time"]:
            self.telegram_rate_limit = {"count": 0, "reset_time": current_time + 60}
        if self.telegram_rate_limit["count"] >= self.telegram_max_rate:
            logger.warning("텔레그램 메시지 속도 제한 도달, 메시지 전송 건너뜀")
            return
        self.telegram_rate_limit["count"] += 1
        self.send_telegram_message(message)

    def send_telegram_message(self, message: str, retry=3):
        if not (hasattr(self, "TELEGRAM_BOT_TOKEN") and hasattr(self, "TELEGRAM_CHAT_ID") and self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID):
            return
        url = f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": self.TELEGRAM_CHAT_ID, "text": message}
        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code != 200:
                raise Exception(f"Telegram API 응답 코드: {response.status_code}, 내용: {response.text}")
        except Exception as e:
            logger.error(f"Telegram 전송 오류: {e}")
            if retry > 0:
                time.sleep(2)
                self.send_telegram_message(message, retry - 1)

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
                    self.log("⚠️ 마진 타입이 이미 CROSSED로 설정되어 있습니다. 변경할 필요가 없습니다.")
                else:
                    raise
            self.log(f"✅ 바이낸스 선물 API 연결 및 레버리지 {self.leverage}배 설정 완료")
        except BinanceAPIException as e:
            self.log(f"⚠️ 바이낸스 API 오류: {e}")
            raise
        except BinanceRequestException as e:
            self.log(f"⚠️ 바이낸스 요청 오류: {e}")
            raise
        except Exception as e:
            self.log(f"⚠️ 바이낸스 API 연결/레버리지 설정 실패: {e}")
            raise

    def _load_trades(self):
        try:
            if os.path.exists("active_trades.json"):
                with open("active_trades.json", "r") as f:
                    self.active_trades = json.load(f)
                self.log(f"✅ 기존 거래 내역 로드 완료: {len(self.active_trades)}개")
        except Exception as e:
            self.log(f"⚠️ 거래 내역 로드 실패: {e}")
            self.active_trades = []

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
        today = datetime.now().strftime("%Y-%m-%d")
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
        except Exception as e:
            self.log(f"⚠️ 잔고 조회 오류: {e}")
            return 0.0

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
                    "time", "open", "high", "low", "close", "volume", "close_time",
                    "quote_asset_volume", "trades", "taker_base", "taker_quote", "ignore"
                ])
                from datetime import timezone
                df["time"] = pd.to_datetime(df["time"], unit='ms', utc=True)
                df["close_time"] = pd.to_datetime(df["close_time"], unit='ms', utc=True)
                df["open"] = df["open"].astype(float)
                df["close"] = df["close"].astype(float)
                df["high"] = df["high"].astype(float)
                df["low"] = df["low"].astype(float)
                df["volume"] = df["volume"].astype(float)
                latest_candle_time = df["close_time"].iloc[-1]
                current_time = datetime.now(timezone.utc)
                if (current_time - latest_candle_time).total_seconds() > 900:
                    self.log(f"⚠️ 데이터가 최신이 아닙니다. 마지막 캔들 시간: {latest_candle_time}")
                delta = df["close"].diff()
                gain = delta.copy()
                loss = delta.copy()
                gain[gain < 0] = 0
                loss[loss > 0] = 0
                loss = abs(loss)
                avg_gain = gain.rolling(window=14).mean()
                avg_loss = loss.rolling(window=14).mean()
                rs = avg_gain / avg_loss
                df["rsi"] = 100 - (100 / (1 + rs))
                high14 = df["high"].rolling(window=14).max()
                low14 = df["low"].rolling(window=14).min()
                df["william"] = (high14 - df["close"]) / (high14 - low14) * -100
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
        except BinanceAPIException as e:
            self.log(f"⚠️ 바이낸스 API 오류 (get_data): {e}")
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
                max_attempts = 20
                for i in range(max_attempts):
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
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                    if i < max_attempts - 1:
                        time.sleep(0.5)
                self.log(f"⚠️ 주문 체결 확인 시간 초과. 주문 ID: {order_id}")
                return None
        except BinanceAPIException as e:
            self.log(f"⚠️ 바이낸스 API 오류 (매수): {e}")
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
                max_attempts = 20
                for i in range(max_attempts):
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
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                    if i < max_attempts - 1:
                        time.sleep(0.5)
                self.log(f"⚠️ 주문 체결 확인 시간 초과. 주문 ID: {order_id}")
                return None
        except BinanceAPIException as e:
            self.log(f"⚠️ 바이낸스 API 오류 (매도): {e}")
            return None
        except Exception as e:
            self.log(f"⚠️ 매도 주문 실패: {e}")
            return None

    def get_market_news(self):
        try:
            news = "최근 시장은 변동성이 높으며, 글로벌 경제 지표와 뉴스에 따라 BTC 가격에 영향을 주고 있습니다."
            return news
        except Exception as e:
            self.log(f"⚠️ 시장 뉴스 가져오기 실패: {e}")
            return "뉴스 데이터를 가져오는 데 실패했습니다."

    # 매수 조건 체크 함수
    def check_conditions(self, df):
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

    # 자동매매 실행 루프
    def execute_trade(self):
        self.running = True
        self._init_daily_stats()
        self.log(f"✅ 자동매매 시작: 심볼={self.symbol}, 레버리지={self.leverage}배")
        self.log(f"📊 리스크 관리: 일일 최대 손실={self.max_daily_loss_pct}%")
        last_check_time = 0
        check_interval = 60  # 60초 주기
        while self.running:
            try:
                current_time = time.time()
                if current_time - last_check_time < check_interval:
                    time.sleep(1)
                    continue
                last_check_time = current_time
                today = datetime.now().strftime("%Y-%m-%d")
                if self.daily_stats["date"] != today:
                    self._init_daily_stats()
                df = self.get_data()
                if df is None or len(df) < 14:
                    self.log("⚠️ 충분한 시장 데이터를 가져오지 못했습니다. 1분 후 재시도합니다.")
                    time.sleep(60)
                    continue
                ticker = self.client.futures_symbol_ticker(symbol=self.symbol)
                self.last_price = float(ticker["price"])
                self.last_df = df
                self.manage_active_trades()
                # 매수 조건 판단
                if self.buy_setup_triggered:
                    if df["william"].iloc[-1] <= self.baseline_william or df["william"].iloc[-1] <= -90:
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
                                self.buy_setup_triggered = False
                                self.baseline_william = None
                            else:
                                self.log("⚠️ 매수 주문이 체결되지 않았습니다. 재시도합니다.")
                else:
                    should_buy, baseline = self.check_conditions(df)
                    if should_buy:
                        self.buy_setup_triggered = True
                        self.baseline_william = baseline
                        self.log(f"⚡ 매수 조건 감지! 기준선: {baseline:.2f}")
                if time.time() - self.last_status_update_time > self.status_update_interval:
                    self.update_status()
                    self.last_status_update_time = time.time()
                if time.time() - self.last_gpt_report_time > self.gpt_report_interval:
                    self.generate_gpt_report_with_retry()
                    self.last_gpt_report_time = time.time()
            except BinanceAPIException as e:
                self.log(f"⚠️ 바이낸스 API 오류: {e}")
                time.sleep(30)
            except Exception as e:
                self.log(f"⚠️ 거래 실행 중 오류 발생: {e}")
                time.sleep(30)
        self.log("❌ 자동매매 종료됨")

    # 활성 거래 관리
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
                if trade.get("sell_stage", 0) == 0 and current_price >= entry_price * (1 + self.first_target_profit_pct / 100):
                    sell_qty = trade["remaining_quantity"] / 2
                    sell_order = self.safe_sell(sell_qty)
                    if sell_order:
                        trade["first_sell"] = sell_order
                        trade["sell_stage"] = 1
                        trade["remaining_quantity"] -= sell_qty
                        self.log(f"💰 {self.first_target_profit_pct}% 목표 달성: 절반 매도, 남은 수량: {trade['remaining_quantity']} BTC")
                elif trade.get("sell_stage", 0) == 1 and current_price >= entry_price * (1 + self.second_target_profit_pct / 100):
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

    # 최근 2시간 거래 데이터 분석 함수
    def analyze_trade_data(self):
        try:
            if len(self.trade_history) == 0:
                return "⚠️ 거래 내역이 없습니다."
            df = pd.DataFrame(self.trade_history)
            if df.empty:
                return "⚠️ 최근 2시간 동안 거래가 없습니다."
            if "entry_time" in df.columns:
                df["entry_time"] = pd.to_datetime(df["entry_time"])
            last_2_hours = datetime.now() - timedelta(hours=2)
            df_recent = df[df["entry_time"] > last_2_hours]
            total_trades = len(df_recent)
            if total_trades == 0:
                return "⚠️ 최근 2시간 동안 거래가 없습니다."
            win_trades = len(df_recent[df_recent["profit_pct"] > 0])
            lose_trades = len(df_recent[df_recent["profit_pct"] < 0])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            avg_profit = df_recent["profit_pct"].mean() if total_trades > 0 else 0
            summary = f"""
📊 최근 2시간 매매 요약
- 총 거래 횟수: {total_trades}
- 승리 횟수: {win_trades}
- 패배 횟수: {lose_trades}
- 승률: {win_rate:.2f}%
- 평균 손익: {avg_profit:.3f}%
"""
            return summary.strip()
        except Exception as e:
            return f"⚠️ 거래 데이터 분석 오류: {e}"

    def update_status(self):
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                account = self.client.futures_account()
                balance = float(next((asset.get("walletBalance", 0) for asset in account.get("assets", []) if asset.get("asset") == "USDT"), 0))
                available_balance = float(next((asset.get("availableBalance", 0) for asset in account.get("assets", []) if asset.get("asset") == "USDT"), 0))
                unrealized_pnl = float(next((asset["unrealizedProfit"] for asset in account["assets"] if asset["asset"] == "USDT"), 0))
                positions = account["positions"]
                btc_position = next((pos for pos in positions if pos["symbol"] == self.symbol), None)
                position_size = 0
                leverage = self.leverage
                entry_price = 0
                if btc_position:
                    position_size = float(btc_position["positionAmt"])
                    leverage = int(btc_position["leverage"])
                    entry_price = float(btc_position["entryPrice"])
                status_message = f"""
📊 상태 업데이트 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
----------------------------
💰 계정 잔고: {balance:.2f} USDT
💵 사용 가능 잔고: {available_balance:.2f} USDT
📈 미실현 손익: {unrealized_pnl:.2f} USDT
🔄 포지션: {position_size} BTC
⚙️ 레버리지: {leverage}배
💵 진입가: {entry_price:.2f} USDT
💹 현재가: {self.last_price:.2f} USDT
----------------------------
📉 일일 성과:
    시작 잔고: {self.daily_stats["start_balance"]:.2f} USDT
    현재 잔고: {self.daily_stats["current_balance"]:.2f} USDT
    거래 횟수: {self.daily_stats["trades_today"]}
    손익: {self.daily_stats["profit_today"]:.2f} USDT
    수익률: {(self.daily_stats["profit_today"] / self.daily_stats["start_balance"] * 100) if self.daily_stats["start_balance"] > 0 else 0:.2f}%
----------------------------
                """
                candle_info = ""
                if self.last_df is not None and len(self.last_df) >= 3:
                    last_three = self.last_df.tail(3)
                    candle_info += "🔍 최근 3개 15분봉 지표:\n"
                    for idx, row in last_three.iterrows():
                        candle_info += f"  - {row['time'].strftime('%Y-%m-%d %H:%M:%S')}: RSI {row['rsi']:.2f}, 윌리엄 %R {row['william']:.2f}\n"
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

    def generate_gpt_report_with_retry(self, max_retries=3):
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
            try:
                now = datetime.now(self.KST).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
            recent_candles = df.iloc[-5:][
                ["time", "open", "high", "low", "close", "volume", "rsi", "william"]
            ].to_dict('records')
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
                    candle_info += f"  - {candle_time}: RSI {row['rsi']:.2f}, 윌리엄 %R {row['william']:.2f}\n"
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
            positions_info = ""
            account = self.client.futures_account()
            positions = account["positions"]
            btc_position = next((pos for pos in positions if pos["symbol"] == self.symbol), None)
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
                            f"\n+아래 데이터를 기반으로, 트레이딩 전략을 평가하고 개선점을 제안하는 트레이딩 분석가 역할을 수행합니다. 매매 전략을 자동으로 변경하지 말고, 조언과 제안만 제공합니다.\n"
                            f"\n+현재 매매 전략:\n"
                            f"+1. RSI와 윌리엄 %R을 사용하여 매수 신호를 확인합니다.\n"
                            f"+2. RSI가 35 이하, 윌리엄 %R이 -70 이하일 때 매수 가능성이 있습니다.\n"
                            f"+3. RSI는 3개의 캔들을 비교하여 감소하는 패턴을 찾습니다.\n"
                            f"+4. 윌리엄 %R은 2개의 캔들을 비교하여 특정 패턴을 찾습니다.\n"
                            f"+5. 위 조건이 충족되고, 윌리엄%R이 이전에 설정된 기준선을 돌파하거나 -90이하로 떨어진다면, 매수를 진행합니다.\n"
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
            response = requests.post(
                self.GPT_API_URL,
                headers=headers,
                data=json.dumps(request_data),
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                analysis = result.get("choices", [{}])[0].get("message", {}).get("content", "분석 결과를 받지 못했습니다.")
                report = (
                    f"🧠 GPT 시장 분석 보고서 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n"
                    "---------------------------------------------------\n"
                    f"{analysis}\n"
                    "---------------------------------------------------"
                )
                self.log(report)
                return report
            elif response.status_code == 403:
                self.log("⚠️ GPT API 403 오류: 권한이 없거나 API 키가 올바르지 않습니다.")
                return None
            else:
                self.log(f"⚠️ GPT API 오류: HTTP {response.status_code}, {response.text}")
                return None
        except Exception as e:
            self.log(f"⚠️ GPT 보고서 생성 중 오류 발생: {e}")
            return None

    def stop(self):
        self.running = False
        self.log("🛑 자동매매 중지 요청 처리됨")

    def set_telegram_callback(self, callback):
        self.telegram_callback = callback

# ─────────────────────────────────────────────────────────────
# [GUI 클래스]
# GUI는 log.txt와 config.json을 읽어와 설정 편집 및 로그 모니터링을 제공합니다.
# ─────────────────────────────────────────────────────────────
class FutherbinanceGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("futherbinance - EC2 매매 데이터 및 설정 확인")
        self.root.geometry("900x600")
        self.root.resizable(True, True)
        self._setup_ui()
        self.load_config()

    def _setup_ui(self):
        # 로그 표시 영역
        log_frame = tk.LabelFrame(self.root, text="EC2 매매 로그 (log.txt)", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        refresh_button = tk.Button(self.root, text="로그 새로고침", command=self.refresh_log, width=15)
        refresh_button.pack(pady=5)
        # 설정 편집 영역
        config_frame = tk.LabelFrame(self.root, text="설정 (config.json)", padx=10, pady=10)
        config_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(config_frame, text="환경 설정 파일 경로:").grid(row=0, column=0, sticky=tk.W)
        self.env_path_var = tk.StringVar()
        tk.Entry(config_frame, textvariable=self.env_path_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(config_frame, text="심볼:").grid(row=1, column=0, sticky=tk.W)
        self.symbol_var = tk.StringVar()
        tk.Entry(config_frame, textvariable=self.symbol_var, width=15).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        tk.Label(config_frame, text="레버리지:").grid(row=1, column=2, sticky=tk.W)
        self.leverage_var = tk.IntVar()
        tk.Spinbox(config_frame, from_=1, to=125, textvariable=self.leverage_var, width=5).grid(row=1, column=3, padx=5, pady=5, sticky=tk.W)
        
        tk.Label(config_frame, text="최대 일일 손실(%):").grid(row=2, column=0, sticky=tk.W)
        self.max_daily_loss_var = tk.DoubleVar()
        tk.Spinbox(config_frame, from_=1, to=100, increment=0.5, textvariable=self.max_daily_loss_var, width=5).grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        tk.Label(config_frame, text="1차 목표수익(%):").grid(row=2, column=2, sticky=tk.W)
        self.first_target_profit_var = tk.DoubleVar()
        tk.Spinbox(config_frame, from_=1, to=100, increment=0.5, textvariable=self.first_target_profit_var, width=5).grid(row=2, column=3, padx=5, pady=5, sticky=tk.W)
        
        tk.Label(config_frame, text="2차 목표수익(%):").grid(row=3, column=0, sticky=tk.W)
        self.second_target_profit_var = tk.DoubleVar()
        tk.Spinbox(config_frame, from_=1, to=100, increment=0.5, textvariable=self.second_target_profit_var, width=5).grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        
        load_button = tk.Button(config_frame, text="설정 불러오기", command=self.load_config, width=15)
        load_button.grid(row=4, column=0, padx=5, pady=5)
        save_button = tk.Button(config_frame, text="설정 저장", command=self.save_config, width=15)
        save_button.grid(row=4, column=1, padx=5, pady=5)

    def refresh_log(self):
        try:
            if os.path.exists("log.txt"):
                with open("log.txt", "r", encoding="utf-8") as f:
                    content = f.read()
                self.log_text.configure(state=tk.NORMAL)
                self.log_text.delete("1.0", tk.END)
                self.log_text.insert(tk.END, content)
                self.log_text.see(tk.END)
                self.log_text.configure(state=tk.DISABLED)
            else:
                messagebox.showwarning("경고", "log.txt 파일을 찾을 수 없습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"로그 불러오기 중 오류 발생:\n{e}")

    def load_config(self):
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.env_path_var.set(config.get("env_path", ".env"))
                self.symbol_var.set(config.get("symbol", "BTCUSDT"))
                self.leverage_var.set(config.get("leverage", 10))
                self.max_daily_loss_var.set(config.get("max_daily_loss_pct", 20.0))
                self.first_target_profit_var.set(config.get("first_target_profit_pct", 11.0))
                self.second_target_profit_var.set(config.get("second_target_profit_pct", 22.0))
                messagebox.showinfo("정보", "설정을 성공적으로 불러왔습니다.")
            else:
                messagebox.showwarning("경고", "config.json 파일이 존재하지 않습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"설정 불러오기 중 오류 발생:\n{e}")

    def save_config(self):
        try:
            config = {
                "env_path": self.env_path_var.get(),
                "symbol": self.symbol_var.get(),
                "leverage": self.leverage_var.get(),
                "max_daily_loss_pct": self.max_daily_loss_var.get(),
                "first_target_profit_pct": self.first_target_profit_var.get(),
                "second_target_profit_pct": self.second_target_profit_var.get()
            }
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            messagebox.showinfo("정보", "설정을 성공적으로 저장했습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 중 오류 발생:\n{e}")

# ─────────────────────────────────────────────────────────────
# Main 함수: 트레이딩 봇을 백그라운드 스레드에서 실행하고, 동시에 GUI를 실행합니다.
# ─────────────────────────────────────────────────────────────
def main():
    # 트레이딩 봇을 백그라운드 스레드로 시작합니다.
    bot = FutherbinanceBot()
    trading_thread = threading.Thread(target=bot.execute_trade)
    trading_thread.daemon = True
    trading_thread.start()
    
    # GUI는 메인 스레드에서 실행되어 log.txt 및 config.json을 확인하고 편집할 수 있습니다.
    root = tk.Tk()
    app = FutherbinanceGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
