import pyupbit
import pandas as pd
import numpy as np
import time
import requests
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class DonwinBot:
    def __init__(self, access, secret, telegram_token, telegram_chat_id):
        self.access = access
        self.secret = secret
        self.upbit = pyupbit.Upbit(access, secret)
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        
        self.symbol = "KRW-BTC"
        # 타임프레임 설정
        self.main_tf = "minute60"     # 1시간봉
        self.aux_tf = "minute240"     # 4시간봉
        self.baseline_tf = "minute15" # 청산 기준용 15분봉
        
        # 지표 파라미터
        self.donchian_period = 20  # 돈치안 채널 계산 기간
        self.lwti_period = 14      # LWTI 계산 기간
        
        # 주문/포지션 관리 변수
        self.entry_price = None
        self.position = 0.0   # 보유 BTC 수량
        self.entry_time = None

    def telegram_report(self, message):
        """텔레그램으로 상태보고 메시지 전송"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {"chat_id": self.telegram_chat_id, "text": message}
        try:
            requests.post(url, data=data)
        except Exception as e:
            logging.error("텔레그램 전송 실패: " + str(e))

    def get_ohlcv(self, interval, count):
        """지정 타임프레임의 캔들 데이터를 반환 (pandas DataFrame)"""
        df = pyupbit.get_ohlcv(self.symbol, interval=interval, count=count)
        if df is None or df.empty:
            logging.info(f"{interval} 데이터 없음")
        return df

    def calculate_donchian(self, df):
        """돈치안 채널 계산: 상단, 하단, 중간선을 반환"""
        upper = df['high'].rolling(self.donchian_period).max().iloc[-1]
        lower = df['low'].rolling(self.donchian_period).min().iloc[-1]
        middle = (upper + lower) / 2
        return upper, lower, middle

    def calculate_lwti(self, df):
        """
        LWTI 계산 (기본 공식 예시):
        LWTI = 50 + ((현재 종가 - 단순이동평균) / 표준편차) * 10
        """
        ma = df['close'].rolling(self.lwti_period).mean().iloc[-1]
        std = df['close'].rolling(self.lwti_period).std().iloc[-1]
        current_close = df['close'].iloc[-1]
        if std == 0:
            return 50
        lwti = 50 + ((current_close - ma) / std) * 10
        return lwti

    def check_entry_signal(self):
        """
        진입 신호 확인
        - 1시간봉 돈치안 채널 상단 돌파 (현재 종가 > 상단)
        - 동시에 4시간봉 LWTI가 50 이상 (상승 모멘텀 확인)
        """
        df_main = self.get_ohlcv(self.main_tf, self.donchian_period + 10)
        if df_main is None:
            return False, None, None
        upper, lower, _ = self.calculate_donchian(df_main)
        current_price = df_main['close'].iloc[-1]
        logging.info(f"1시간봉 현재가: {current_price}, 상단: {upper}")
        if current_price > upper:
            df_aux = self.get_ohlcv(self.aux_tf, self.lwti_period + 10)
            if df_aux is None:
                return False, current_price, None
            lwti_aux = self.calculate_lwti(df_aux)
            logging.info(f"4시간봉 LWTI: {lwti_aux}")
            if lwti_aux > 50:
                return True, current_price, lwti_aux
        return False, current_price, None

    def get_account_balance(self):
        """업비트 계좌에서 KRW 잔고를 반환"""
        balances = self.upbit.get_balances()
        for b in balances:
            if b['currency'] == "KRW":
                return float(b['balance'])
        return 0.0

    def execute_entry(self):
        """
        진입 실행:
        - 계좌 잔고의 50%를 사용해 시장가 매수 주문 실행
        - 주문 체결 후 진입 가격 및 포지션 업데이트
        """
        balance = self.get_account_balance()
        if balance <= 0:
            logging.info("KRW 잔고 없음.")
            return
        entry_amount = balance * 0.5
        logging.info(f"진입 금액: {entry_amount} KRW")
        order = self.upbit.buy_market_order(self.symbol, entry_amount)
        logging.info(f"매수 주문 실행: {order}")
        self.telegram_report(f"매수 주문 실행: {order}")
        # 주문 체결 가격은 주문 결과에 포함된 경우 사용 (예시)
        self.entry_price = order.get('price', None)
        self.entry_time = datetime.now()
        # BTC 잔고 업데이트
        balances = self.upbit.get_balances()
        for b in balances:
            if b['currency'] == "BTC":
                self.position = float(b['balance'])
                break

    def check_exit_conditions(self):
        """
        청산 조건 확인:
        1. 부분 청산 기준: 15분봉 기준선(돈치안 중간선) 도달 시
        2. 추가 청산 기준: 진입가 대비 +5% 상승 시
        3. LWTI 과열: 1시간봉 LWTI가 70 이상 (롱) 시 전량 청산
        4. 손절: 진입가 대비 -2% 하락하며, LWTI가 50 미만으로 하락하면 전량 청산
        """
        df_main = self.get_ohlcv(self.main_tf, 10)
        if df_main is None:
            return None
        current_price = df_main['close'].iloc[-1]
        df_baseline = self.get_ohlcv(self.baseline_tf, self.donchian_period + 10)
        if df_baseline is None:
            return None
        _, _, baseline = self.calculate_donchian(df_baseline)
        if self.entry_price is None:
            return None
        pct_change = (current_price - self.entry_price) / self.entry_price * 100
        logging.info(f"진입가: {self.entry_price}, 현재가: {current_price}, 변동율: {pct_change:.2f}%")
        lwti_main = self.calculate_lwti(df_main)
        exit_signal = None
        # 부분 청산 조건: 가격이 기준선(15분봉 중간선) 이상 도달하면
        if current_price >= baseline:
            exit_signal = "partial_baseline"
        # 추가 청산: 진입가 대비 +5% 이상 상승 시
        if pct_change >= 5:
            exit_signal = "partial_target"
        # LWTI 과열: LWTI가 70 이상이면 전량 청산
        if lwti_main >= 70:
            exit_signal = "lwti_overheat"
        # 손절 조건: 진입가 대비 -2% 하락 및 LWTI가 50 미만이면 전량 청산
        if pct_change <= -2 and lwti_main < 50:
            exit_signal = "stop_loss"
        return exit_signal

    def execute_exit(self, exit_signal):
        """
        청산 실행:
        - 부분 청산: 보유 포지션의 50%를 시장가 매도
        - 전량 청산: 보유 포지션 전부를 시장가 매도
        """
        if self.position <= 0:
            return
        if exit_signal in ["partial_baseline", "partial_target"]:
            sell_amount = self.position * 0.5
            order = self.upbit.sell_market_order(self.symbol, sell_amount)
            logging.info(f"부분 청산 주문 실행: {order}")
            self.telegram_report(f"부분 청산 주문 실행: {order}")
            self.position -= sell_amount
        elif exit_signal in ["lwti_overheat", "stop_loss"]:
            order = self.upbit.sell_market_order(self.symbol, self.position)
            logging.info(f"전량 청산 주문 실행: {order}")
            self.telegram_report(f"전량 청산 주문 실행: {order}")
            self.position = 0.0
            self.entry_price = None
            self.entry_time = None

    def run(self):
        """메인 실행 루프: 1분 간격으로 진입/청산 조건을 확인하고 주문 실행"""
        while True:
            try:
                if self.position <= 0:
                    signal, current_price, lwti_aux = self.check_entry_signal()
                    if signal:
                        logging.info("진입 신호 감지됨. 매수 실행합니다.")
                        self.execute_entry()
                    else:
                        logging.info("진입 조건 미충족. 대기 중...")
                else:
                    exit_signal = self.check_exit_conditions()
                    if exit_signal:
                        logging.info(f"청산 조건 충족: {exit_signal}")
                        self.execute_exit(exit_signal)
                    else:
                        logging.info("청산 조건 미충족. 포지션 유지 중...")
                time.sleep(60)
            except Exception as e:
                logging.error(f"메인 루프 에러: {e}")
                self.telegram_report(f"에러 발생: {e}")
                time.sleep(60)

if __name__ == "__main__":
    # 본인의 업비트 API 키 및 텔레그램 정보를 입력하세요.
    ACCESS_KEY = "YOUR_UPBIT_ACCESS_KEY"
    SECRET_KEY = "YOUR_UPBIT_SECRET_KEY"
    TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"
    
    bot = DonwinBot(ACCESS_KEY, SECRET_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    bot.run()
