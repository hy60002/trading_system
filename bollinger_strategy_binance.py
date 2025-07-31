
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

# 🧠 전략 로직: 볼린저밴드 하단 하락 + 30% 추가 하락 + RSI < 40 → 다음 봉 마감 청산
def apply_bollinger_rsi_strategy_relaxed(df, tf_minutes):
    df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
    bb = BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_lower'] = bb.bollinger_lband()
    df.dropna(inplace=True)

    entries = []
    for i in range(2, len(df) - 1):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        prev_open = prev['open']
        prev_close = prev['close']
        curr_close = curr['close']

        prev_drop = prev_open - prev_close
        curr_drop = prev_close - curr_close

        if (
            prev_close < prev['bb_lower'] and
            curr_drop >= prev_drop * 0.3 and
            curr['rsi'] < 40
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

# ▶ 실행
if __name__ == "__main__":
    print("⏳ 바이낸스 15분봉 데이터 수집 중...")
    df_binance_15m = fetch_binance_ohlcv('BTC/USDT', '15m', 365)
    print(f"📈 데이터 수집 완료: {len(df_binance_15m)}개")

    print("🔍 전략 조건 평가 중...")
    signals = apply_bollinger_rsi_strategy_relaxed(df_binance_15m.copy(), 15)
    summary = summarize(signals)
    print("\n✅ 전략 결과 요약:")
    print(summary)

    if not isinstance(summary, str):
        signals.to_csv("bollinger_strategy_results.csv", index=False)
        print("📁 진입 및 수익 결과가 'bollinger_strategy_results.csv'에 저장되었습니다.")
