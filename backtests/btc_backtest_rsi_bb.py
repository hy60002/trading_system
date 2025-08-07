import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from binance.client import Client
from ta.volatility import BollingerBands
from datetime import datetime, timedelta
import time

# Binance API 설정 (공개 데이터만 사용)
client = Client()

# 전략 파라미터
SYMBOL = 'BTCUSDT'
INTERVAL_MAIN = Client.KLINE_INTERVAL_30MINUTE
INTERVAL_SUB = Client.KLINE_INTERVAL_1MINUTE
LIMIT = 1000
MONTHS = 6
LEVERAGE = 20
INITIAL_BALANCE = 1000.0

def get_klines(symbol, interval, start_time, end_time):
    klines = []
    while start_time < end_time:
        temp = client.get_klines(
            symbol=symbol,
            interval=interval,
            startTime=int(start_time.timestamp() * 1000),
            endTime=int(min(end_time, start_time + timedelta(minutes=interval_to_minutes(interval)*LIMIT)).timestamp() * 1000),
            limit=LIMIT
        )
        if not temp:
            break
        klines.extend(temp)
        start_time = datetime.fromtimestamp(temp[-1][0] / 1000) + timedelta(minutes=interval_to_minutes(interval))
        time.sleep(0.2)
    return klines

def interval_to_minutes(interval):
    if 'm' in interval:
        return int(interval.replace('m', ''))
    if 'h' in interval:
        return int(interval.replace('h', '')) * 60
    return 1

def fetch_data():
    end = datetime.utcnow()
    start = end - timedelta(days=30 * MONTHS)
    print("📥 Binance에서 최근 6개월치 30분봉 + 1분봉 데이터 수집 중...")
    main_klines = get_klines(SYMBOL, INTERVAL_MAIN, start, end)
    sub_klines = get_klines(SYMBOL, INTERVAL_SUB, start, end)
    df_main = pd.DataFrame(main_klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', '_', '_', '_', '_', '_', '_'])
    df_sub = pd.DataFrame(sub_klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', '_', '_', '_', '_', '_', '_'])
    for df in [df_main, df_sub]:
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df_main, df_sub

def simulate_trades(df_main, df_sub):
    balance = INITIAL_BALANCE
    trades = []
    bb = BollingerBands(close=df_main['close'], window=20, window_dev=2)
    df_main['bb_lower'] = bb.bollinger_lband()
    df_main['bb_upper'] = bb.bollinger_hband()

    for i in range(1, len(df_main) - 1):
        A = df_main.iloc[i - 1]
        B = df_main.iloc[i]
        C = df_main.iloc[i + 1]

        if A['close'] >= A['open']:
            continue
        if A['close'] > A['bb_lower']:
            continue

        drop_a = (A['open'] - A['close']) / A['open']

        # B 구간의 1분봉 확인
        b_start, b_end = B.name, C.name
        df_b_sub = df_sub[(df_sub.index >= b_start) & (df_sub.index < b_end)]

        entry_price = None
        for _, row in df_b_sub.iterrows():
            drop_b = (B['open'] - row['low']) / B['open']
            if drop_b >= drop_a * 0.7:
                entry_price = row['low']
                break

        if entry_price:
            exit_price = C['close']
            profit_pct = (exit_price - entry_price) / entry_price
            profit = balance * profit_pct * LEVERAGE
            balance += profit
            trades.append({
                'entry_time': row.name,
                'entry_price': entry_price,
                'exit_time': C.name,
                'exit_price': exit_price,
                'profit_pct': profit_pct,
                'balance': balance
            })

    return trades, balance

def summarize(trades, final_balance):
    df = pd.DataFrame(trades)
    total = len(df)
    wins = df[df['profit_pct'] > 0]
    losses = df[df['profit_pct'] <= 0]
    win_rate = len(wins) / total * 100 if total > 0 else 0
    avg_profit = df['profit_pct'].mean() * 100 if total > 0 else 0
    max_gain = df['profit_pct'].max() * 100 if total > 0 else 0
    max_loss = df['profit_pct'].min() * 100 if total > 0 else 0

    print(f"\n✅ 백테스트 결과 요약")
    print(f"총 트레이드 수: {total}")
    print(f"최종 자산: ${final_balance:.2f}")
    print(f"평균 수익률: {avg_profit:.2f}%")
    print(f"승률: {win_rate:.2f}%")
    print(f"최대 수익률: {max_gain:.2f}%")
    print(f"최대 손실률: {max_loss:.2f}%")

    # 자산 곡선 그리기
    plt.plot(df['balance'].values)
    plt.title("📈 자산 변화 추이")
    plt.xlabel("트레이드 횟수")
    plt.ylabel("자산 ($)")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

df_main, df_sub = fetch_data()
trades, final_balance = simulate_trades(df_main, df_sub)
summarize(trades, final_balance)
