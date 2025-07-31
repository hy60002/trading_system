import pandas as pd
from yfinance import Ticker
import requests
import numpy as np

# Access token acquisition
access_token = "YOUR_ACCESS_TOKEN"

def get_upbit_access_token():
    url = f"https://api.upbit.com/v1/accounts"
    headers = {
        'x-access-token': access_token,
    }
    response = requests.get(url, headers=headers)
    return response.json()['data'][0]['access_token']

upbit_access_token = get_upbit_access_token()

# Define stock symbol and date range
stock_symbol = "KRX:"
start_date = "2022-01-01"
end_date = "2023-02-28"

# Get historical data from UPBIT API
def get_historical_data(access_token, stock_symbol, start_date, end_date):
    url = f"https://api.upbit.com/v1/spot/event?isComplete=true&startTime={start_date}&endTime={end_date}"
    headers = {
        'x-access-token': access_token,
        'Content-Type': "application/json"
    }
    data = {
        "eventType":"market_data",
        "symbol":stock_symbol,
        "isComplete":True
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

historical_data = get_historical_data(upbit_access_token, stock_symbol, start_date, end_date)

# Extract trade data from historical data
def extract_trade_data(data):
    trade_data = []
    for item in data['payload']['events']:
        if item['type'] == 'market_data':
            trade_data.append({
                'timestamp': item['data']['trade_time'],
                'close_price': item['data']['trade_price']
            })
    return pd.DataFrame(trade_data)

df = extract_trade_data(historical_data['payload'])

# Define trading strategy
def define_trading_strategy(df):
    # Simple moving average crossover strategy
    df['short_ma'] = df['close_price'].rolling(window=10).mean()
    df['long_ma'] = df['close_price'].rolling(window=30).mean()
    df['signal'] = np.where(df['short_ma'] > df['long_ma'], 1, 0)
    return df

df = define_trading_strategy(df)

# Define position management
def manage_positions(df):
    # Initialize positions dictionary
    positions = {}
    for index, row in df.iterrows():
        if row['signal'] == 1:
            if 'buy' not in positions.keys():
                positions['buy'] = {'stock': stock_symbol, 'quantity': 100}
            else:
                quantities = positions['buy']['quantity']
                positions['buy']['quantity'] += quantities * (row['close_price'] / df.loc[index-10,
'close_price'])
        elif row['signal'] == -1:
            if 'sell' not in positions.keys():
                positions['sell'] = {'stock': stock_symbol, 'quantity': 100}
            else:
                quantities = positions['sell']['quantity']
                positions['sell']['quantity'] += quantities * (df.loc[index-10, 'close_price'] /
row['close_price'])
    return positions

positions = manage_positions(df)

# Print final positions
print("Final Positions:")
for key, value in positions.items():
    print(f"{key}: {value}")