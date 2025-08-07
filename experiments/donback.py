import pyupbit
import pandas as pd
import numpy as np
import datetime

def fetch_ohlcv(ticker, interval, count):
    """
    pyupbit.get_ohlcv를 이용해 지정된 개수의 캔들 데이터를 가져옵니다.
    """
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    return df

def calculate_donchian(df, period=20):
    """
    돈치안 채널 계산: 
      - Upper Band: 최근 period 캔들 중 최고가
      - Lower Band: 최근 period 캔들 중 최저가
      - Middle Line: Upper와 Lower의 평균
    (4시간봉 기준 20봉으로 계산)
    """
    df['don_upper'] = df['high'].rolling(window=period).max()
    df['don_lower'] = df['low'].rolling(window=period).min()
    df['don_mid'] = (df['don_upper'] + df['don_lower']) / 2
    return df

def calculate_lwti(df, period=20):
    """
    LWTI 계산 (예시 공식):
      LWTI = 50 + ((현재 종가 - 이동평균) / 표준편차) * 10
    period=20로 계산 (4시간봉 20봉, 약 80시간 분량)
    """
    rolling_mean = df['close'].rolling(window=period).mean()
    rolling_std = df['close'].rolling(window=period).std()
    df['lwti'] = 50 + ((df['close'] - rolling_mean) / rolling_std) * 10
    df['lwti'] = df['lwti'].fillna(50)
    return df

