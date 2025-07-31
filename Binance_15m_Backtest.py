import os
import time
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import logging
from binance.client import Client
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def fetch_and_save_data(filename, start_date, end_date, max_retries=3, retry_delay=5):
    """
    Binance API를 통해 지정된 기간(start_date ~ end_date)의 15분봉 데이터를 받아 CSV 파일에 저장합니다.
    날짜 형식은 "YYYY-MM-DD"로 입력합니다.
    """
    load_dotenv()  # .env 파일에서 API 키 불러오기
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_SECRET_KEY")
    if not API_KEY or not API_SECRET:
        logger.error("Binance API 키/SECRET이 설정되지 않았습니다.")
        raise ValueError("Binance API 키/SECRET이 설정되지 않았습니다.")
    
    client = Client(API_KEY, API_SECRET)
    
    # 시작, 종료 날짜를 밀리초 단위로 변환
    start_ts = int(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
    
    retries = 0
    klines = None
    while retries < max_retries:
        try:
            klines = client.futures_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_15MINUTE, start_str=start_ts, end_str=end_ts)
            if klines and len(klines) > 0:
                break
            else:
                logger.warning("Binance API로부터 데이터가 반환되지 않았습니다. 재시도합니다...")
                retries += 1
                time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"데이터 가져오기 오류: {e}")
            retries += 1
            time.sleep(retry_delay)
    
    if klines is None or len(klines) == 0:
        raise ValueError("Binance API로부터 데이터를 가져오지 못했습니다.")
    
    # DataFrame 생성 (필요한 컬럼: time, open, high, low, close, volume)
    df = pd.DataFrame(klines, columns=["time", "open", "high", "low", "close", "volume",
                                         "close_time", "quote_asset_volume", "trades", "taker_base", "taker_quote", "ignore"])
    df = df[["time", "open", "high", "low", "close", "volume"]]
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df.to_csv(filename, index=False)
    logger.info(f"✅ 데이터를 {filename}에 저장 완료!")
    return df

def calculate_indicators(df):
    """
    RSI와 William %R 지표를 14기간 기준으로 계산합니다.
    """
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    
    # RSI 계산
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # William %R 계산
    highest_high = df["high"].rolling(window=14).max()
    lowest_low = df["low"].rolling(window=14).min()
    df["william"] = (highest_high - df["close"]) / (highest_high - lowest_low) * -100
    
    return df

def backtest_strategy(df, initial_capital=10000.0, trade_unit=100.0, leverage=10):
    """
    전략 백테스트:
    - 매수 조건: 최근 3봉 기준 (rsi2 ≤ 35, william2 ≤ -75, rsi0 > rsi1 > rsi2, will0 > will1 and will1 < will2)
      시 buy setup으로 기준봉(will1)을 설정하고, 이후 현재의 william2가 기준보다 낮으면 trade_unit 달러 어치 매수.
    - 매도 조건:
      * Partial Sell: 아직 partial sell이 되지 않은 경우, 진입가 대비 레버리지 적용 후 +10% 이상이면 보유량의 50%를 매도하고 sell_label을 "sell1"로 기록.
      * Full Sell: 이미 partial sell한 상태에서 진입가 대비 레버리지 적용 후 +16% 이상이면 남은 포지션 전량 매도하고 sell_label을 "sell2"로 기록.
      * Stop Loss: 진입가 대비 레버리지 적용 후 -100% 이하이면 전량 청산하며 sell_label은 "stop_loss_sell".
      
    각 거래별로 매수일시, 매수금액, 매도일시, 수익률, 매수 라벨(buy_label)과 매도 라벨(sell_label)을 기록합니다.
    """
    capital = initial_capital
    equity_curve = []
    open_trades = []   # 미청산 매수건
    closed_trades = [] # 최종 청산된 거래
    buy_setup_triggered = False
    baseline_william = None
    buy_counter = 0  # 매수 건수를 위한 카운터
    
    for i in range(2, len(df)):
        current = df.iloc[i]
        prev1 = df.iloc[i-1]
        prev2 = df.iloc[i-2]
        
        # 현재 캔들의 시간
        current_time = current["time"]
        
        # 최근 3봉의 RSI와 William %R 추출
        rsi0, rsi1, rsi2 = prev2["rsi"], prev1["rsi"], current["rsi"]
        will0, will1, will2 = prev2["william"], prev1["william"], current["william"]
        
        # 매수 조건: william2 ≤ -75 로 수정
        if (rsi2 <= 35 and will2 <= -75 and (rsi0 > rsi1 > rsi2) and (will0 > will1 and will1 < will2)):
            if not buy_setup_triggered:
                baseline_william = will1
                buy_setup_triggered = True
        
        # 매수 실행: 기준봉 설정 후 현재 william2가 기준보다 낮으면 매수
        if buy_setup_triggered and (will2 < baseline_william):
            if capital >= trade_unit:
                entry_price = current["close"]
                buy_time = current["time"]
                amount = trade_unit / entry_price  # 100달러 어치 BTC 수량
                buy_counter += 1
                open_trades.append({
                    "buy_index": i,
                    "buy_time": buy_time,
                    "buy_price": entry_price,
                    "investment": trade_unit,
                    "amount": amount,
                    "realized_return": 0.0,
                    "partial_sold": False,
                    "buy_label": f"buy{buy_counter}"
                })
                capital -= trade_unit
            buy_setup_triggered = False
            baseline_william = None
        
        # 활성 매수 건들에 대해 매도 및 Stop Loss 처리
        remaining_open = []
        for trade in open_trades:
            entry_price = trade["buy_price"]
            profit_pct = ((current["close"] - entry_price) / entry_price) * leverage * 100
            # Stop Loss: -100% 이하일 경우 전량 청산
            if profit_pct <= -100:
                sell_time = current["time"]
                sell_price = current["close"]
                sale_return = trade["amount"] * sell_price
                trade["realized_return"] += sale_return
                final_profit_pct = ((trade["realized_return"] - trade["investment"]) / trade["investment"]) * 100
                trade["sell_label"] = "stop_loss_sell"
                closed_trades.append({
                    "buy_time": trade["buy_time"],
                    "buy_price": trade["buy_price"],
                    "investment": trade["investment"],
                    "sell_time": sell_time,
                    "sell_price": sell_price,
                    "profit_pct": final_profit_pct,
                    "buy_label": trade["buy_label"],
                    "sell_label": trade["sell_label"]
                })
            else:
                # Partial Sell: 아직 부분 매도 안 된 경우, +10% 이상이면 50% 매도
                if (not trade["partial_sold"]) and (profit_pct >= 10):
                    sell_time = current["time"]
                    sell_price = current["close"]
                    sell_amount = trade["amount"] * 0.5
                    sale_return = sell_amount * sell_price
                    trade["realized_return"] += sale_return
                    trade["amount"] -= sell_amount
                    trade["partial_sold"] = True
                    trade["last_sell_time"] = sell_time
                    trade["last_sell_price"] = sell_price
                    trade["sell_label"] = "sell1"
                    remaining_open.append(trade)
                # Full Sell: 이미 부분 매도한 후, +16% 이상이면 남은 포지션 전량 청산
                elif trade["partial_sold"] and (profit_pct >= 16):
                    sell_time = current["time"]
                    sell_price = current["close"]
                    sale_return = trade["amount"] * sell_price
                    trade["realized_return"] += sale_return
                    final_profit_pct = ((trade["realized_return"] - trade["investment"]) / trade["investment"]) * 100
                    trade["sell_label"] = "sell2"
                    capital += sale_return 
                    closed_trades.append({
                        "buy_time": trade["buy_time"],
                        "buy_price": trade["buy_price"],
                        "investment": trade["investment"],
                        "sell_time": sell_time,
                        "sell_price": sell_price,
                        "profit_pct": final_profit_pct,
                        "buy_label": trade["buy_label"],
                        "sell_label": trade["sell_label"]
                    })
                else:
                    remaining_open.append(trade)
        open_trades = remaining_open
        
        # Equity 계산: 현금 + 모든 활성 포지션 평가금액
        open_position_value = sum(trade["amount"] * current["close"] for trade in open_trades)
        equity_curve.append(capital + open_position_value)
    
    return capital, closed_trades, equity_curve

