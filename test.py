import ccxt
import pandas as pd
import numpy as np
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta

# ⏳ Binance에서 과거 1년치 15분봉 데이터 가져오기
def fetch_binance_ohlcv(symbol='BTC/USDT', timeframe='15m', since_days=365):
    exchange = ccxt.binance()
    since = exchange.parse8601((datetime.utcnow() - timedelta(days=since_days)).strftime('%Y-%m-%dT%H:%M:%S'))
    all_data = []
    while True:
        data = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not data:
            break
        all_data += data
        since = data[-1][0] + 1
        if len(data) < 1000:
            break
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df

# 🧠 전략 로직
def apply_bollinger_rsi_strategy(df, tf_minutes):
    df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
    bb = BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_lower'] = bb.bollinger_lband()

    df.dropna(inplace=True)
    entries = []

    for i in range(2, len(df) - 1):
        prev_close = df.iloc[i - 1]['close']
        prev_lower = df.iloc[i - 1]['bb_lower']
        curr_close = df.iloc[i]['close']
        prev_open = df.iloc[i - 1]['open']

        prev_drop = prev_open - prev_close
        curr_drop = df.iloc[i - 1]['close'] - curr_close

        if (
            prev_close < prev_lower and
            curr_drop >= prev_drop * 0.5 and
            df.iloc[i]['rsi'] < 40
        ):
            entry_price = curr_close
            exit_price = df.iloc[i + 1]['close']
            return_pct = (exit_price - entry_price) / entry_price * 100
            entries.append({
                'entry_time': df.index[i],
                'exit_time': df.index[i + 1],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'return_pct': return_pct
            })

    return pd.DataFrame(entries)

# ✅ 실행
df_binance_15m = fetch_binance_ohlcv('BTC/USDT', '15m', 365)
signals_15m = apply_bollinger_rsi_strategy(df_binance_15m, 15)

# 📊 결과 요약
def summarize(df):
    if df.empty:
        return "진입 조건을 만족한 결과가 없습니다."
    return {
        '총 진입 횟수': len(df),
        '승률': round(len(df[df['return_pct'] > 0]) / len(df) * 100, 2),
        '평균 수익률': round(df['return_pct'].mean(), 3),
        '최대 수익률': round(df['return_pct'].max(), 3),
        '최소 수익률': round(df['return_pct'].min(), 3)
    }

summary = summarize(signals_15m)
print(summary)
