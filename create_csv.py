import os
import time
import datetime
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

# Binance API 키 로드
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_SECRET_KEY")

# Binance API 연결
client = Client(API_KEY, API_SECRET)

def fetch_binance_data(symbol="BTCUSDT", interval=Client.KLINE_INTERVAL_15MINUTE, start_date="2025-01-01", end_date="2025-03-02"):
    """
    Binance API에서 15분봉 데이터를 가져와 CSV 파일로 저장하는 함수
    """
    filename = "BTCUSDT_15m_1month.csv"
    
    # 시작 및 종료 시간을 밀리초로 변환
    start_ts = int(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
    
    klines = client.futures_historical_klines(symbol, interval, start_str=start_ts, end_str=end_ts)
    
    # 데이터가 없으면 에러 처리
    if not klines:
        raise ValueError("Binance API에서 데이터를 가져오지 못했습니다.")
    
    # 데이터 프레임 생성
    df = pd.DataFrame(klines, columns=["time", "open", "high", "low", "close", "volume",
                                       "close_time", "quote_asset_volume", "trades", "taker_base", "taker_quote", "ignore"])
    
    # 필요한 컬럼만 선택
    df = df[["time", "open", "high", "low", "close", "volume"]]
    
    # 타임스탬프를 datetime 형식으로 변환
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    
    # CSV 파일로 저장
    df.to_csv(filename, index=False)
    
    print(f"✅ {filename} 파일 저장 완료!")
    return df

# 실행
df = fetch_binance_data()