def compute_overall_statistics(closed_trades, initial_capital, trade_unit):
    total_trades = len(closed_trades)
    total_profit = sum(trade["investment"] * (trade["profit_pct"] / 100) for trade in closed_trades)
    overall_profit_pct = (total_profit / (total_trades * trade_unit)) * 100 if total_trades > 0 else 0
    stats = {
        "total_trades": total_trades,
        "total_profit_USDT": total_profit,
        "overall_profit_pct": overall_profit_pct
    }
    return stats

def main():
    # 기간 설정: 1월 1일부터 오늘까지 (날짜 형식 "YYYY-MM-DD")
    start_date = "2025-01-01"
    end_date = datetime.datetime.today().strftime("%Y-%m-%d")
    
    filename = "BTCUSDT_15m_1month.csv"
    initial_capital = 10000.0
    trade_unit = 100.0
    leverage = 10
    
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        logger.info("CSV 파일이 없거나 비어있습니다. Binance API에서 데이터를 받아옵니다...")
        df = fetch_and_save_data(filename, start_date, end_date)
    else:
        df = pd.read_csv(filename)
        if not np.issubdtype(df["time"].dtype, np.datetime64):
            df["time"] = pd.to_datetime(df["time"])
    
    df = calculate_indicators(df)
    final_capital, closed_trades, equity_curve = backtest_strategy(df, initial_capital, trade_unit, leverage)
    
    results_df = pd.DataFrame(closed_trades)
    results_df["buy_time"] = pd.to_datetime(results_df["buy_time"])
    results_df["sell_time"] = pd.to_datetime(results_df["sell_time"])
    results_df = results_df[["buy_time", "buy_price", "investment", "sell_time", "sell_price", "profit_pct", "buy_label", "sell_label"]]
    results_df.to_csv("backtest_results.csv", index=False)
    
    logger.info(f"✅ 백테스트 완료! 최종 자본: {final_capital:.2f} USDT")
    logger.info("거래 내역이 'backtest_results.csv' 파일에 저장되었습니다.")
    
    stats = compute_overall_statistics(closed_trades, initial_capital, trade_unit)
    logger.info("=== 종합 통계 ===")
    for key, value in stats.items():
        logger.info(f"{key}: {value}")
    
    print("=== 거래 내역 ===")
    print(results_df)
    
    plt.figure(figsize=(10,6))
    plt.plot(equity_curve)
    plt.xlabel("캔들 인덱스")
    plt.ylabel("Equity (USDT)")
    plt.title("Equity Curve (자본 변동)")
    plt.grid(True)
    plt.show()
    
    print("\n※ 데이터 기간을 변경하려면, main() 함수 내 start_date와 end_date 변수를 수정하세요.")

if __name__ == "__main__":
    main()
