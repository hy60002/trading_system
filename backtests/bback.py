import os
import time
import pytz
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance.client import Client
from dotenv import load_dotenv

# 1. 환경 설정 및 Binance 클라이언트 초기화
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")
if not API_KEY or not API_SECRET:
    raise Exception("Binance API 키와 시크릿 키를 .env 파일에 설정하세요.")

client = Client(API_KEY, API_SECRET)

# 2. 파라미터 설정
symbol = "BTCUSDT"                                  # 거래 심볼
interval = Client.KLINE_INTERVAL_15MINUTE           # 15분봉
leverage = 10                                       # 레버리지 10배

# 백테스트 조건: 익절 목표 30% (롱: 30/10 = 3% 상승), 손절 목표 20% (롱: 20/10 = 2% 하락)
tp_target = 30   # 목표 수익률 30%
sl_target = 20   # 목표 손실률 20%
tp_threshold_long = 1 + (tp_target / (100 * leverage))  # 1.03
sl_threshold_long = 1 - (sl_target / (100 * leverage))  # 0.98

# 숏 거래의 경우, 반대로 계산:
tp_threshold_short = 1 - (tp_target / (100 * leverage))  # 0.97
sl_threshold_short = 1 + (sl_target / (100 * leverage))  # 1.02

print(f"[LONG] TP threshold: {tp_threshold_long}, SL threshold: {sl_threshold_long}")
print(f"[SHORT] TP threshold: {tp_threshold_short}, SL threshold: {sl_threshold_short}")

# 3. 데이터 다운로드 (지난 3개월, 15분봉)
utc = pytz.utc
now_utc = datetime.now(utc)
end_time = int(now_utc.timestamp() * 1000)
start_time = int((now_utc - timedelta(days=90)).timestamp() * 1000)

klines = client.futures_klines(symbol=symbol, interval=interval, startTime=start_time, endTime=end_time)
if not klines:
    print("데이터 다운로드 실패")
    exit()

columns = ['open_time', 'open', 'high', 'low', 'close', 'volume',
           'close_time', 'quote_asset_volume', 'num_trades', 
           'taker_buy_base', 'taker_buy_quote', 'ignore']
df = pd.DataFrame(klines, columns=columns)

# 형변환
for col in ['open', 'high', 'low', 'close', 'volume']:
    df[col] = pd.to_numeric(df[col])
df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

# 4. 기술 지표 계산 (RSI, 윌리엄 %R)
# RSI (Wilder's smoothing, 윈도우=14)
delta = df['close'].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
window = 14
avg_gain = gain.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
df['rsi'] = 100 - (100 / (1 + rs))
df['rsi'] = df['rsi'].fillna(100)

# 윌리엄 %R (윈도우=14)
high14 = df['high'].rolling(window=14).max()
low14 = df['low'].rolling(window=14).min()
range_val = high14 - low14
df['william'] = np.where(range_val == 0, 0, (high14 - df['close']) / range_val * -100)

# 5. 백테스트 시뮬레이션
trades = []
n = len(df)
# 시작 인덱스: RSI 계산을 위해 최소 14봉 이후, 그리고 3봉을 사용하므로 14까지 건너뜁니다.
i = 14

while i < n - 2:
    # 최근 3봉을 이용한 조건 계산
    rsi_2 = df.iloc[i]['rsi']
    rsi_1 = df.iloc[i+1]['rsi']
    rsi_0 = df.iloc[i+2]['rsi']
    will_2 = df.iloc[i]['william']
    will_1 = df.iloc[i+1]['william']
    will_0 = df.iloc[i+2]['william']
    
    trade_executed = False

    # --- 롱 진입 조건 ---
    if (rsi_0 <= 35 and will_0 <= -70 and 
        (rsi_2 > rsi_1 > rsi_0) and 
        (will_2 > will_1 and will_1 < will_0)):
        entry_index = i + 2
        entry_price = df.iloc[entry_index]['close']
        entry_time = df.iloc[entry_index]['close_time']
        direction = "LONG"
        
        # 진입 후 TP/SL 조건 확인 (롱)
        for j in range(entry_index + 1, n):
            high = df.iloc[j]['high']
            low = df.iloc[j]['low']
            if high >= entry_price * tp_threshold_long:
                exit_price = entry_price * tp_threshold_long
                outcome = 'TP'
                exit_index = j
                trade_executed = True
                break
            elif low <= entry_price * sl_threshold_long:
                exit_price = entry_price * sl_threshold_long
                outcome = 'SL'
                exit_index = j
                trade_executed = True
                break

    # --- 숏 진입 조건 ---
    elif (rsi_0 >= 65 and will_0 >= -30 and 
          (rsi_2 < rsi_1 < rsi_0) and 
          (will_2 < will_1 and will_1 > will_0)):
        entry_index = i + 2
        entry_price = df.iloc[entry_index]['close']
        entry_time = df.iloc[entry_index]['close_time']
        direction = "SHORT"
        
        # 진입 후 TP/SL 조건 확인 (숏): 가격이 내려가면 이익, 올라가면 손실
        for j in range(entry_index + 1, n):
            low = df.iloc[j]['low']
            high = df.iloc[j]['high']
            if low <= entry_price * tp_threshold_short:
                exit_price = entry_price * tp_threshold_short
                outcome = 'TP'
                exit_index = j
                trade_executed = True
                break
            elif high >= entry_price * sl_threshold_short:
                exit_price = entry_price * sl_threshold_short
                outcome = 'SL'
                exit_index = j
                trade_executed = True
                break

    if trade_executed:
        if direction == "LONG":
            profit_pct = ((exit_price - entry_price) / entry_price * 100) * leverage
        else:  # SHORT
            profit_pct = ((entry_price - exit_price) / entry_price * 100) * leverage

        trades.append({
            'direction': direction,
            'entry_time': entry_time,
            'exit_time': df.iloc[exit_index]['close_time'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'outcome': outcome,
            'profit_pct': profit_pct
        })
        # 거래가 종료된 봉의 다음 봉부터 새 거래 탐색
        i = exit_index + 1
    else:
        i += 1

# 6. 백테스트 결과 출력
trades_df = pd.DataFrame(trades)
if trades_df.empty:
    print("거래가 발생하지 않았습니다.")
else:
    num_trades = len(trades_df)
    wins = trades_df[trades_df['profit_pct'] > 0]
    losses = trades_df[trades_df['profit_pct'] < 0]
    win_rate = (len(wins) / num_trades * 100) if num_trades else 0
    avg_profit = trades_df['profit_pct'].mean() if num_trades else 0
    total_profit = trades_df['profit_pct'].sum() if num_trades else 0

    print("\n백테스트 결과:")
    print(f"전체 거래 수: {num_trades}")
    print(f"승률: {win_rate:.2f}%")
    print(f"평균 수익률: {avg_profit:.2f}%")
    print(f"총 수익률 (누적): {total_profit:.2f}%\n")
    print(trades_df)

