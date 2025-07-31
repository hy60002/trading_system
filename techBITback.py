from binance.client import Client
from datetime import datetime, timedelta
import pandas as pd
import os

# 1. 바이낸스 API 키 설정 (직접 입력 or .env 활용)
api_key = "YOUR_API_KEY"
api_secret = "YOUR_API_SECRET"
client = Client(api_key, api_secret)

# 2. OHLCV 데이터 수집 함수
def get_ohlcv(symbol: str, interval: str, days: int = 365):
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)

    klines = client.get_historical_klines(
        symbol=symbol,
        interval=interval,
        start_str=start_time.strftime("%Y-%m-%d %H:%M:%S"),
        end_str=end_time.strftime("%Y-%m-%d %H:%M:%S")
    )

    df = pd.DataFrame(klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
    ])

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("datetime", inplace=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df

# 3. BTCUSDT 30분봉 데이터 저장
btc_30m = get_ohlcv("BTCUSDT", Client.KLINE_INTERVAL_30MINUTE, 365)
btc_30m.to_csv("btcusdt_30m.csv")
print("✅ BTCUSDT 30분봉 데이터 저장 완료!")