def backtest_donwin():
    """
    1. 지난 6개월간의 4시간봉 데이터 수집 (6개월 ~ 180일, 6캔들/일 => 약 1080캔들)
    2. 돈치안 채널 및 LWTI 계산 (둘 다 period=20로 설정)
    3. 각 4시간봉 캔들마다 진입 및 청산 로직 시뮬레이션
    4. 거래 내역을 CSV에 저장하고, 최종 성과를 출력
    """
    ticker = "KRW-BTC"
    # 4시간봉 데이터 6개월치: 6캔들*180일 = 1080캔들
    df_4h = fetch_ohlcv(ticker, interval='minute240', count=1080)
    
    if df_4h is None or df_4h.empty:
        print("데이터를 충분히 가져오지 못했습니다.")
        return

    # 돈치안 채널 계산 (4시간봉 기준 20봉)
    df_4h = calculate_donchian(df_4h, period=20)
    # LWTI 계산 (4시간봉 기준 20봉)
    df_4h = calculate_lwti(df_4h, period=20)
    
    # 백테스트 초기 모의 잔고 및 변수 설정
    initial_balance = 1000000  # 모의 잔고 1,000,000 KRW
    balance = initial_balance
    position = 0.0            # 보유 BTC 수량
    entry_price = None
    trade_records = []        # 거래 내역 저장
    partial_exit_done = False # 부분 청산 여부 플래그
    signal_count = 0          # 진입 신호 발생 횟수

    # 백테스트 시작: 돈치안 채널 계산이 가능한 시점 (인덱스 20 이후)
    for i in range(20, len(df_4h)):
        current_row = df_4h.iloc[i]
        current_time = df_4h.index[i]
        current_price = current_row['close']
        don_upper = current_row['don_upper']
        don_mid = current_row['don_mid']
        lwti_val = current_row['lwti']

        # 유효한 값 확인
        if pd.isna(don_upper) or pd.isna(lwti_val):
            continue

        # 디버깅 출력: 각 캔들의 주요 값 확인
        print(f"[{current_time}] Price: {current_price:.0f}, DonUpper: {don_upper:.0f}, DonMid: {don_mid:.0f}, LWTI: {lwti_val:.2f}")

        # ===== 진입 로직 =====
        # 포지션이 없을 때, 현재 가격이 돈치안 채널 상단을 돌파하고, LWTI가 48 이상이면 매수
        if position <= 0:
            if current_price > don_upper and lwti_val > 48:
                signal_count += 1
                print(f" --> 진입 신호 발생 at {current_time} | Price: {current_price:.0f}, LWTI: {lwti_val:.2f}")
                # 계좌 잔고의 50% 사용
                krw_to_spend = balance * 0.5
                if krw_to_spend > 0:
                    buy_qty = krw_to_spend / current_price
                    position = buy_qty
                    balance -= krw_to_spend
                    entry_price = current_price
                    partial_exit_done = False
                    trade_records.append({
                        'time': current_time,
                        'type': 'BUY',
                        'price': current_price,
                        'qty': buy_qty,
                        'balance': balance,
                        'position': position
                    })
        # ===== 청산 로직 =====
        else:
            pct_change = (current_price - entry_price) / entry_price * 100

            # (1) 부분 청산: 가격이 돈치안 중간선 이상에 도달하고 아직 부분 청산하지 않았다면
            if not partial_exit_done and current_price >= don_mid:
                print(f" --> 부분 청산 신호 at {current_time} | Price: {current_price:.0f}, 기준선: {don_mid:.0f}")
                sell_qty = position * 0.5
                position -= sell_qty
                balance += sell_qty * current_price
                partial_exit_done = True
                trade_records.append({
                    'time': current_time,
                    'type': 'PARTIAL_EXIT',
                    'price': current_price,
                    'qty': sell_qty,
                    'balance': balance,
                    'position': position
                })

            # (2) 추가 청산: 진입가 대비 +5% 이상 상승 시 전량 청산
            if pct_change >= 5:
                print(f" --> 추가 청산 신호 at {current_time} | Price: {current_price:.0f}, 수익률: {pct_change:.2f}%")
                sell_qty = position
                position = 0
                balance += sell_qty * current_price
                trade_records.append({
                    'time': current_time,
                    'type': 'FULL_EXIT(+5%)',
                    'price': current_price,
                    'qty': sell_qty,
                    'balance': balance,
                    'position': position
                })
                entry_price = None
                continue

            # (3) LWTI 과열: LWTI가 70 이상이면 전량 청산
            if lwti_val >= 70:
                print(f" --> LWTI 과열 청산 신호 at {current_time} | LWTI: {lwti_val:.2f}")
                sell_qty = position
                position = 0
                balance += sell_qty * current_price
                trade_records.append({
                    'time': current_time,
                    'type': 'FULL_EXIT(LWTI70)',
                    'price': current_price,
                    'qty': sell_qty,
                    'balance': balance,
                    'position': position
                })
                entry_price = None
                continue

            # (4) 손절: 진입가 대비 -2% 하락하며 LWTI가 50 미만이면 전량 손절
            if pct_change <= -2 and lwti_val < 50:
                print(f" --> 손절 신호 at {current_time} | Price: {current_price:.0f}, 수익률: {pct_change:.2f}%")
                sell_qty = position
                position = 0
                balance += sell_qty * current_price
                trade_records.append({
                    'time': current_time,
                    'type': 'STOP_LOSS',
                    'price': current_price,
                    'qty': sell_qty,
                    'balance': balance,
                    'position': position
                })
                entry_price = None
                continue

    # 백테스트 종료 후, 남은 포지션이 있다면 마지막 종가로 청산 가정
    final_value = balance
    if position > 0 and entry_price is not None:
        last_price = df_4h['close'].iloc[-1]
        final_value += position * last_price

    profit = final_value - initial_balance
    profit_pct = profit / initial_balance * 100

    # 거래 내역 DataFrame 생성 및 CSV 저장
    trades_df = pd.DataFrame(trade_records)
    trades_df.to_csv("donback_result.csv", index=False)

    print("\n===== 백테스트 결과 =====")
    print(f"최종 자본: {final_value:,.0f} KRW")
    print(f"순이익: {profit:,.0f} KRW ({profit_pct:.2f}%)")
    print(f"거래 횟수(체결 건수): {len(trade_records)}")
    print(f"진입 신호 발생 횟수: {signal_count}")
    print("거래 내역 CSV: donback_result.csv")

if __name__ == "__main__":
    backtest_donwin()
