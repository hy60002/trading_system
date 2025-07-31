import pyupbit
import pandas as pd
import numpy as np

# 1️⃣ 15일치 15분봉 & 5분봉 데이터 가져오기
df_15m = pyupbit.get_ohlcv("KRW-BTC", count=1440, interval="minute15")  # 15분봉 (1440개)
df_5m = pyupbit.get_ohlcv("KRW-BTC", count=4320, interval="minute5")  # 5분봉 (4320개)

# 2️⃣ 볼린저밴드, RSI, Williams %R 계산 (15분봉 & 5분봉)
def calculate_indicators(df):
    df['middle_band'] = df['close'].rolling(window=20).mean()
    df['rsi'] = 100 - (100 / (1 + df['close'].pct_change().rolling(window=14).mean() /
                               df['close'].pct_change().rolling(window=14).std()))
    df['william'] = (df['high'].rolling(window=14).max() - df['close']) / \
                    (df['high'].rolling(window=14).max() - df['low'].rolling(window=14).min()) * -100
    return df

df_15m = calculate_indicators(df_15m)
df_5m = calculate_indicators(df_5m)

# 3️⃣ 백테스트 실행 변수 설정
initial_balance = 1_000_000  # 초기 투자금 (100만원)
balance = initial_balance
btc_balance = 0
entry_price = None
trade_log = []

# 4️⃣ 백테스트 실행 (15분봉 & 5분봉 데이터 사용)
for i in range(20, len(df_15m)):
    current_price = df_15m['close'].iloc[i]
    recent_5m = df_5m.loc[df_5m.index < df_15m.index[i]].tail(5)  # 최근 5개 5분봉 데이터 사용

    # ✅ 매수 조건 체크 (15분봉 기준, 5분봉 보조 확인)
    if (
        df_15m['close'].iloc[i] < df_15m['middle_band'].iloc[i] and
        df_15m['rsi'].iloc[i] < 35 and
        df_15m['rsi'].iloc[i-2] > df_15m['rsi'].iloc[i-1] > df_15m['rsi'].iloc[i] and
        df_15m['william'].iloc[i] < -75 and
        df_15m['william'].iloc[i-2] > df_15m['william'].iloc[i-1] < df_15m['william'].iloc[i] and
        balance >= 100000 and
        recent_5m['rsi'].mean() < 40  # 5분봉 RSI 추가 확인
    ):
        btc_bought = 100000 / current_price
        btc_balance += btc_bought
        balance -= 100000
        entry_price = current_price
        trade_log.append({'condition_time': df_15m.index[i], 'action': 'BUY', 'time': df_15m.index[i], 'amount': 100000, 'reason': '조건 충족', 'balance': balance, 'btc': btc_balance})

    # ✅ 추가 매수 (-5% 하락 시)
    if entry_price and (current_price - entry_price) / entry_price * 100 <= -5 and balance >= 100000:
        btc_bought = 100000 / current_price
        btc_balance += btc_bought
        balance -= 100000
        entry_price = (entry_price + current_price) / 2  # 평균 매수가 조정
        trade_log.append({'condition_time': df_15m.index[i], 'action': 'ADD BUY', 'time': df_15m.index[i], 'amount': 100000, 'reason': '손실 -5% 추가 매수', 'balance': balance, 'btc': btc_balance})

    # ✅ 익절 조건 (5% → 50% 매도, 이후 3% or 8% 도달 시 전량 매도)
    if entry_price:
        profit_pct = (current_price - entry_price) / entry_price * 100

        if profit_pct >= 5 and btc_balance > 0:
            btc_sold = btc_balance * 0.5
            balance += btc_sold * current_price
            btc_balance -= btc_sold
            trade_log.append({'condition_time': df_15m.index[i], 'action': 'SELL 50%', 'time': df_15m.index[i], 'amount': btc_sold * current_price, 'reason': '수익 +5%', 'balance': balance, 'btc': btc_balance})

        if profit_pct >= 3 or profit_pct >= 8 and btc_balance > 0:
            balance += btc_balance * current_price
            btc_balance = 0
            trade_log.append({'condition_time': df_15m.index[i], 'action': 'SELL ALL', 'time': df_15m.index[i], 'amount': balance, 'reason': '수익 +3% 또는 +8%', 'balance': balance, 'btc': btc_balance})
            entry_price = None  # 매도 후 초기화

# 5️⃣ 결과 정리
final_balance = balance + (btc_balance * df_15m['close'].iloc[-1])
profit_pct = ((final_balance - initial_balance) / initial_balance) * 100

# 6️⃣ 백테스트 결과 출력
trade_df = pd.DataFrame(trade_log)
trade_df.to_csv("techBIT_backtest_results.csv", index=False)

print(f"✅ 최종 잔고: {final_balance} 원")
print(f"📈 총 수익률: {profit_pct:.2f}%")
