import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance.client import Client

# ====================== 설정 ======================
API_KEY         = "YOUR_BINANCE_API_KEY"
API_SECRET      = "YOUR_BINANCE_API_SECRET"
client          = Client(api_key=API_KEY, api_secret=API_SECRET)

SYMBOLS         = ['BTCUSDT', 'ETHUSDT', 'DOGEUSDT', 'XRPUSDT']
INTERVAL        = '1h'
START_DATE      = datetime.utcnow() - timedelta(days=365)
FEE_RATE        = 0.0007
INITIAL_CAPITAL = 1000
# ==================================================

def get_1y_ohlcv(symbol):
    """
    START_DATE부터 현재까지 1시간봉 데이터를
    최대 1000캔들씩 반복 호출하여 1년치 전체를 가져옵니다.
    """
    df_all  = pd.DataFrame()
    current = START_DATE

    while current < datetime.utcnow():
        start_ms = int(current.timestamp() * 1000)
        klines = client.get_klines(
            symbol=symbol,
            interval=INTERVAL,
            startTime=start_ms,
            limit=1000
        )
        if not klines:
            break

        df = pd.DataFrame(klines, columns=[
            'timestamp','open','high','low','close','volume',
            'close_time','qav','trades','taker_base_vol','taker_quote_vol','ignore'
        ])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
        df = df[['open','high','low','close','volume']].astype(float)

        df_all = pd.concat([df_all, df])
        last_time = df.index[-1]
        current = last_time + timedelta(hours=1)

    # 중복 인덱스 제거 후 반환
    return df_all[~df_all.index.duplicated(keep='first')]

def deviation_trend_profile(df, window=20, deviation=2.5):
    """
    Deviation Trend Profile 계산:
    - ma: 이동평균
    - upper/lower: ma ± deviation * std
    - trend: up/down
    - signal: blue_circle/red_circle
    """
    df = df.copy()
    df['ma']    = df['close'].rolling(window=window).mean()
    df['std']   = df['close'].rolling(window=window).std()
    df['upper'] = df['ma'] + deviation * df['std']
    df['lower'] = df['ma'] - deviation * df['std']

    df['trend'] = np.nan
    for i in range(1, len(df)):
        if df['close'].iat[i] > df['upper'].iat[i]:
            df['trend'].iat[i] = 'up'
        elif df['close'].iat[i] < df['lower'].iat[i]:
            df['trend'].iat[i] = 'down'
        else:
            df['trend'].iat[i] = df['trend'].iat[i-1]

    df['signal'] = None
    for i in range(1, len(df)):
        prev, curr = df['trend'].iat[i-1], df['trend'].iat[i]
        if prev != curr:
            df['signal'].iat[i] = 'blue_circle' if curr == 'up' else 'red_circle'

    return df

def backtest(df):
    """
    신호에 따라 롱 진입/청산 후:
    - TotalReturn, WinRate, AvgTrade, MaxDrawdown, NumTrades 계산
    """
    balance      = INITIAL_CAPITAL
    entry_price  = None
    equity_curve = [balance]
    trades       = []

    for _, row in df.iterrows():
        sig   = row['signal']
        price = row['close']

        if sig == 'blue_circle' and entry_price is None:
            entry_price = price
        elif sig == 'red_circle' and entry_price is not None:
            ret = (price - entry_price) / entry_price - FEE_RATE * 2
            balance *= (1 + ret)
            equity_curve.append(balance)
            trades.append(ret)
            entry_price = None

    peak   = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd

    return {
        'TotalReturn':   round((balance / INITIAL_CAPITAL - 1) * 100, 2),
        'WinRate':       round(np.mean([1 for r in trades if r > 0]) * 100, 2) if trades else 0,
        'AvgTrade':      round(np.mean(trades) * 100, 2) if trades else 0,
        'MaxDrawdown':   round(max_dd, 2),
        'NumTrades':     len(trades)
    }

if __name__ == "__main__":
    results = []
    for symbol in SYMBOLS:
        print(f"▶ {symbol} 데이터 수집 중...")
        df = get_1y_ohlcv(symbol)
        print(f"→ {len(df)}개 캔들 수집됨")
        df = deviation_trend_profile(df)
        stats = backtest(df)
        stats['Symbol'] = symbol
        results.append(stats)

    df_result = pd.DataFrame(results)[
        ['Symbol', 'TotalReturn', 'WinRate', 'AvgTrade', 'MaxDrawdown', 'NumTrades']
    ]

    print("\n📊 1시간봉 1년치 DTP 백테스트 결과:")
    print(df_result.to_string(index=False))
