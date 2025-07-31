import pandas as pd
import numpy as np
import talib  # TA-Lib 설치 필요

# 설정값
leverage = 40
stop_loss_percent = -0.50

# (가상) 거래 데이터
data = {
    'timestamp': pd.to_datetime(['2025-03-24 14:00:00', '2025-03-24 14:05:00', '2025-03-24 14:10:00', '2025-03-24 14:15:00', '2025-03-24 14:20:00',
                                  '2025-03-24 14:25:00', '2025-03-24 14:30:00', '2025-03-24 14:35:00', '2025-03-24 14:40:00', '2025-03-24 14:45:00']),
    'open': [50000, 50050, 50100, 50150, 50200, 50250, 50300, 50350, 50400, 50450],
    'high': [50080, 50120, 50180, 50220, 50280, 50320, 50380, 50420, 50480, 50520],
    'low': [49980, 50030, 50080, 50130, 50180, 50230, 50280, 50330, 50380, 50430],
    'close': [50060, 50110, 50160, 50210, 50260, 50310, 50360, 50410, 50460, 50510],
    'volume': [10, 12, 15, 13, 16, 14, 17, 18, 20, 22]
}
df = pd.DataFrame(data)

# EMA 계산 함수
def calculate_ema(df, period, column='close'):
    return df[column].ewm(span=period, adjust=False).mean()

# RSI 계산 함수 (TA-Lib 사용)
def calculate_rsi(df, period=14, column='close'):
    return talib.RSI(df[column], timeperiod=period)

# (직접 구현) RSI 계산 함수
# def calculate_rsi(df, period=14, column='close'):
#     delta = df[column].diff(1).dropna()
#     up = delta.where(delta > 0, 0)
#     down = -delta.where(delta < 0, 0)
#     avg_gain = up.rolling(window=period, min_periods=period).mean()
#     avg_loss = down.rolling(window=period, min_periods=period).mean()
#     rs = avg_gain / avg_loss
#     return 100 - (100 / (1 + rs))

# 기술 지표 계산
df['ema_10'] = calculate_ema(df, 10)
df['ema_34'] = calculate_ema(df, 34)
df['ema_116'] = calculate_ema(df, 116)
df['rsi_14'] = calculate_rsi(df)

# 매매 로직
in_position = False
entry_price = 0

for i in range(1, len(df)):
    # 롱 매수 조건
    if not in_position and \
       df['ema_10'][i] > df['ema_34'][i] and \
       df['ema_10'][i-1] <= df['ema_34'][i-1] and \
       df['rsi_14'][i] >= 55:
        print(f"{df['timestamp'][i]} - 롱 매수 진입")
        in_position = True
        entry_price = df['close'][i]

    # 매도 조건 (RSI 73 이상)
    elif in_position and df['rsi_14'][i] >= 73:
        print(f"{df['timestamp'][i]} - 롱 매도 (RSI)")
        in_position = False

    # 손절 조건 (-50%)
    elif in_position and (df['close'][i] / entry_price - 1) <= stop_loss_percent:
        print(f"{df['timestamp'][i]} - 손절 ({-stop_loss_percent * 100:.0f}%)")
        in_position = False

if in_position:
    print("미청산 포지션 존재")