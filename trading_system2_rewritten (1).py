import os
import sys
import time
import json
import asyncio
import logging
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import traceback
import hashlib
import hmac
import base64
from collections import defaultdict, deque
import threading
import pickle
from functools import lru_cache
import aiofiles
# External imports
import numpy as np
import pandas as pd
import requests
import aiohttp
import websockets
import feedparser
import ccxt
from dotenv import load_dotenv
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Depends, Security, WebSocket, WebSocketDisconnect, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from pydantic import BaseModel, Field, validator
import openai
import talib
import sqlite3
from contextlib import contextmanager
import redis
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.ensemble import RandomForestRegressor
import joblib
import backoff
from cachetools import TTLCache
import queue
warnings.filterwarnings('ignore')
# ==============================
# Enhanced Configuration
# ==============================
@dataclass
class TradingConfig:
   """Centralized configuration with validation"""
# API Keys
BITGET_API_KEY: str = ""
BITGET_SECRET_KEY: str = ""
BITGET_PASSPHRASE: str = ""
OPENAI_API_KEY: str = ""
TELEGRAM_BOT_TOKEN: str = ""
TELEGRAM_CHAT_ID: str = ""
# Trading Symbols (Fixed)
SYMBOLS: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "XRPUSDT"])

# Fixed Leverage
LEVERAGE: Dict[str, int] = field(default_factory=lambda: {
    "BTCUSDT": 20,
    "ETHUSDT": 10,
    "XRPUSDT": 10
})

# Portfolio Allocation
PORTFOLIO_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
    "BTCUSDT": 0.7,  # 70%
    "ETHUSDT": 0.2,  # 20%
    "XRPUSDT": 0.1   # 10%
})

# Position Size Ranges (% of allocated capital)
POSITION_SIZE_RANGE: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
    "BTCUSDT": {"min": 0.15, "standard": 0.25, "max": 0.35},
    "ETHUSDT": {"min": 0.05, "standard": 0.10, "max": 0.15},
    "XRPUSDT": {"min": 0.03, "standard": 0.05, "max": 0.08}
})

# Max Positions per Symbol
MAX_POSITIONS: Dict[str, int] = field(default_factory=lambda: {
    "BTCUSDT": 3,
    "ETHUSDT": 1,
    "XRPUSDT": 1
})

# Entry Conditions by Symbol
ENTRY_CONDITIONS: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
    "BTCUSDT": {
        "signal_threshold": 0.3,
        "confidence_required": 50,
        "timeframe_agreement": 0.3,
        "allow_pyramid": True
    },
    "ETHUSDT": {
        "signal_threshold": 0.5,
        "confidence_required": 65,
        "timeframe_agreement": 0.5,
        "allow_pyramid": False,
        "btc_correlation_check": True
    },
    "XRPUSDT": {
        "signal_threshold": 0.6,
        "confidence_required": 70,
        "timeframe_agreement": 0.6,
        "allow_pyramid": False,
        "btc_correlation_check": True,
        "extreme_rsi_only": True
    }
})

# Risk Management
STOP_LOSS: Dict[str, float] = field(default_factory=lambda: {
    "BTCUSDT": 0.02,   # 2%
    "ETHUSDT": 0.015,  # 1.5%
    "XRPUSDT": 0.012   # 1.2%
})

TAKE_PROFIT: Dict[str, List[Tuple[float, float]]] = field(default_factory=lambda: {
    "BTCUSDT": [(0.03, 0.3), (0.05, 0.3), (0.08, 0.4)],
    "ETHUSDT": [(0.025, 0.5), (0.04, 0.5)],
    "XRPUSDT": [(0.02, 0.7), (0.03, 0.3)]
})

TRAILING_STOP: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
    "BTCUSDT": {"activate": 0.025, "distance": 0.012},
    "ETHUSDT": {"activate": 0.02, "distance": 0.01},
    "XRPUSDT": {"activate": 0.015, "distance": 0.008}
})

# Timeframe Settings
TIMEFRAMES: Dict[str, str] = field(default_factory=lambda: {
    '5m': 'five_minutes',
    '15m': 'fifteen_minutes',
    '30m': 'thirty_minutes',
    '1h': 'one_hour',
    '4h': 'four_hours'
})

# Timeframe Weights by Symbol
TIMEFRAME_WEIGHTS: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
    "BTCUSDT": {'4h': 0.5, '1h': 0.3, '15m': 0.2},
    "ETHUSDT": {'1h': 0.5, '30m': 0.3, '15m': 0.2},
    "XRPUSDT": {'1h': 0.6, '30m': 0.4}
})

# Trading Limits
DAILY_TRADE_LIMITS: Dict[str, Dict[str, int]] = field(default_factory=lambda: {
    "BTCUSDT": {"max_trades": 10, "max_loss_trades": 3, "cooldown_minutes": 30},
    "ETHUSDT": {"max_trades": 3, "max_loss_trades": 1, "cooldown_minutes": 120},
    "XRPUSDT": {"max_trades": 2, "max_loss_trades": 1, "cooldown_minutes": 240}
})

# Fee Configuration
MAKER_FEE: float = 0.0002  # 0.02%
TAKER_FEE: float = 0.0006  # 0.06%

# Performance Targets
DAILY_LOSS_LIMIT: float = 0.05  # 5%
WEEKLY_LOSS_LIMIT: float = 0.15  # 15%
MONTHLY_TARGET: float = 0.40  # 40%
MAX_DRAWDOWN: float = 0.20  # 20%

# System Settings
TIMEZONE: str = "Asia/Seoul"
DATABASE_PATH: str = "advanced_trading_v2.db"
REDIS_HOST: str = "localhost"
REDIS_PORT: int = 6379
LOG_LEVEL: str = "INFO"
USE_WEBSOCKET: bool = True
ENABLE_BACKTESTING: bool = True
ENABLE_ML_MODELS: bool = True
MAX_RETRIES: int = 3
RETRY_DELAY: int = 5

# WebSocket URLs
BITGET_WS_URL: str = "wss://ws.bitget.com/mix/v1/stream"

# Cache Settings
CACHE_TTL: int = 60  # seconds
INDICATOR_CACHE_SIZE: int = 1000

def validate(self) -> list:
    """Check for missing essential configuration"""
    required_fields = [
        'BITGET_API_KEY',
        'BITGET_SECRET_KEY',
        'BITGET_PASSPHRASE'
    ]
    missing = []
    for field_name in required_fields:
        if not getattr(self, field_name, None):
            missing.append(field_name)
    return missing

# ==============================
# Error Handling
# ==============================

    def validate(self) -> list:
        """Check for missing essential configuration"""
        required_fields = ['BITGET_API_KEY', 'BITGET_SECRET_KEY', 'BITGET_PASSPHRASE']
        missing = [f for f in required_fields if not getattr(self, f, None)]
        return missing

    @classmethod
    def from_env(cls, env_path: str = ".env") -> 'TradingConfig':
        """Load configuration from environment"""
        load_dotenv(env_path)
        config = cls()
        config.BITGET_API_KEY = os.getenv("BITGET_API_KEY", "")
        config.BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY", "")
        config.BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE", "")
        config.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        config.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        config.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
        return config

class TradingError(Exception):
   """Base trading error"""
pass
class ExchangeError(TradingError):
   """Exchange related errors"""
pass
class RiskLimitError(TradingError):
   """Risk limit exceeded"""
pass
class DataError(TradingError):
   """Data related errors"""
pass
# ==============================
# Enhanced Database Manager
# ==============================
class EnhancedDatabaseManager:
   """Database manager with complete implementation"""
def __init__(self, db_path: str):
    self.db_path = db_path
    self._init_database()
    self._init_redis()
    self._lock = threading.Lock()

def _init_redis(self):
    """Initialize Redis for caching"""
    try:
        self.redis_client = redis.Redis(
            host='localhost', 
            port=6379, 
            decode_responses=True,
            socket_connect_timeout=5
        )
        self.redis_client.ping()
        self.redis_enabled = True
    except:
        self.redis_enabled = False
        logging.warning("Redis not available, using memory cache")
        self.memory_cache = TTLCache(maxsize=1000, ttl=300)

def _init_database(self):
    """Initialize all database tables"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        # Enhanced predictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                price REAL NOT NULL,
                prediction REAL NOT NULL,
                confidence REAL NOT NULL,
                direction TEXT NOT NULL,
                model_predictions TEXT,
                technical_score REAL,
                news_sentiment REAL,
                multi_tf_score REAL,
                regime TEXT,
                executed BOOLEAN DEFAULT FALSE,
                actual_price REAL,
                actual_change REAL,
                direction_hit BOOLEAN,
                magnitude_hit BOOLEAN,
                indicators_snapshot TEXT,
                INDEX idx_symbol_timestamp (symbol, timestamp)
            )
        """)
        
        # Enhanced trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                leverage INTEGER NOT NULL,
                order_id TEXT,
                status TEXT DEFAULT 'pending',
                pnl REAL,
                pnl_percent REAL,
                close_price REAL,
                close_time DATETIME,
                reason TEXT,
                multi_tf_score REAL,
                regime TEXT,
                entry_signal_strength REAL,
                max_profit REAL,
                max_loss REAL,
                hold_duration INTEGER,
                trailing_stop_activated BOOLEAN DEFAULT FALSE,
                fees_paid REAL DEFAULT 0,
                slippage REAL DEFAULT 0,
                INDEX idx_status (status),
                INDEX idx_symbol_timestamp (symbol, timestamp)
            )
        """)
        
        # Position tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                trade_id INTEGER,
                entry_price REAL NOT NULL,
                current_price REAL,
                quantity REAL NOT NULL,
                side TEXT NOT NULL,
                stop_loss REAL,
                take_profit TEXT,
                trailing_stop_active BOOLEAN DEFAULT FALSE,
                trailing_stop_price REAL,
                max_profit REAL DEFAULT 0,
                status TEXT DEFAULT 'open',
                last_update DATETIME DEFAULT CURRENT_TIMESTAMP,
                stop_order_id TEXT,
                tp_order_ids TEXT,
                FOREIGN KEY (trade_id) REFERENCES trades(id),
                INDEX idx_status (status),
                INDEX idx_symbol (symbol)
            )
        """)
        
        # Daily performance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_performance (
                date DATE PRIMARY KEY,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                total_pnl_percent REAL DEFAULT 0,
                btc_pnl REAL DEFAULT 0,
                eth_pnl REAL DEFAULT 0,
                xrp_pnl REAL DEFAULT 0,
                max_drawdown REAL DEFAULT 0,
                sharpe_ratio REAL,
                win_rate REAL,
                avg_win REAL,
                avg_loss REAL,
                best_trade REAL,
                worst_trade REAL,
                total_volume REAL DEFAULT 0,
                total_fees REAL DEFAULT 0
            )
        """)
        
        # Indicator values cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indicator_cache (
                symbol TEXT,
                timeframe TEXT,
                indicator TEXT,
                value REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, timeframe, indicator)
            )
        """)
        
        # System logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                level TEXT,
                component TEXT,
                message TEXT,
                details TEXT
            )
        """)
        
        conn.commit()

@contextmanager
def _get_connection(self):
    """Database connection context manager with thread safety"""
    with self._lock:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

def cache_set(self, key: str, value: Any, ttl: int = 300):
    """Set cache value with error handling"""
    try:
        if self.redis_enabled:
            self.redis_client.setex(key, ttl, json.dumps(value))
        else:
            self.memory_cache[key] = value
    except Exception as e:
        logging.error(f"Cache set error: {e}")

def cache_get(self, key: str) -> Optional[Any]:
    """Get cache value with error handling"""
    try:
        if self.redis_enabled:
            value = self.redis_client.get(key)
            return json.loads(value) if value else None
        else:
            return self.memory_cache.get(key)
    except Exception as e:
        logging.error(f"Cache get error: {e}")
        return None

def save_prediction_with_indicators(self, prediction_data: Dict) -> int:
    """Save prediction with indicator snapshot"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions 
            (symbol, timeframe, price, prediction, confidence, direction, 
             model_predictions, technical_score, news_sentiment, multi_tf_score, 
             regime, indicators_snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction_data['symbol'],
            prediction_data['timeframe'],
            prediction_data['price'],
            prediction_data['prediction'],
            prediction_data['confidence'],
            prediction_data['direction'],
            json.dumps(prediction_data.get('model_predictions', {})),
            prediction_data.get('technical_score', 0),
            prediction_data.get('news_sentiment', 0),
            prediction_data.get('multi_tf_score', 0),
            prediction_data.get('regime', 'unknown'),
            json.dumps(prediction_data.get('indicators', {}))
        ))
        return cursor.lastrowid

def save_trade(self, trade_data: Dict) -> int:
    """Save new trade"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        columns = list(trade_data.keys())
        values = list(trade_data.values())
        placeholders = ', '.join(['?' for _ in columns])
        
        cursor.execute(f"""
            INSERT INTO trades ({', '.join(columns)})
            VALUES ({placeholders})
        """, values)
        
        return cursor.lastrowid

def update_trade(self, trade_id: int, update_data: Dict):
    """Update trade data"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        set_clauses = []
        values = []
        for key, value in update_data.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)
        
        values.append(trade_id)
        
        cursor.execute(f"""
            UPDATE trades 
            SET {', '.join(set_clauses)}
            WHERE id = ?
        """, values)

def save_position(self, position_data: Dict) -> int:
    """Save new position"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO positions 
            (symbol, trade_id, entry_price, quantity, side, stop_loss, take_profit)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            position_data['symbol'],
            position_data['trade_id'],
            position_data['entry_price'],
            position_data['quantity'],
            position_data['side'],
            position_data['stop_loss'],
            json.dumps(position_data['take_profit'])
        ))
        return cursor.lastrowid

def update_position(self, position_id: int, update_data: Dict):
    """Update position data"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        set_clauses = []
        values = []
        for key, value in update_data.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)
        
        values.append(datetime.now())
        values.append(position_id)
        
        cursor.execute(f"""
            UPDATE positions 
            SET {', '.join(set_clauses)}, last_update = ?
            WHERE id = ?
        """, values)

def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
    """Get open positions"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM positions WHERE status = 'open'"
        if symbol:
            query += f" AND symbol = ?"
            cursor.execute(query, (symbol,))
        else:
            cursor.execute(query)
        
        return [dict(row) for row in cursor.fetchall()]

def get_daily_performance(self, date: Optional[str] = None) -> Dict:
    """Get daily performance stats"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("SELECT * FROM daily_performance WHERE date = ?", (date,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        else:
            return self._get_default_daily_performance()

def update_daily_performance(self, date: str, performance_data: Dict):
    """Update daily performance"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if record exists
        cursor.execute("SELECT date FROM daily_performance WHERE date = ?", (date,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing
            set_clauses = []
            values = []
            for key, value in performance_data.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)
            values.append(date)
            
            cursor.execute(f"""
                UPDATE daily_performance 
                SET {', '.join(set_clauses)}
                WHERE date = ?
            """, values)
        else:
            # Insert new
            performance_data['date'] = date
            columns = list(performance_data.keys())
            values = list(performance_data.values())
            placeholders = ', '.join(['?' for _ in columns])
            
            cursor.execute(f"""
                INSERT INTO daily_performance ({', '.join(columns)})
                VALUES ({placeholders})
            """, values)

def get_symbol_trades_today(self, symbol: str) -> Dict[str, int]:
    """Get today's trade count for a symbol"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Total trades
        cursor.execute("""
            SELECT COUNT(*) as total FROM trades 
            WHERE symbol = ? AND DATE(timestamp) = ?
        """, (symbol, today))
        total = cursor.fetchone()['total']
        
        # Loss trades
        cursor.execute("""
            SELECT COUNT(*) as losses FROM trades 
            WHERE symbol = ? AND DATE(timestamp) = ? AND pnl < 0
        """, (symbol, today))
        losses = cursor.fetchone()['losses']
        
        # Last trade time
        cursor.execute("""
            SELECT MAX(timestamp) as last_trade FROM trades 
            WHERE symbol = ? AND DATE(timestamp) = ?
        """, (symbol, today))
        last_trade = cursor.fetchone()['last_trade']
        
        return {
            'total': total, 
            'losses': losses,
            'last_trade': last_trade
        }

def log_system_event(self, level: str, component: str, message: str, details: Dict = None):
    """Log system events"""
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_logs (level, component, message, details)
            VALUES (?, ?, ?, ?)
        """, (level, component, message, json.dumps(details or {})))

def _get_default_daily_performance(self) -> Dict:
    """Default daily performance structure"""
    return {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'total_pnl': 0.0,
        'total_pnl_percent': 0.0,
        'btc_pnl': 0.0,
        'eth_pnl': 0.0,
        'xrp_pnl': 0.0,
        'max_drawdown': 0.0,
        'sharpe_ratio': 0.0,
        'win_rate': 0.0,
        'avg_win': 0.0,
        'avg_loss': 0.0,
        'best_trade': 0.0,
        'worst_trade': 0.0,
        'total_volume': 0.0,
        'total_fees': 0.0
    }
# ==============================
# Enhanced Exchange Manager with WebSocket
# ==============================
class EnhancedBitgetExchangeManager:
   """Bitget exchange manager with complete WebSocket implementation"""
def __init__(self, config: TradingConfig):
    self.config = config
    self.exchange = ccxt.bitget({
        'apiKey': config.BITGET_API_KEY,
        'secret': config.BITGET_SECRET_KEY,
        'password': config.BITGET_PASSPHRASE,
        'enableRateLimit': True,
        'rateLimit': 50,
        'options': {
            'defaultType': 'swap',
            'adjustForTimeDifference': True
        }
    })
    self.logger = logging.getLogger(__name__)
    
    # WebSocket data
    self.ws_connected = False
    self.price_data = {}
    self.orderbook_data = {}
    self.ws_task = None
    self.ws_reconnect_attempts = 0
    
    # Circuit breaker
    self.error_count = 0
    self.max_errors = 5
    self.last_error_time = None
    
    # Cache
    self.cache = TTLCache(maxsize=config.INDICATOR_CACHE_SIZE, ttl=config.CACHE_TTL)
    
    # Rate limiting
    self.rate_limiter = self._create_rate_limiter()

def _create_rate_limiter(self):
    """Create rate limiter"""
    return {
        'calls': deque(maxlen=30),
        'max_calls': 30,
        'time_window': 60
    }

async def _check_rate_limit(self):
    """Check and enforce rate limits"""
    current_time = time.time()
    
    # Remove old calls
    while self.rate_limiter['calls'] and self.rate_limiter['calls'][0] < current_time - self.rate_limiter['time_window']:
        self.rate_limiter['calls'].popleft()
    
    # Check if limit exceeded
    if len(self.rate_limiter['calls']) >= self.rate_limiter['max_calls']:
        sleep_time = self.rate_limiter['calls'][0] + self.rate_limiter['time_window'] - current_time
        if sleep_time > 0:
            self.logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
    
    # Add current call
    self.rate_limiter['calls'].append(current_time)

async def initialize(self):
    """Initialize exchange connection"""
    try:
        # Test connection
        await self.get_balance()
        
        # Start WebSocket if enabled
        if self.config.USE_WEBSOCKET:
            self.ws_task = asyncio.create_task(self._websocket_manager())
            
        self.logger.info("Exchange manager initialized successfully")
        
    except Exception as e:
        self.logger.error(f"Failed to initialize exchange: {e}")
        raise

async def _websocket_manager(self):
    """Manage WebSocket connection with auto-reconnect"""
    while True:
        try:
            await self._connect_websocket()
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
            self.ws_reconnect_attempts += 1
            
            # Exponential backoff
            wait_time = min(300, 5 * (2 ** self.ws_reconnect_attempts))
            await asyncio.sleep(wait_time)

async def _connect_websocket(self):
    """Connect to Bitget WebSocket"""
    self.logger.info("Connecting to Bitget WebSocket...")
    
    try:
        async with websockets.connect(self.config.BITGET_WS_URL) as websocket:
            self.ws_connected = True
            self.ws_reconnect_attempts = 0
            self.logger.info("WebSocket connected successfully")
            
            # Subscribe to channels
            await self._subscribe_channels(websocket)
            
            # Handle messages
            async for message in websocket:
                await self._handle_ws_message(message)
                
    except Exception as e:
        self.ws_connected = False
        self.logger.error(f"WebSocket connection error: {e}")
        raise

async def _subscribe_channels(self, websocket):
    """Subscribe to WebSocket channels"""
    for symbol in self.config.SYMBOLS:
        # Subscribe to ticker
        subscribe_msg = {
            "op": "subscribe",
            "args": [{
                "instType": "mc",
                "channel": "ticker",
                "instId": symbol
            }]
        }
        await websocket.send(json.dumps(subscribe_msg))
        
        # Subscribe to orderbook
        subscribe_msg = {
            "op": "subscribe",
            "args": [{
                "instType": "mc",
                "channel": "books5",
                "instId": symbol
            }]
        }
        await websocket.send(json.dumps(subscribe_msg))

async def _handle_ws_message(self, message: str):
    """Handle WebSocket message"""
    try:
        data = json.loads(message)
        
        if data.get('event') == 'error':
            self.logger.error(f"WebSocket error: {data}")
            return
        
        if 'data' in data:
            for item in data['data']:
                if data.get('arg', {}).get('channel') == 'ticker':
                    symbol = item.get('instId')
                    self.price_data[symbol] = {
                        'last': float(item.get('last', 0)),
                        'bid': float(item.get('bidPx', 0)),
                        'ask': float(item.get('askPx', 0)),
                        'volume': float(item.get('vol24h', 0)),
                        'timestamp': int(item.get('ts', 0))
                    }
                
                elif data.get('arg', {}).get('channel') == 'books5':
                    symbol = item.get('instId')
                    self.orderbook_data[symbol] = {
                        'bids': item.get('bids', []),
                        'asks': item.get('asks', []),
                        'timestamp': int(item.get('ts', 0))
                    }
                    
    except Exception as e:
        self.logger.error(f"Error handling WebSocket message: {e}")

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
async def fetch_ohlcv_with_cache(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
    """Fetch OHLCV with caching and retry"""
    cache_key = f"ohlcv:{symbol}:{timeframe}"
    
    # Check cache first
    cached = self.cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Fetch from exchange
    df = await self.fetch_ohlcv(symbol, timeframe, limit)
    
    # Cache if successful
    if df is not None and not df.empty:
        self.cache[cache_key] = df
    
    return df

async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
    """Fetch OHLCV data with error handling"""
    await self._check_rate_limit()
    
    try:
        market_symbol = self._format_symbol(symbol)
        
        ohlcv = await asyncio.get_event_loop().run_in_executor(
            None,
            self.exchange.fetch_ohlcv,
            market_symbol,
            timeframe,
            None,
            limit
        )
        
        if not ohlcv:
            return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # Reset error count on success
        self.error_count = 0
        
        return df
        
    except Exception as e:
        self._handle_error(e)
        return pd.DataFrame()

def _handle_error(self, error: Exception):
    """Handle errors with circuit breaker"""
    self.error_count += 1
    self.last_error_time = datetime.now()
    
    if self.error_count >= self.max_errors:
        self.logger.critical(f"Circuit breaker triggered after {self.max_errors} errors")
        raise ExchangeError("Exchange circuit breaker triggered")
    
    self.logger.error(f"Exchange error ({self.error_count}/{self.max_errors}): {error}")

async def get_balance(self) -> Dict:
    """Get account balance"""
    await self._check_rate_limit()
    
    try:
        balance = await asyncio.get_event_loop().run_in_executor(
            None,
            self.exchange.fetch_balance
        )
        self.error_count = 0
        return balance
    except Exception as e:
        self._handle_error(e)
        return {}

async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
    """Get open positions"""
    await self._check_rate_limit()
    
    try:
        positions = await asyncio.get_event_loop().run_in_executor(
            None,
            self.exchange.fetch_positions,
            [self._format_symbol(symbol)] if symbol else None
        )
        self.error_count = 0
        return positions
    except Exception as e:
        self._handle_error(e)
        return []

async def place_order(self, symbol: str, side: str, amount: float, 
                     order_type: str = 'market', price: Optional[float] = None,
                     params: Optional[Dict] = None) -> Dict:
    """Place order with enhanced parameters"""
    await self._check_rate_limit()
    
    try:
        market_symbol = self._format_symbol(symbol)
        
        # Set leverage
        leverage = self.config.LEVERAGE.get(symbol, 10)
        await self.set_leverage(symbol, leverage)
        
        # Calculate slippage for market orders
        if order_type == 'market' and self.ws_connected:
            price_data = self.price_data.get(symbol, {})
            if side == 'buy' and 'ask' in price_data:
                estimated_price = price_data['ask']
            elif side == 'sell' and 'bid' in price_data:
                estimated_price = price_data['bid']
            else:
                estimated_price = price_data.get('last', price)
        else:
            estimated_price = price
        
        # Place order
        order = await asyncio.get_event_loop().run_in_executor(
            None,
            self.exchange.create_order,
            market_symbol,
            order_type,
            side,
            amount,
            price,
            params or {}
        )
        
        # Calculate actual slippage
        if order_type == 'market' and estimated_price:
            actual_price = order.get('price', estimated_price)
            slippage = abs(actual_price - estimated_price) / estimated_price
            order['slippage'] = slippage
        
        self.error_count = 0
        self.logger.info(f"Order placed: {symbol} {side} {amount} @ {price or 'market'}")
        return order
        
    except Exception as e:
        self._handle_error(e)
        return {}

async def place_stop_loss_order(self, symbol: str, side: str, amount: float, 
                               stop_price: float) -> Dict:
    """Place stop loss order"""
    params = {
        'stopPrice': stop_price,
        'triggerType': 'market_price',
        'timeInForce': 'GTC'
    }
    
    return await self.place_order(
        symbol, 
        side, 
        amount, 
        order_type='stop',
        params=params
    )

async def modify_stop_loss(self, symbol: str, order_id: str, new_stop_price: float) -> Dict:
    """Modify existing stop loss order"""
    await self._check_rate_limit()
    
    try:
        market_symbol = self._format_symbol(symbol)
        
        # Cancel old order
        await asyncio.get_event_loop().run_in_executor(
            None,
            self.exchange.cancel_order,
            order_id,
            market_symbol
        )
        
        # Get position to determine side and amount
        positions = await self.get_positions(symbol)
        if positions:
            position = positions[0]
            side = 'sell' if position['side'] == 'long' else 'buy'
            amount = position['contracts']
            
            # Place new stop loss
            return await self.place_stop_loss_order(symbol, side, amount, new_stop_price)
        
        return {}
        
    except Exception as e:
        self.logger.error(f"Failed to modify stop loss: {e}")
        return {}

async def close_position(self, symbol: str, reason: str = "manual") -> Dict:
    """Close position with reason"""
    try:
        positions = await self.get_positions(symbol)
        
        for position in positions:
            if position['contracts'] > 0:
                side = 'sell' if position['side'] == 'long' else 'buy'
                amount = position['contracts']
                
                order = await self.place_order(symbol, side, amount)
                
                self.logger.info(f"Position closed: {symbol} - Reason: {reason}")
                return order
        
        return {}
        
    except Exception as e:
        self._handle_error(e)
        return {}

async def set_leverage(self, symbol: str, leverage: int):
    """Set leverage for symbol"""
    await self._check_rate_limit()
    
    try:
        market_symbol = self._format_symbol(symbol)
        
        await asyncio.get_event_loop().run_in_executor(
            None,
            self.exchange.set_leverage,
            leverage,
            market_symbol
        )
        
        self.error_count = 0
        
    except Exception as e:
        self.logger.error(f"Failed to set leverage: {e}")

def _format_symbol(self, symbol: str) -> str:
    """Format symbol for Bitget"""
    # BTCUSDT -> BTC/USDT:USDT
    base = symbol[:-4]
    return f"{base}/USDT:USDT"

async def calculate_position_size(self, symbol: str, position_value: float) -> float:
    """Calculate position size in contracts"""
    try:
        # Use WebSocket price if available
        if self.ws_connected and symbol in self.price_data:
            current_price = self.price_data[symbol]['last']
        else:
            ticker = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_ticker,
                self._format_symbol(symbol)
            )
            current_price = ticker['last']
        
        contract_size = self._get_contract_size(symbol)
        contracts = position_value / (current_price * contract_size)
        
        return round(contracts, self._get_precision(symbol))
        
    except Exception as e:
        self.logger.error(f"Failed to calculate position size: {e}")
        return 0

def _get_contract_size(self, symbol: str) -> float:
    """Get contract size for symbol"""
    contract_sizes = {
        "BTCUSDT": 0.001,
        "ETHUSDT": 0.01,
        "XRPUSDT": 1
    }
    return contract_sizes.get(symbol, 0.01)

def _get_precision(self, symbol: str) -> int:
    """Get precision for symbol"""
    precisions = {
        "BTCUSDT": 3,
        "ETHUSDT": 2,
        "XRPUSDT": 0
    }
    return precisions.get(symbol, 2)

def get_current_price(self, symbol: str) -> Optional[float]:
    """Get current price from WebSocket or cache"""
    if self.ws_connected and symbol in self.price_data:
        return self.price_data[symbol]['last']
    return None
[Continue with remaining components in next part due to length limit...]
</artifact>
<artifact identifier="trading-system-part2" type="application/vnd.ant.code" language="python" title="Complete Trading System - Part 2">

class EnhancedTechnicalIndicators:
    """Comprehensive technical indicators library with caching"""
_cache = TTLCache(maxsize=1000, ttl=60)

@classmethod
@lru_cache(maxsize=128)
def _calculate_cached_indicator(cls, data_hash: str, indicator_name: str, *args, **kwargs):
    """Cache wrapper for indicator calculations"""
    return None  # Will be overridden by actual calculations

@classmethod
def calculate_all_indicators(cls, df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate all technical indicators with caching"""
    # Create hash of dataframe for caching
    df_hash = hashlib.md5(pd.util.hash_pandas_object(df).values).hexdigest()
    
    indicators = {}
    
    # Trend Indicators
    indicators['sma_20'] = talib.SMA(df['close'], timeperiod=20)
    indicators['sma_50'] = talib.SMA(df['close'], timeperiod=50)
    indicators['sma_200'] = talib.SMA(df['close'], timeperiod=200)
    indicators['ema_20'] = talib.EMA(df['close'], timeperiod=20)
    indicators['ema_50'] = talib.EMA(df['close'], timeperiod=50)
    
    # MACD
    indicators['macd'], indicators['macd_signal'], indicators['macd_hist'] = talib.MACD(
        df['close'], fastperiod=12, slowperiod=26, signalperiod=9
    )
    
    # RSI with multiple periods
    indicators['rsi'] = talib.RSI(df['close'], timeperiod=14)
    indicators['rsi_6'] = talib.RSI(df['close'], timeperiod=6)
    indicators['rsi_24'] = talib.RSI(df['close'], timeperiod=24)
    
    # Stochastic RSI
    indicators['stoch_rsi'], indicators['stoch_rsi_d'] = talib.STOCHRSI(
        df['close'], timeperiod=14, fastk_period=3, fastd_period=3
    )
    
    # Bollinger Bands
    indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = talib.BBANDS(
        df['close'], timeperiod=20, nbdevup=2, nbdevdn=2
    )
    
    # Keltner Channels
    indicators['kc_upper'], indicators['kc_middle'], indicators['kc_lower'] = cls.calculate_keltner_channels(df)
    
    # ATR
    indicators['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    indicators['atr_percent'] = indicators['atr'] / df['close'] * 100
    
    # ADX
    indicators['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
    indicators['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
    indicators['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
    
    # Volume Indicators
    indicators['obv'] = talib.OBV(df['close'], df['volume'])
    indicators['volume_sma'] = talib.SMA(df['volume'], timeperiod=20)
    indicators['volume_ratio'] = df['volume'] / indicators['volume_sma']
    
    # MFI
    indicators['mfi'] = talib.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)
    
    # Ichimoku Cloud
    ichimoku = cls.calculate_ichimoku(df)
    indicators.update(ichimoku)
    
    # VWAP
    indicators['vwap'] = cls.calculate_vwap(df)
    
    # CMF
    indicators['cmf'] = cls.calculate_cmf(df)
    
    # Supertrend
    indicators['supertrend'], indicators['supertrend_direction'] = cls.calculate_supertrend(df)
    
    # Custom indicators
    indicators['price_position'] = cls.calculate_price_position(df, indicators)
    indicators['trend_strength'] = cls.calculate_trend_strength(indicators)
    indicators['volatility_ratio'] = cls.calculate_volatility_ratio(df, indicators)
    
    return indicators

@staticmethod
def calculate_keltner_channels(df: pd.DataFrame, period: int = 20, multiplier: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Keltner Channels"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    middle = talib.EMA(typical_price, timeperiod=period)
    atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
    
    upper = middle + (multiplier * atr)
    lower = middle - (multiplier * atr)
    
    return upper, middle, lower

@staticmethod
def calculate_ichimoku(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """Calculate Ichimoku Cloud"""
    high_9 = df['high'].rolling(window=9).max()
    low_9 = df['low'].rolling(window=9).min()
    tenkan_sen = (high_9 + low_9) / 2
    
    high_26 = df['high'].rolling(window=26).max()
    low_26 = df['low'].rolling(window=26).min()
    kijun_sen = (high_26 + low_26) / 2
    
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
    
    high_52 = df['high'].rolling(window=52).max()
    low_52 = df['low'].rolling(window=52).min()
    senkou_span_b = ((high_52 + low_52) / 2).shift(26)
    
    chikou_span = df['close'].shift(-26)
    
    return {
        'ichimoku_tenkan': tenkan_sen,
        'ichimoku_kijun': kijun_sen,
        'ichimoku_senkou_a': senkou_span_a,
        'ichimoku_senkou_b': senkou_span_b,
        'ichimoku_chikou': chikou_span,
        'ichimoku_cloud_top': pd.Series(np.maximum(senkou_span_a, senkou_span_b)),
        'ichimoku_cloud_bottom': pd.Series(np.minimum(senkou_span_a, senkou_span_b))
    }

@staticmethod
def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculate VWAP"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

@staticmethod
def calculate_cmf(df: pd.DataFrame, period: int = 21) -> pd.Series:
    """Calculate Chaikin Money Flow"""
    mf_multiplier = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
    mf_multiplier = mf_multiplier.fillna(0)
    mf_volume = mf_multiplier * df['volume']
    
    cmf = mf_volume.rolling(window=period).sum() / df['volume'].rolling(window=period).sum()
    return cmf

@staticmethod
def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    """Calculate Supertrend"""
    hl_avg = (df['high'] + df['low']) / 2
    atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
    
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)
    
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)
    
    for i in range(period, len(df)):
        if df['close'].iloc[i] <= upper_band.iloc[i]:
            supertrend.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = -1
        else:
            supertrend.iloc[i] = lower_band.iloc[i]
            direction.iloc[i] = 1
            
        if i > period:
            if direction.iloc[i] == 1:
                if supertrend.iloc[i] < supertrend.iloc[i-1]:
                    supertrend.iloc[i] = supertrend.iloc[i-1]
            else:
                if supertrend.iloc[i] > supertrend.iloc[i-1]:
                    supertrend.iloc[i] = supertrend.iloc[i-1]
    
    return supertrend, direction

@staticmethod
def calculate_price_position(df: pd.DataFrame, indicators: Dict) -> pd.Series:
    """Calculate price position relative to key levels"""
    current_price = df['close']
    
    # Calculate position between 0 and 1
    position = pd.Series(index=df.index, dtype=float)
    
    # Bollinger Band position
    bb_position = (current_price - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
    
    # Moving average position
    ma_range = indicators['sma_200'] - indicators['sma_20']
    ma_position = (current_price - indicators['sma_20']) / ma_range.replace(0, 1)
    
    # Combine positions
    position = (bb_position + ma_position) / 2
    
    return position.clip(0, 1)

@staticmethod
def calculate_trend_strength(indicators: Dict) -> pd.Series:
    """Calculate overall trend strength"""
    # ADX-based trend strength
    adx_strength = indicators['adx'] / 100
    
    # Moving average alignment
    ma_alignment = pd.Series(index=indicators['sma_20'].index, dtype=float)
    ma_alignment[(indicators['ema_20'] > indicators['ema_50']) & 
                (indicators['ema_50'] > indicators['sma_200'])] = 1
    ma_alignment[(indicators['ema_20'] < indicators['ema_50']) & 
                (indicators['ema_50'] < indicators['sma_200'])] = -1
    ma_alignment.fillna(0, inplace=True)
    
    # MACD strength
    macd_strength = np.sign(indicators['macd']) * np.minimum(np.abs(indicators['macd']) / indicators['macd'].std(), 1)
    
    # Combine
    trend_strength = (adx_strength + np.abs(ma_alignment) + np.abs(macd_strength)) / 3
    
    return trend_strength.clip(0, 1)

@staticmethod
def calculate_volatility_ratio(df: pd.DataFrame, indicators: Dict) -> pd.Series:
    """Calculate volatility ratio"""
    # ATR-based volatility
    atr_ratio = indicators['atr'] / df['close']
    
    # Bollinger Band width
    bb_width = (indicators['bb_upper'] - indicators['bb_lower']) / indicators['bb_middle']
    
    # Historical volatility
    returns = df['close'].pct_change()
    hist_vol = returns.rolling(window=20).std()
    
    # Combine
    volatility_ratio = (atr_ratio + bb_width + hist_vol) / 3
    
    return volatility_ratio
# ==============================
# Trading Strategies (Continued from Part 1)
# ==============================
[BTCTradingStrategy, ETHTradingStrategy, XRPTradingStrategy remain the same as in original code]
# ==============================
# Enhanced Risk Manager
# ==============================
class RiskManager:
"""Comprehensive risk management system with enhanced checks"""
def __init__(self, config: TradingConfig, db: EnhancedDatabaseManager):
    self.config = config
    self.db = db
    self.logger = logging.getLogger(__name__)
    
    # Track risk metrics
    self.risk_metrics = {
        'daily_pnl': 0,
        'weekly_pnl': 0,
        'peak_equity': 0,
        'current_drawdown': 0,
        'correlation_matrix': {}
    }

async def check_risk_limits(self, symbol: str) -> Dict[str, bool]:
    """Check all risk limits before trading"""
    checks = {
        'daily_loss': await self._check_daily_loss_limit(),
        'weekly_loss': await self._check_weekly_loss_limit(),
        'symbol_trades': await self._check_symbol_trade_limits(symbol),
        'position_limits': await self._check_position_limits(symbol),
        'correlation': await self._check_correlation_limits(),
        'drawdown': await self._check_drawdown_limit(),
        'cooldown': await self._check_cooldown_period(symbol),
        'market_conditions': await self._check_market_conditions()
    }
    
    # Overall decision
    can_trade = all(checks.values())
    
    if not can_trade:
        failed_checks = [k for k, v in checks.items() if not v]
        self.logger.warning(f"Risk checks failed for {symbol}: {failed_checks}")
        self.db.log_system_event('WARNING', 'RiskManager', 
                               f"Risk checks failed for {symbol}", 
                               {'failed_checks': failed_checks})
    
    return {
        'can_trade': can_trade,
        'checks': checks
    }

async def _check_daily_loss_limit(self) -> bool:
    """Check if daily loss limit exceeded"""
    today_performance = self.db.get_daily_performance()
    
    if today_performance['total_pnl_percent'] <= -self.config.DAILY_LOSS_LIMIT:
        self.logger.warning(f"Daily loss limit reached: {today_performance['total_pnl_percent']:.2%}")
        return False
    
    return True

async def _check_weekly_loss_limit(self) -> bool:
    """Check weekly loss limit"""
    # Get last 7 days performance
    weekly_pnl = 0
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        daily_perf = self.db.get_daily_performance(date)
        weekly_pnl += daily_perf.get('total_pnl_percent', 0)
    
    if weekly_pnl <= -self.config.WEEKLY_LOSS_LIMIT:
        self.logger.warning(f"Weekly loss limit reached: {weekly_pnl:.2%}")
        return False
    
    return True

async def _check_symbol_trade_limits(self, symbol: str) -> bool:
    """Check symbol-specific trade limits"""
    limits = self.config.DAILY_TRADE_LIMITS[symbol]
    today_trades = self.db.get_symbol_trades_today(symbol)
    
    # Check total trades
    if today_trades['total'] >= limits['max_trades']:
        self.logger.warning(f"{symbol} daily trade limit reached: {today_trades['total']}")
        return False
    
    # Check loss trades
    if today_trades['losses'] >= limits['max_loss_trades']:
        self.logger.warning(f"{symbol} daily loss limit reached: {today_trades['losses']}")
        return False
    
    return True

async def _check_cooldown_period(self, symbol: str) -> bool:
    """Check if in cooldown period"""
    limits = self.config.DAILY_TRADE_LIMITS[symbol]
    today_trades = self.db.get_symbol_trades_today(symbol)
    
    if today_trades['last_trade']:
        last_trade_time = datetime.fromisoformat(today_trades['last_trade'])
        cooldown_end = last_trade_time + timedelta(minutes=limits['cooldown_minutes'])
        
        if datetime.now() < cooldown_end:
            remaining = (cooldown_end - datetime.now()).seconds / 60
            self.logger.info(f"{symbol} in cooldown for {remaining:.1f} more minutes")
            return False
    
    return True

async def _check_position_limits(self, symbol: str) -> bool:
    """Check position limits"""
    open_positions = self.db.get_open_positions(symbol)
    max_positions = self.config.MAX_POSITIONS[symbol]
    
    if len(open_positions) >= max_positions:
        self.logger.warning(f"{symbol} position limit reached: {len(open_positions)}")
        return False
    
    return True

async def _check_correlation_limits(self) -> bool:
    """Check correlation between positions"""
    # Get all open positions
    all_positions = self.db.get_open_positions()
    
    if not all_positions:
        return True
    
    # Group by direction
    long_positions = [p for p in all_positions if p['side'] == 'long']
    short_positions = [p for p in all_positions if p['side'] == 'short']
    
    # Simple check: avoid all positions in same direction
    if len(long_positions) >= len(self.config.SYMBOLS) or len(short_positions) >= len(self.config.SYMBOLS):
        self.logger.warning("All positions in same direction, avoiding correlation risk")
        return False
    
    return True

async def _check_drawdown_limit(self) -> bool:
    """Check maximum drawdown"""
    # This would track peak equity and calculate drawdown
    # For now, simplified implementation
    today_performance = self.db.get_daily_performance()
    
    if today_performance['max_drawdown'] >= self.config.MAX_DRAWDOWN:
        self.logger.warning(f"Max drawdown reached: {today_performance['max_drawdown']:.2%}")
        return False
    
    return True

async def _check_market_conditions(self) -> bool:
    """Check overall market conditions"""
    # Could check VIX, funding rates, etc.
    # For now, always return True
    return True

def calculate_position_allocation(self, symbol: str, total_capital: float, 
                                current_positions: List[Dict]) -> float:
    """Calculate how much capital to allocate to a position"""
    # Base allocation
    symbol_allocation = self.config.PORTFOLIO_WEIGHTS[symbol]
    allocated_capital = total_capital * symbol_allocation
    
    # Adjust for existing positions
    symbol_positions = [p for p in current_positions if p['symbol'] == symbol]
    used_allocation = sum(p['quantity'] * p['entry_price'] for p in symbol_positions)
    
    remaining_allocation = allocated_capital - used_allocation
    
    # Ensure we don't over-allocate
    max_position_size = allocated_capital / self.config.MAX_POSITIONS[symbol]
    
    # Apply Kelly Criterion adjustment (simplified)
    win_rate = self._calculate_win_rate(symbol)
    avg_win = self._calculate_avg_win(symbol)
    avg_loss = self._calculate_avg_loss(symbol)
    
    if avg_loss != 0:
        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * abs(avg_loss)) / avg_win
        kelly_fraction = max(0, min(0.25, kelly_fraction))  # Cap at 25%
    else:
        kelly_fraction = 0.1
    
    adjusted_allocation = remaining_allocation * kelly_fraction
    
    return min(remaining_allocation, max_position_size, adjusted_allocation)

def _calculate_win_rate(self, symbol: str) -> float:
    """Calculate historical win rate for symbol"""
    # Would query historical trades
    # For now, return default
    return 0.55

def _calculate_avg_win(self, symbol: str) -> float:
    """Calculate average winning trade"""
    return 0.03  # 3%

def _calculate_avg_loss(self, symbol: str) -> float:
    """Calculate average losing trade"""
    return -0.02  # -2%
# ==============================
# Web Dashboard Frontend
# ==============================
# DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitget Trading System Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background-color: #0a0e27;
        color: #e4e4e7;
        line-height: 1.6;
    }
    
    .container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 20px;
    }
    
    .header {
        background: linear-gradient(135deg, #1a1f3a 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 30px;
        margin-bottom: 30px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    
    .header h1 {
        font-size: 2.5rem;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
    }
    
    .status-bar {
        display: flex;
        gap: 20px;
        flex-wrap: wrap;
    }
    
    .status-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
    }
    
    .status-indicator {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #10b981;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }
    
    .card {
        background: linear-gradient(135deg, #1a1f3a 0%, #0f172a 100%);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    }
    
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    
    .card-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #e0e7ff;
    }
    
    .balance {
        font-size: 2.5rem;
        font-weight: 700;
        color: #60a5fa;
        margin-bottom: 10px;
    }
    
    .profit {
        color: #10b981;
    }
    
    .loss {
        color: #ef4444;
    }
    
    .positions-table {
        width: 100%;
        border-collapse: collapse;
    }
    
    .positions-table th {
        text-align: left;
        padding: 12px;
        border-bottom: 2px solid rgba(255, 255, 255, 0.1);
        color: #9ca3af;
        font-weight: 500;
        font-size: 0.875rem;
        text-transform: uppercase;
    }
    
    .positions-table td {
        padding: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .positions-table tr:hover {
        background: rgba(255, 255, 255, 0.02);
    }
    
    .side-long {
        color: #10b981;
    }
    
    .side-short {
        color: #ef4444;
    }
    
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
    }
    
    .metric {
        background: rgba(255, 255, 255, 0.03);
        padding: 16px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #9ca3af;
        margin-bottom: 4px;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 600;
    }
    
    .chart-container {
        height: 300px;
        margin-top: 20px;
    }
    
    .activity-feed {
        max-height: 400px;
        overflow-y: auto;
    }
    
    .activity-item {
        padding: 12px;
        border-left: 3px solid #60a5fa;
        margin-bottom: 12px;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 0 8px 8px 0;
    }
    
    .activity-time {
        font-size: 0.875rem;
        color: #9ca3af;
    }
    
    .btn {
        padding: 10px 20px;
        border-radius: 8px;
        border: none;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        text-transform: uppercase;
        font-size: 0.875rem;
    }
    
    .btn-primary {
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        color: white;
    }
    
    .btn-primary:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(96, 165, 250, 0.4);
    }
    
    .loading {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(255, 255, 255, 0.2);
        border-radius: 50%;
        border-top-color: #60a5fa;
        animation: spin 1s ease-in-out infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Bitget Trading System</h1>
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-indicator"></div>
                    <span>시스템 정상</span>
                </div>
                <div class="status-item">
                    <span>서버 시간:</span>
                    <span id="server-time">--:--:--</span>
                </div>
                <div class="status-item">
                    <span>실행 시간:</span>
                    <span id="uptime">0시간 0분</span>
                </div>
            </div>
        </div>
    <div class="grid">
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">💰 계좌 현황</h2>
                <button class="btn btn-primary" onclick="refreshData()">
                    새로고침
                </button>
            </div>
            <div class="balance" id="total-balance">$0.00</div>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-label">일일 손익</div>
                    <div class="metric-value" id="daily-pnl">+0.00%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">총 포지션</div>
                    <div class="metric-value" id="total-positions">0</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">📊 성과 지표</h2>
            </div>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-label">승률</div>
                    <div class="metric-value" id="win-rate">0.0%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">샤프 비율</div>
                    <div class="metric-value" id="sharpe-ratio">0.00</div>
                </div>
                <div class="metric">
                    <div class="metric-label">최대 낙폭</div>
                    <div class="metric-value" id="max-drawdown">0.0%</div>
                </div>
                <div class="metric">
                    <div class="metric-label">일일 거래</div>
                    <div class="metric-value" id="daily-trades">0</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">📈 오픈 포지션</h2>
        </div>
        <table class="positions-table">
            <thead>
                <tr>
                    <th>심볼</th>
                    <th>방향</th>
                    <th>진입가</th>
                    <th>현재가</th>
                    <th>수량</th>
                    <th>손익</th>
                    <th>손익률</th>
                </tr>
            </thead>
            <tbody id="positions-tbody">
                <tr>
                    <td colspan="7" style="text-align: center; color: #9ca3af;">
                        포지션 없음
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
    
    <div class="grid">
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">🔔 실시간 활동</h2>
            </div>
            <div class="activity-feed" id="activity-feed">
                <div class="activity-item">
                    <div class="activity-time">시스템 시작됨</div>
                    <div>거래 시스템이 초기화되었습니다.</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">⚙️ 시스템 상태</h2>
            </div>
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-label">BTC 거래</div>
                    <div class="metric-value" id="btc-trades">0/10</div>
                </div>
                <div class="metric">
                    <div class="metric-label">ETH 거래</div>
                    <div class="metric-value" id="eth-trades">0/3</div>
                </div>
                <div class="metric">
                    <div class="metric-label">XRP 거래</div>
                    <div class="metric-value" id="xrp-trades">0/2</div>
                </div>
                <div class="metric">
                    <div class="metric-label">API 지연</div>
                    <div class="metric-value" id="api-latency">0ms</div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    let ws = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log('WebSocket connected');
            reconnectAttempts = 0;
            addActivity('WebSocket 연결됨');
        };
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        };
        
        ws.onclose = function() {
            console.log('WebSocket disconnected');
            addActivity('WebSocket 연결 끊김');
            
            if (reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++;
                setTimeout(connectWebSocket, 5000 * reconnectAttempts);
            }
        };
        
        ws.onerror = function(error) {
            console.error('WebSocket error:', error);
        };
    }
    
    function updateDashboard(data) {
        if (data.type === 'update') {
            // Update balance
            if (data.balance !== undefined) {
                document.getElementById('total-balance').textContent = 
                    `$${data.balance.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            }
            
            // Update positions
            if (data.positions) {
                updatePositionsTable(data.positions);
            }
            
            // Update metrics
            if (data.metrics) {
                updateMetrics(data.metrics);
            }
            
            // Update system status
            if (data.system) {
                updateSystemStatus(data.system);
            }
        } else if (data.type === 'trade') {
            addActivity(`${data.symbol} ${data.action}: ${data.details}`);
        }
    }
    
    function updatePositionsTable(positions) {
        const tbody = document.getElementById('positions-tbody');
        
        if (positions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; color: #9ca3af;">
                        포지션 없음
                    </td>
                </tr>
            `;
            document.getElementById('total-positions').textContent = '0';
            return;
        }
        
        document.getElementById('total-positions').textContent = positions.length;
        
        tbody.innerHTML = positions.map(position => {
            const pnl = position.pnl || 0;
            const pnlPercent = position.pnl_percent || 0;
            const pnlClass = pnl >= 0 ? 'profit' : 'loss';
            const sideClass = position.side === 'long' ? 'side-long' : 'side-short';
            
            return `
                <tr>
                    <td>${position.symbol}</td>
                    <td class="${sideClass}">${position.side.toUpperCase()}</td>
                    <td>$${position.entry_price.toFixed(2)}</td>
                    <td>$${position.current_price.toFixed(2)}</td>
                    <td>${position.quantity}</td>
                    <td class="${pnlClass}">$${pnl.toFixed(2)}</td>
                    <td class="${pnlClass}">${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%</td>
                </tr>
            `;
        }).join('');
    }
    
    function updateMetrics(metrics) {
        // Update performance metrics
        if (metrics.daily_pnl !== undefined) {
            const pnlElement = document.getElementById('daily-pnl');
            pnlElement.textContent = `${metrics.daily_pnl >= 0 ? '+' : ''}${metrics.daily_pnl.toFixed(2)}%`;
            pnlElement.className = `metric-value ${metrics.daily_pnl >= 0 ? 'profit' : 'loss'}`;
        }
        
        if (metrics.win_rate !== undefined) {
            document.getElementById('win-rate').textContent = `${metrics.win_rate.toFixed(1)}%`;
        }
        
        if (metrics.sharpe_ratio !== undefined) {
            document.getElementById('sharpe-ratio').textContent = metrics.sharpe_ratio.toFixed(2);
        }
        
        if (metrics.max_drawdown !== undefined) {
            document.getElementById('max-drawdown').textContent = `${metrics.max_drawdown.toFixed(1)}%`;
        }
        
        if (metrics.daily_trades !== undefined) {
            document.getElementById('daily-trades').textContent = metrics.daily_trades;
        }
    }
    
    function updateSystemStatus(system) {
        if (system.btc_trades !== undefined) {
            document.getElementById('btc-trades').textContent = system.btc_trades;
        }
        
        if (system.eth_trades !== undefined) {
            document.getElementById('eth-trades').textContent = system.eth_trades;
        }
        
        if (system.xrp_trades !== undefined) {
            document.getElementById('xrp-trades').textContent = system.xrp_trades;
        }
        
        if (system.api_latency !== undefined) {
            document.getElementById('api-latency').textContent = `${system.api_latency}ms`;
        }
    }
    
    function addActivity(message) {
        const feed = document.getElementById('activity-feed');
        const now = new Date();
        const timeStr = now.toLocaleTimeString('ko-KR');
        
        const item = document.createElement('div');
        item.className = 'activity-item';
        item.innerHTML = `
            <div class="activity-time">${timeStr}</div>
            <div>${message}</div>
        `;
        
        feed.insertBefore(item, feed.firstChild);
        
        // Keep only last 20 activities
        while (feed.children.length > 20) {
            feed.removeChild(feed.lastChild);
        }
    }
    
    function updateClock() {
        const now = new Date();
        document.getElementById('server-time').textContent = 
            now.toLocaleTimeString('ko-KR');
    }
    
    async function refreshData() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            updateDashboard(data);
            addActivity('데이터 새로고침 완료');
        } catch (error) {
            console.error('Failed to refresh data:', error);
            addActivity('데이터 새로고침 실패');
        }
    }
    
    // Initialize
    connectWebSocket();
    setInterval(updateClock, 1000);
    setInterval(refreshData, 30000); // Refresh every 30 seconds
    
    // Initial data load
    refreshData();
</script>
</body>
</html>
"""
# ==============================
# Main Application (Final Part)
# ==============================
[Continue with web API endpoints and main application as in original code, but with fixes]
Initialize FastAPI app
app = FastAPI(title="Bitget Trading System API")
app.add_middleware(
CORSMiddleware,
allow_origins=[""],
allow_credentials=True,
allow_methods=[""],
allow_headers=["*"],
)
Global reference to trading engine
trading_engine = None
@app.get("/", response_class=HTMLResponse)
async def root():
"""Serve dashboard HTML"""
return DASHBOARD_HTML
@app.get("/api/status")
async def get_status():
"""Get system status"""
if not trading_engine:
return {"status": "not_initialized"}
try:
    balance = await trading_engine.exchange.get_balance()
    positions = trading_engine.db.get_open_positions()
    daily_perf = trading_engine.db.get_daily_performance()
    
    # Get trade counts
    btc_trades = trading_engine.db.get_symbol_trades_today('BTCUSDT')
    eth_trades = trading_engine.db.get_symbol_trades_today('ETHUSDT')
    xrp_trades = trading_engine.db.get_symbol_trades_today('XRPUSDT')
    
    return {
        "type": "update",
        "status": "running" if trading_engine.is_running else "stopped",
        "balance": balance.get('USDT', {}).get('free', 0),
        "positions": positions,
        "metrics": {
            "daily_pnl": daily_perf['total_pnl_percent'],
            "win_rate": daily_perf['win_rate'] * 100,
            "sharpe_ratio": daily_perf['sharpe_ratio'],
            "max_drawdown": daily_perf['max_drawdown'] * 100,
            "daily_trades": daily_perf['total_trades']
        },
        "system": {
            "btc_trades": f"{btc_trades['total']}/10",
            "eth_trades": f"{eth_trades['total']}/3",
            "xrp_trades": f"{xrp_trades['total']}/2",
            "api_latency": 45  # Placeholder
        }
    }
except Exception as e:
    logging.error(f"Error getting status: {e}")
    return {"error": str(e)}
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
"""WebSocket for real-time updates"""
await websocket.accept()
try:
while True:
if trading_engine and trading_engine.is_running:
status = await get_status()
await websocket.send_json(status)
        await asyncio.sleep(1)
except WebSocketDisconnect:
    pass
except Exception as e:
    logging.error(f"WebSocket error: {e}")
[Main application class and entry point remain largely the same, with server startup fix]
class BitgetTradingApplication:
"""Main application orchestrator"""
def __init__(self, config: TradingConfig):
    self.config = config
    self.engine = AdvancedTradingEngine(config)
    self.scheduler = AsyncIOScheduler(timezone=timezone(config.TIMEZONE))
    self.logger = logging.getLogger(__name__)
    
    # Backtesting system
    self.backtester = BacktestingSystem(config) if config.ENABLE_BACKTESTING else None
    
    # Set global reference for API
    global trading_engine
    trading_engine = self.engine

async def initialize(self):
    """Initialize application"""
    await self.engine.initialize()
    
    # Run initial analysis
    await self.engine.run_trading_cycle()

def setup_schedule(self):
    """Setup trading schedule"""
    # Main trading cycles - every 15 minutes
    self.scheduler.add_job(
        self.engine.run_trading_cycle,
        'cron',
        minute='*/15',
        id='main_trading_cycle'
    )
    
    # Position management - every 5 minutes
    self.scheduler.add_job(
        self.engine.position_manager.manage_positions,
        'cron',
        minute='*/5',
        id='position_management'
    )
    
    # Performance update - every hour
    self.scheduler.add_job(
        self.engine.performance_analyzer.update_daily_performance,
        'cron',
        minute=0,
        id='performance_update'
    )
    
    # Daily report - 9 AM
    self.scheduler.add_job(
        self._send_daily_report,
        'cron',
        hour=9,
        minute=0,
        id='daily_report'
    )
    
    self.logger.info("Schedule configured:")
    self.logger.info("- Main cycle: Every 15 minutes")
    self.logger.info("- Position check: Every 5 minutes")
    self.logger.info("- Daily report: 9:00 AM")

async def _send_daily_report(self):
    """Send daily report"""
    report = self.engine.performance_analyzer.generate_performance_report(1)
    await self.engine.notifier.send_daily_report(report)

async def start_api_server(self):
    """Start FastAPI server"""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

async def start(self):
    """Start the application"""
    try:
        # Initialize
        await self.initialize()
        
        # Setup schedule
        self.setup_schedule()
        self.scheduler.start()
        
        # Start API server in background
        api_task = asyncio.create_task(self.start_api_server())
        
        self.logger.info("\n" + "="*60)
        self.logger.info("🚀 Bitget Trading System Started")
        self.logger.info("📊 Dashboard: http://localhost:8000")
        self.logger.info("="*60 + "\n")
        
        # Keep running
        while self.engine.is_running:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        self.logger.info("Shutting down...")
        self.engine.is_running = False
        self.scheduler.shutdown()
        
    except Exception as e:
        self.logger.critical(f"Critical error: {e}")
        traceback.print_exc()
        raise
# ==============================
# Entry Point
# ==============================
async def main():
"""Main entry point"""
try:
# Load configuration
config = TradingConfig.from_env()
    # Validate
    missing = config.validate()
    if missing:
        print(f"Missing configuration: {', '.join(missing)}")
        print("Please check your .env file")
        return
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('trading_system.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    #재시도Y계속편집Mapped out comprehensive trading system components and improvements.4초사용자가 "계속"이라고 요청했으므로, 이전 코드의 나머지 부분을 완성해야 합니다. Part 2에서 끝났던 부분부터 이어서 작성하겠습니다.
주요 완성해야 할 부분들:

# Multi-Timeframe Analyzer
# Position Manager with Trailing Stop
# Performance Analyzer
# News Sentiment Analyzer
# Notification Manager
# Market Regime Analyzer
# Pattern Recognition System
# ML Model Manager
Main Trading Engine
Entry point completion

모든 개선사항을 반영하여 완벽한 시스템을 만들어야 합니다.<artifact identifier="trading-system-part3" type="application/vnd.ant.code" language="python" title="Complete Trading System - Part 3 (Final)">
# ==============================
# Multi-Timeframe Analyzer (Enhanced)
# ==============================
class MultiTimeframeAnalyzer:
    """Enhanced multi-timeframe analysis with caching"""
def __init__(self, config: TradingConfig):
    self.config = config
    self.logger = logging.getLogger(__name__)
    self._analysis_cache = TTLCache(maxsize=100, ttl=300)

async def analyze_all_timeframes(self, exchange, symbol: str, strategies: Dict) -> Dict:
    """Analyze all timeframes for a symbol with parallel processing"""
    # Check cache first
    cache_key = f"mtf_analysis:{symbol}"
    cached_result = self._analysis_cache.get(cache_key)
    if cached_result:
        return cached_result
    
    results = {}
    timeframes = self.config.TIMEFRAME_WEIGHTS.get(symbol, self.config.TIMEFRAME_WEIGHTS["BTCUSDT"])
    
    # Parallel timeframe analysis
    tasks = []
    for tf_key, weight in timeframes.items():
        task = self._analyze_timeframe(exchange, symbol, tf_key, weight, strategies)
        tasks.append(task)
    
    # Wait for all analyses to complete
    tf_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for i, (tf_key, weight) in enumerate(timeframes.items()):
        if isinstance(tf_results[i], Exception):
            self.logger.error(f"Error analyzing {symbol} {tf_key}: {tf_results[i]}")
            results[tf_key] = self._get_default_result(weight)
        else:
            results[tf_key] = tf_results[i]
    
    # Combine results
    combined_result = self._combine_timeframe_results(results, symbol)
    
    # Cache the result
    self._analysis_cache[cache_key] = combined_result
    
    return combined_result

async def _analyze_timeframe(self, exchange, symbol: str, timeframe: str, 
                            weight: float, strategies: Dict) -> Dict:
    """Analyze single timeframe"""
    try:
        # Fetch OHLCV data
        df = await exchange.fetch_ohlcv_with_cache(symbol, timeframe)
        
        if df is None or len(df) < 100:
            return self._get_default_result(weight)
        
        # Calculate indicators
        indicators = EnhancedTechnicalIndicators.calculate_all_indicators(df)
        
        # Get strategy for symbol
        strategy = strategies.get(symbol)
        if not strategy:
            return self._get_default_result(weight)
        
        # Analyze
        tf_result = await strategy.analyze(symbol, df, indicators)
        tf_result['weight'] = weight
        tf_result['timeframe'] = timeframe
        
        return tf_result
        
    except Exception as e:
        self.logger.error(f"Error in timeframe analysis: {e}")
        return self._get_default_result(weight)

def _combine_timeframe_results(self, results: Dict, symbol: str) -> Dict:
    """Combine timeframe results with enhanced logic"""
    if not results:
        return self._get_default_combined_result()
    
    # Calculate weighted scores
    total_weight = 0
    weighted_score = 0
    weighted_confidence = 0
    directions = defaultdict(float)
    timeframe_scores = {}
    
    for tf, result in results.items():
        weight = result.get('weight', 0)
        total_weight += weight
        
        weighted_score += result['score'] * weight
        weighted_confidence += result.get('confidence', 50) * weight
        directions[result['direction']] += weight
        timeframe_scores[tf] = result['score']
    
    if total_weight == 0:
        return self._get_default_combined_result()
    
    # Normalize
    final_score = weighted_score / total_weight
    final_confidence = weighted_confidence / total_weight
    
    # Determine direction based on symbol-specific thresholds
    agreement_threshold = self.config.ENTRY_CONDITIONS[symbol]['timeframe_agreement']
    
    direction = 'neutral'
    alignment_score = 0
    
    for dir_name, dir_weight in directions.items():
        dir_ratio = dir_weight / total_weight
        if dir_ratio >= agreement_threshold:
            direction = dir_name
            alignment_score = dir_ratio
            break
    
    # Check for divergence
    divergence = self._check_divergence(timeframe_scores)
    
    # Adjust confidence based on alignment and divergence
    if alignment_score < agreement_threshold:
        final_confidence *= 0.7
    if divergence:
        final_confidence *= 0.8
    
    is_aligned = alignment_score >= agreement_threshold and not divergence
    
    return {
        'direction': direction,
        'score': final_score,
        'confidence': final_confidence,
        'alignment_score': alignment_score,
        'timeframe_results': results,
        'is_aligned': is_aligned,
        'divergence': divergence,
        'timeframe_scores': timeframe_scores
    }

def _check_divergence(self, timeframe_scores: Dict) -> bool:
    """Check for significant divergence between timeframes"""
    if len(timeframe_scores) < 2:
        return False
    
    scores = list(timeframe_scores.values())
    
    # Check if any timeframe strongly disagrees
    positive_scores = [s for s in scores if s > 0.3]
    negative_scores = [s for s in scores if s < -0.3]
    
    # Divergence if we have both strong positive and negative signals
    return len(positive_scores) > 0 and len(negative_scores) > 0

def _get_default_result(self, weight: float) -> Dict:
    """Default result for a timeframe"""
    return {
        'direction': 'neutral',
        'score': 0,
        'confidence': 50,
        'weight': weight,
        'components': {}
    }

def _get_default_combined_result(self) -> Dict:
    """Default combined result"""
    return {
        'direction': 'neutral',
        'score': 0,
        'confidence': 50,
        'alignment_score': 0,
        'timeframe_results': {},
        'is_aligned': False,
        'divergence': False,
        'timeframe_scores': {}
    }
# ==============================
# Enhanced Position Manager
# ==============================
class PositionManager:
    """Advanced position management with complete trailing stop implementation"""
    def __init__(self, config: TradingConfig, exchange, db: EnhancedDatabaseManager):
    self.config = config
    self.exchange = exchange
    self.db = db
    self.logger = logging.getLogger(__name__)
    
    # Track positions in memory for faster access
    self.active_positions = {}
    self._position_lock = asyncio.Lock()

async def open_position(self, symbol: str, signal: Dict, allocated_capital: float) -> Optional[Dict]:
    """Open a new position with comprehensive checks"""
    async with self._position_lock:
        try:
            # Double-check risk limits
            current_positions = self.db.get_open_positions(symbol)
            if len(current_positions) >= self.config.MAX_POSITIONS[symbol]:
                self.logger.warning(f"Position limit reached for {symbol}")
                return None
            
            # Calculate position size with slippage consideration
            size_ratio = self._calculate_position_size_ratio(symbol, signal)
            position_value = allocated_capital * size_ratio
            
            # Account for fees
            position_value *= (1 - self.config.TAKER_FEE)
            
            # Get contract size
            contracts = await self.exchange.calculate_position_size(symbol, position_value)
            
            if contracts <= 0:
                self.logger.warning(f"Invalid position size for {symbol}")
                return None
            
            # Place order
            side = 'buy' if signal['direction'] == 'long' else 'sell'
            order = await self.exchange.place_order(symbol, side, contracts)
            
            if not order or not order.get('id'):
                self.logger.error(f"Failed to place order for {symbol}")
                return None
            
            # Get fill details
            fill_price = order.get('price') or order.get('average', 0)
            actual_contracts = order.get('filled', contracts)
            
            # Calculate fees
            fees = position_value * self.config.TAKER_FEE
            slippage = order.get('slippage', 0)
            
            # Calculate stop loss and take profit levels
            stop_loss = self._calculate_stop_loss(symbol, fill_price, side)
            take_profit = self._calculate_take_profit(symbol, fill_price, side)
            
            # Save to database
            trade_data = {
                'symbol': symbol,
                'side': side,
                'price': fill_price,
                'quantity': actual_contracts,
                'leverage': self.config.LEVERAGE[symbol],
                'order_id': order.get('id'),
                'status': 'open',
                'reason': f"Signal: {signal['score']:.2f}, Confidence: {signal['confidence']:.1f}%",
                'multi_tf_score': signal.get('alignment_score', 0),
                'regime': signal.get('regime', 'unknown'),
                'entry_signal_strength': signal['score'],
                'fees_paid': fees,
                'slippage': slippage
            }
            
            trade_id = self.db.save_trade(trade_data)
            
            # Save position
            position_data = {
                'symbol': symbol,
                'trade_id': trade_id,
                'entry_price': fill_price,
                'quantity': actual_contracts,
                'side': side,
                'stop_loss': stop_loss,
                'take_profit': json.dumps(take_profit)
            }
            
            position_id = self.db.save_position(position_data)
            
            # Place stop loss order
            sl_side = 'sell' if side == 'buy' else 'buy'
            sl_order = await self.exchange.place_stop_loss_order(
                symbol, sl_side, actual_contracts, stop_loss
            )
            
            if sl_order and sl_order.get('id'):
                self.db.update_position(position_id, {'stop_order_id': sl_order['id']})
            
            # Track in memory
            self.active_positions[position_id] = {
                'symbol': symbol,
                'position_id': position_id,
                'trade_id': trade_id,
                'entry_price': fill_price,
                'side': side,
                'quantity': actual_contracts,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'max_profit': 0,
                'trailing_active': False
            }
            
            self.logger.info(
                f"✅ Position opened: {symbol} {side} {actual_contracts} @ {fill_price} "
                f"(SL: {stop_loss}, TP: {take_profit[0]['price'] if take_profit else 'None'})"
            )
            
            # Log to system
            self.db.log_system_event(
                'INFO', 'PositionManager', 
                f"Position opened: {symbol} {side}",
                {'trade_id': trade_id, 'position_id': position_id, 'signal': signal}
            )
            
            return {
                'trade_id': trade_id,
                'position_id': position_id,
                'order': order,
                'position_data': self.active_positions[position_id]
            }
            
        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
            self.db.log_system_event('ERROR', 'PositionManager', 
                                   f"Failed to open position: {symbol}", 
                                   {'error': str(e)})
            return None

async def manage_positions(self):
    """Manage all open positions with enhanced logic"""
    positions = self.db.get_open_positions()
    
    if not positions:
        return
    
    # Update active positions cache
    await self._sync_active_positions(positions)
    
    # Process each position
    tasks = []
    for position in positions:
        task = self._manage_single_position(position)
        tasks.append(task)
    
    # Execute position management in parallel
    await asyncio.gather(*tasks, return_exceptions=True)

async def _sync_active_positions(self, db_positions: List[Dict]):
    """Sync in-memory positions with database"""
    db_position_ids = {p['id'] for p in db_positions}
    memory_position_ids = set(self.active_positions.keys())
    
    # Remove closed positions from memory
    for pos_id in memory_position_ids - db_position_ids:
        del self.active_positions[pos_id]
    
    # Add new positions to memory
    for pos in db_positions:
        if pos['id'] not in self.active_positions:
            self.active_positions[pos['id']] = {
                'symbol': pos['symbol'],
                'position_id': pos['id'],
                'trade_id': pos['trade_id'],
                'entry_price': pos['entry_price'],
                'side': pos['side'],
                'quantity': pos['quantity'],
                'stop_loss': pos['stop_loss'],
                'take_profit': json.loads(pos.get('take_profit', '[]')),
                'max_profit': pos.get('max_profit', 0),
                'trailing_active': pos.get('trailing_stop_active', False)
            }

async def _manage_single_position(self, position: Dict):
    """Manage a single position with complete logic"""
    try:
        symbol = position['symbol']
        position_id = position['id']
        
        # Get current price
        current_price = self.exchange.get_current_price(symbol)
        if not current_price:
            ticker = await self.exchange.exchange.fetch_ticker(
                self.exchange._format_symbol(symbol)
            )
            current_price = ticker['last']
        
        # Update position in database
        self.db.update_position(position_id, {'current_price': current_price})
        
        # Calculate P&L
        pnl_data = self._calculate_pnl(position, current_price)
        
        # Update max profit
        if pnl_data['pnl_percent'] > position.get('max_profit', 0):
            self.db.update_position(position_id, {'max_profit': pnl_data['pnl_percent']})
            if position_id in self.active_positions:
                self.active_positions[position_id]['max_profit'] = pnl_data['pnl_percent']
        
        # Check for trailing stop
        await self._manage_trailing_stop(position, current_price, pnl_data)
        
        # Check for partial take profits
        await self._check_take_profit(position, current_price, pnl_data)
        
        # Check stop loss
        if self._should_stop_loss(position, current_price):
            await self._close_position(position, 'stop_loss', current_price)
            return
        
        # Check for position timeout (optional)
        if self._should_timeout_position(position):
            await self._close_position(position, 'timeout', current_price)
            return
        
        # Check for adverse movement
        if self._should_cut_loss_early(position, pnl_data):
            await self._close_position(position, 'early_stop', current_price)
            return
            
    except Exception as e:
        self.logger.error(f"Error managing position {position_id}: {e}")
        self.db.log_system_event('ERROR', 'PositionManager',
                               f"Position management error: {symbol}",
                               {'position_id': position_id, 'error': str(e)})

def _calculate_pnl(self, position: Dict, current_price: float) -> Dict:
    """Calculate position P&L with fees"""
    entry_price = position['entry_price']
    quantity = position['quantity']
    side = position['side']
    
    if side == 'long':
        price_change = (current_price - entry_price) / entry_price
    else:
        price_change = (entry_price - current_price) / entry_price
    
    # Account for fees (entry + potential exit)
    total_fees = self.config.TAKER_FEE * 2
    pnl_percent = price_change - total_fees
    pnl_value = pnl_percent * quantity * entry_price
    
    return {
        'pnl_value': pnl_value,
        'pnl_percent': pnl_percent,
        'price_change': price_change,
        'current_price': current_price
    }

async def _manage_trailing_stop(self, position: Dict, current_price: float, pnl_data: Dict):
    """Manage trailing stop with enhanced logic"""
    symbol = position['symbol']
    position_id = position['id']
    trailing_config = self.config.TRAILING_STOP[symbol]
    
    # Check if we should activate trailing stop
    if (pnl_data['pnl_percent'] >= trailing_config['activate'] and 
        not position.get('trailing_stop_active', False)):
        
        await self._activate_trailing_stop(position, current_price, trailing_config)
        
    elif position.get('trailing_stop_active', False):
        # Update trailing stop if price moved favorably
        await self._update_trailing_stop(position, current_price, trailing_config)
        
        # Check if trailing stop would be hit
        if self._check_trailing_stop_hit(position, current_price):
            await self._close_position(position, 'trailing_stop', current_price)

async def _activate_trailing_stop(self, position: Dict, current_price: float, config: Dict):
    """Activate trailing stop"""
    side = position['side']
    distance = config['distance']
    
    if side == 'long':
        trailing_stop_price = current_price * (1 - distance)
    else:
        trailing_stop_price = current_price * (1 + distance)
    
    # Ensure trailing stop is better than original stop loss
    original_sl = position['stop_loss']
    if side == 'long' and trailing_stop_price <= original_sl:
        return
    if side == 'short' and trailing_stop_price >= original_sl:
        return
    
    # Update database
    self.db.update_position(position['id'], {
        'trailing_stop_active': True,
        'trailing_stop_price': trailing_stop_price,
        'stop_loss': trailing_stop_price
    })
    
    # Update stop order on exchange
    if position.get('stop_order_id'):
        await self.exchange.modify_stop_loss(
            position['symbol'],
            position['stop_order_id'],
            trailing_stop_price
        )
    
    # Update memory
    if position['id'] in self.active_positions:
        self.active_positions[position['id']]['trailing_active'] = True
        self.active_positions[position['id']]['stop_loss'] = trailing_stop_price
    
    self.logger.info(
        f"📈 Trailing stop activated for {position['symbol']} at {trailing_stop_price:.2f}"
    )

async def _update_trailing_stop(self, position: Dict, current_price: float, config: Dict):
    """Update trailing stop if price moved favorably"""
    side = position['side']
    distance = config['distance']
    current_trailing = position.get('trailing_stop_price', position['stop_loss'])
    
    if side == 'long':
        new_trailing = current_price * (1 - distance)
        if new_trailing > current_trailing:
            await self._set_new_trailing_stop(position, new_trailing)
    else:
        new_trailing = current_price * (1 + distance)
        if new_trailing < current_trailing:
            await self._set_new_trailing_stop(position, new_trailing)

async def _set_new_trailing_stop(self, position: Dict, new_stop_price: float):
    """Set new trailing stop price"""
    self.db.update_position(position['id'], {
        'trailing_stop_price': new_stop_price,
        'stop_loss': new_stop_price
    })
    
    if position.get('stop_order_id'):
        await self.exchange.modify_stop_loss(
            position['symbol'],
            position['stop_order_id'],
            new_stop_price
        )
    
    if position['id'] in self.active_positions:
        self.active_positions[position['id']]['stop_loss'] = new_stop_price

def _check_trailing_stop_hit(self, position: Dict, current_price: float) -> bool:
    """Check if trailing stop is hit"""
    stop_loss = position.get('stop_loss', 0)
    side = position['side']
    
    if side == 'long':
        return current_price <= stop_loss
    else:
        return current_price >= stop_loss

async def _check_take_profit(self, position: Dict, current_price: float, pnl_data: Dict):
    """Check and execute partial take profits"""
    take_profit_levels = json.loads(position.get('take_profit', '[]'))
    
    if not take_profit_levels:
        return
    
    for tp in take_profit_levels:
        if tp.get('executed', False):
            continue
        
        tp_hit = False
        if position['side'] == 'long':
            tp_hit = current_price >= tp['price']
        else:
            tp_hit = current_price <= tp['price']
        
        if tp_hit:
            # Execute partial close
            partial_quantity = position['quantity'] * tp['size']
            await self._close_partial_position(position, partial_quantity, 'take_profit', current_price)
            
            # Mark as executed
            tp['executed'] = True
            self.db.update_position(position['id'], {
                'take_profit': json.dumps(take_profit_levels)
            })

async def _close_partial_position(self, position: Dict, quantity: float, reason: str, current_price: float):
    """Close partial position"""
    try:
        side = 'sell' if position['side'] == 'long' else 'buy'
        order = await self.exchange.place_order(position['symbol'], side, quantity)
        
        if order:
            self.logger.info(
                f"💰 Partial position closed: {position['symbol']} - "
                f"{quantity} contracts @ {current_price} - Reason: {reason}"
            )
            
            # Update remaining quantity
            new_quantity = position['quantity'] - quantity
            self.db.update_position(position['id'], {'quantity': new_quantity})
            
    except Exception as e:
        self.logger.error(f"Failed to close partial position: {e}")

def _should_stop_loss(self, position: Dict, current_price: float) -> bool:
    """Check if stop loss should be triggered"""
    side = position['side']
    stop_loss = position['stop_loss']
    
    if side == 'long':
        return current_price <= stop_loss
    else:
        return current_price >= stop_loss

def _should_timeout_position(self, position: Dict) -> bool:
    """Check if position should be closed due to timeout"""
    # Optional: Close positions open for too long
    # For now, return False
    return False

def _should_cut_loss_early(self, position: Dict, pnl_data: Dict) -> bool:
    """Check if we should cut losses early based on adverse movement"""
    # If position quickly moves against us, cut early
    # This helps prevent larger losses
    
    # Get time since entry
    # If within first hour and already down significantly, cut
    # For now, simplified implementation
    if pnl_data['pnl_percent'] < -self.config.STOP_LOSS[position['symbol']] * 0.7:
        return True
    
    return False

async def _close_position(self, position: Dict, reason: str, close_price: float):
    """Close a position completely"""
    try:
        # Close on exchange
        order = await self.exchange.close_position(position['symbol'], reason)
        
        if not order:
            self.logger.error(f"Failed to close position on exchange: {position['symbol']}")
            return
        
        # Get actual close price from order
        actual_close_price = order.get('price', close_price)
        
        # Calculate final P&L
        pnl_data = self._calculate_pnl(position, actual_close_price)
        
        # Update database
        self.db.update_position(position['id'], {
            'status': 'closed',
            'current_price': actual_close_price
        })
        
        # Calculate hold duration
        trade = self.db._get_connection().execute(
            "SELECT timestamp FROM trades WHERE id = ?", 
            (position['trade_id'],)
        ).fetchone()
        
        if trade:
            hold_duration = (datetime.now() - datetime.fromisoformat(trade['timestamp'])).seconds // 60
        else:
            hold_duration = 0
        
        # Update trade
        self.db.update_trade(position['trade_id'], {
            'status': 'closed',
            'close_price': actual_close_price,
            'close_time': datetime.now(),
            'pnl': pnl_data['pnl_value'],
            'pnl_percent': pnl_data['pnl_percent'] * 100,
            'reason': reason,
            'hold_duration': hold_duration,
            'max_profit': position.get('max_profit', 0),
            'trailing_stop_activated': position.get('trailing_stop_active', False)
        })
        
        # Remove from active positions
        if position['id'] in self.active_positions:
            del self.active_positions[position['id']]
        
        # Log
        emoji = '💰' if pnl_data['pnl_percent'] > 0 else '🛑'
        self.logger.info(
            f"{emoji} Position closed: {position['symbol']} - {reason} - "
            f"P&L: {pnl_data['pnl_percent']:.2%} (${pnl_data['pnl_value']:.2f})"
        )
        
        self.db.log_system_event(
            'INFO', 'PositionManager',
            f"Position closed: {position['symbol']} - {reason}",
            {
                'position_id': position['id'],
                'pnl_percent': pnl_data['pnl_percent'],
                'reason': reason
            }
        )
        
    except Exception as e:
        self.logger.error(f"Error closing position: {e}")
        self.db.log_system_event(
            'ERROR', 'PositionManager',
            f"Failed to close position: {position['symbol']}",
            {'position_id': position['id'], 'error': str(e)}
        )

def _calculate_position_size_ratio(self, symbol: str, signal: Dict) -> float:
    """Calculate position size ratio based on signal strength and market conditions"""
    base_range = self.config.POSITION_SIZE_RANGE[symbol]
    
    # Start with standard size
    size = base_range['standard']
    
    # Adjust based on signal strength
    signal_strength = abs(signal['score'])
    if signal_strength > 0.7:
        size = base_range['max']
    elif signal_strength < 0.4:
        size = base_range['min']
    
    # Adjust based on confidence
    confidence = signal['confidence']
    if confidence > 80:
        size *= 1.2
    elif confidence < 60:
        size *= 0.8
    
    # Adjust based on market regime
    regime = signal.get('regime', 'unknown')
    if regime == 'volatile':
        size *= 0.7  # Reduce size in volatile markets
    elif regime in ['trending_up', 'trending_down']:
        size *= 1.1  # Increase size in trending markets
    
    # Ensure within limits
    return np.clip(size, base_range['min'], base_range['max'])

def _calculate_stop_loss(self, symbol: str, entry_price: float, side: str) -> float:
    """Calculate stop loss price with market conditions adjustment"""
    base_sl_pct = self.config.STOP_LOSS[symbol]
    
    # Could adjust based on volatility here
    # For now, use base stop loss
    
    if side == 'buy':
        return entry_price * (1 - base_sl_pct)
    else:
        return entry_price * (1 + base_sl_pct)

def _calculate_take_profit(self, symbol: str, entry_price: float, side: str) -> List[Dict]:
    """Calculate take profit levels"""
    tp_levels = self.config.TAKE_PROFIT[symbol]
    result = []
    
    for tp_pct, tp_size in tp_levels:
        if side == 'buy':
            tp_price = entry_price * (1 + tp_pct)
        else:
            tp_price = entry_price * (1 - tp_pct)
        
        result.append({
            'price': tp_price,
            'size': tp_size,
            'executed': False
        })
    
    return result
# ==============================
# Enhanced Performance Analyzer
# ==============================
class PerformanceAnalyzer:
    """Real-time performance analysis and reporting with advanced metrics"""
    def __init__(self, db: EnhancedDatabaseManager):
    self.db = db
    self.logger = logging.getLogger(__name__)
    self._performance_cache = TTLCache(maxsize=100, ttl=300)

async def update_daily_performance(self):
    """Update daily performance metrics with comprehensive calculations"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get all trades from today
    with self.db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM trades 
            WHERE DATE(timestamp) = ? AND status = 'closed'
        """, (today,))
        
        trades = [dict(row) for row in cursor.fetchall()]
    
    if not trades:
        # Still update with zeros
        self.db.update_daily_performance(today, self._get_empty_metrics())
        return
    
    # Calculate comprehensive metrics
    metrics = self._calculate_comprehensive_metrics(trades)
    
    # Update database
    self.db.update_daily_performance(today, metrics)
    
    # Clear cache
    self._performance_cache.clear()

def _calculate_comprehensive_metrics(self, trades: List[Dict]) -> Dict:
    """Calculate comprehensive performance metrics"""
    metrics = {
        'total_trades': len(trades),
        'winning_trades': sum(1 for t in trades if t['pnl'] > 0),
        'losing_trades': sum(1 for t in trades if t['pnl'] < 0),
        'total_pnl': sum(t['pnl'] for t in trades),
        'total_pnl_percent': sum(t['pnl_percent'] for t in trades) / 100,  # Convert from percentage
        'total_fees': sum(t.get('fees_paid', 0) for t in trades),
        'total_volume': sum(t['quantity'] * t['price'] for t in trades)
    }
    
    # P&L by symbol
    for symbol in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']:
        symbol_trades = [t for t in trades if t['symbol'] == symbol]
        symbol_key = f"{symbol[:3].lower()}_pnl"
        metrics[symbol_key] = sum(t['pnl'] for t in symbol_trades)
    
    # Win rate
    if metrics['total_trades'] > 0:
        metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades']
    else:
        metrics['win_rate'] = 0
    
    # Average win/loss
    winning_pnls = [t['pnl_percent'] / 100 for t in trades if t['pnl'] > 0]
    losing_pnls = [t['pnl_percent'] / 100 for t in trades if t['pnl'] < 0]
    
    metrics['avg_win'] = np.mean(winning_pnls) if winning_pnls else 0
    metrics['avg_loss'] = np.mean(losing_pnls) if losing_pnls else 0
    
    # Best/worst trade
    if trades:
        metrics['best_trade'] = max(t['pnl_percent'] / 100 for t in trades)
        metrics['worst_trade'] = min(t['pnl_percent'] / 100 for t in trades)
    else:
        metrics['best_trade'] = 0
        metrics['worst_trade'] = 0
    
    # Calculate Sharpe ratio
    metrics['sharpe_ratio'] = self._calculate_sharpe_ratio(trades)
    
    # Calculate max drawdown
    metrics['max_drawdown'] = self._calculate_max_drawdown(trades)
    
    return metrics

def _calculate_sharpe_ratio(self, trades: List[Dict]) -> float:
    """Calculate Sharpe ratio"""
    if len(trades) < 2:
        return 0
    
    returns = [t['pnl_percent'] / 100 for t in trades]
    
    if not returns or np.std(returns) == 0:
        return 0
    
    # Annualized Sharpe ratio (assuming ~20 trades per day, 252 trading days)
    daily_return = np.mean(returns)
    daily_std = np.std(returns)
    
    if daily_std == 0:
        return 0
    
    # Risk-free rate (assuming 0 for crypto)
    sharpe = (daily_return / daily_std) * np.sqrt(252)
    
    return round(sharpe, 2)

def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
    """Calculate maximum drawdown"""
    if not trades:
        return 0
    
    # Calculate cumulative returns
    cumulative_pnl = 0
    peak = 0
    max_dd = 0
    
    for trade in sorted(trades, key=lambda x: x['timestamp']):
        cumulative_pnl += trade['pnl']
        
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        
        drawdown = (peak - cumulative_pnl) / peak if peak > 0 else 0
        max_dd = max(max_dd, drawdown)
    
    return round(max_dd, 4)

def _get_empty_metrics(self) -> Dict:
    """Get empty metrics structure"""
    return {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'total_pnl': 0.0,
        'total_pnl_percent': 0.0,
        'btc_pnl': 0.0,
        'eth_pnl': 0.0,
        'xrp_pnl': 0.0,
        'max_drawdown': 0.0,
        'sharpe_ratio': 0.0,
        'win_rate': 0.0,
        'avg_win': 0.0,
        'avg_loss': 0.0,
        'best_trade': 0.0,
        'worst_trade': 0.0,
        'total_volume': 0.0,
        'total_fees': 0.0
    }

def generate_performance_report(self, days: int = 7) -> str:
    """Generate comprehensive performance report"""
    # Check cache first
    cache_key = f"report_{days}"
    cached_report = self._performance_cache.get(cache_key)
    if cached_report:
        return cached_report
    
    # Get performance data
    with self.db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM daily_performance 
            WHERE date >= date('now', '-{} days')
            ORDER BY date DESC
        """.format(days))
        
        daily_data = [dict(row) for row in cursor.fetchall()]
    
    if not daily_data:
        return "No trading data available for the period."
    
    # Get recent trades for additional insights
    cursor.execute("""
        SELECT * FROM trades 
        WHERE timestamp >= datetime('now', '-{} days')
        AND status = 'closed'
        ORDER BY timestamp DESC
    """.format(days))
    
    recent_trades = [dict(row) for row in cursor.fetchall()]
    
    # Aggregate metrics
    total_trades = sum(d['total_trades'] for d in daily_data)
    total_pnl = sum(d['total_pnl'] for d in daily_data)
    total_pnl_pct = sum(d['total_pnl_percent'] for d in daily_data)
    total_fees = sum(d.get('total_fees', 0) for d in daily_data)
    
    # Calculate strategy performance
    strategy_performance = self._calculate_strategy_performance(recent_trades)
    
    # Generate report
    report = f"""
📊 Performance Report - Last {days} Days
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} KST
📈 Summary

Total Trades: {total_trades}
Total P&L: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)
Total Fees: ${total_fees:,.2f}
Net P&L: ${total_pnl - total_fees:,.2f}
Average Daily P&L: ${total_pnl/days:,.2f}

💎 By Symbol

BTC: ${sum(d['btc_pnl'] for d in daily_data):,.2f}
ETH: ${sum(d['eth_pnl'] for d in daily_data):,.2f}
XRP: ${sum(d['xrp_pnl'] for d in daily_data):,.2f}

📊 Statistics

Win Rate: {np.mean([d['win_rate'] for d in daily_data if d['total_trades'] > 0]):.1%}
Avg Win: {np.mean([d['avg_win'] for d in daily_data if d['avg_win'] > 0]):+.2f}%
Avg Loss: {np.mean([d['avg_loss'] for d in daily_data if d['avg_loss'] < 0]):+.2f}%
Best Day: {max(d['total_pnl_percent'] for d in daily_data):+.2f}%
Worst Day: {min(d['total_pnl_percent'] for d in daily_data):+.2f}%
Max Drawdown: {max(d['max_drawdown'] for d in daily_data):.2%}
Sharpe Ratio: {np.mean([d['sharpe_ratio'] for d in daily_data if d['sharpe_ratio'] != 0]):.2f}

🎯 Strategy Performance
{strategy_performance}
📅 Daily Breakdown
"""
    # Add daily breakdown
    for day_data in daily_data[:7]:  # Last 7 days
        date = day_data['date']
        daily_pnl = day_data['total_pnl_percent']
        trades = day_data['total_trades']
        win_rate = day_data['win_rate']
        
        emoji = '🟢' if daily_pnl > 0 else '🔴' if daily_pnl < 0 else '⚪'
        report += f"{emoji} {date}: {daily_pnl:+.2f}% ({trades} trades, {win_rate:.0%} win rate)\n"
    
    # Cache the report
    self._performance_cache[cache_key] = report
    
    return report

def _calculate_strategy_performance(self, trades: List[Dict]) -> str:
    """Calculate performance by strategy/regime"""
    if not trades:
        return "No trade data available"
    
    # Group by regime
    regime_performance = defaultdict(lambda: {'count': 0, 'pnl': 0})
    
    for trade in trades:
        regime = trade.get('regime', 'unknown')
        regime_performance[regime]['count'] += 1
        regime_performance[regime]['pnl'] += trade['pnl_percent'] / 100
    
    # Format results
    results = []
    for regime, data in regime_performance.items():
        avg_pnl = data['pnl'] / data['count'] if data['count'] > 0 else 0
        results.append(f"• {regime.title()}: {avg_pnl:+.2f}% avg ({data['count']} trades)")
    
    return '\n'.join(results) if results else "No regime data available"
# ==============================
# Enhanced News Sentiment Analyzer
# ==============================
class NewsSentimentAnalyzer:
"""Enhanced news sentiment analysis with multiple sources"""
def __init__(self, config: TradingConfig):
    self.config = config
    self.openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None
    self.logger = logging.getLogger(__name__)
    self._sentiment_cache = TTLCache(maxsize=50, ttl=600)  # 10 min cache
    
    self.emergency_keywords = [
        'hack', 'exploit', 'crash', 'bankruptcy', 'fraud', 'investigation',
        'sec', 'lawsuit', 'ban', 'emergency', 'urgent', 'breaking',
        'liquidation', 'default', 'collapse', 'scam', 'theft', 'attack',
        '해킹', '파산', '사기', '긴급', '폭락', '규제'
    ]
    
    self.news_sources = [
        "https://feeds.feedburner.com/CoinDesk",
        "https://cointelegraph.com/rss",
        "https://bitcoinist.com/feed/",
        "https://www.newsbtc.com/feed/"
    ]

async def analyze_sentiment(self, symbol: Optional[str] = None) -> Dict[str, Any]:
    """Analyze news sentiment with caching"""
    # Check cache
    cache_key = f"sentiment:{symbol or 'all'}"
    cached_result = self._sentiment_cache.get(cache_key)
    if cached_result:
        return cached_result
    
    try:
        # Fetch news
        news_items = await self._fetch_news(symbol)
        
        if not news_items:
            result = self._get_default_sentiment()
            self._sentiment_cache[cache_key] = result
            return result
        
        # Check for emergency keywords
        has_emergency = self._check_emergency_keywords(news_items)
        
        # Get sentiment analysis
        if self.openai_client:
            analysis = await self._get_gpt_analysis(news_items, symbol)
        else:
            analysis = self._get_basic_analysis(news_items, has_emergency)
        
        # Override if emergency detected
        if has_emergency:
            analysis['has_emergency'] = True
            analysis['sentiment'] = min(analysis['sentiment'], -0.5)
            analysis['action_required'] = 'close_positions'
            analysis['urgency'] = '즉시'
        
        # Cache result
        self._sentiment_cache[cache_key] = analysis
        
        return analysis
        
    except Exception as e:
        self.logger.error(f"News sentiment analysis failed: {e}")
        return self._get_default_sentiment()

async def _fetch_news(self, symbol: Optional[str] = None) -> List[Dict]:
    """Fetch crypto news from multiple sources"""
    news_items = []
    
    # Fetch from RSS feeds concurrently
    tasks = []
    for source_url in self.news_sources:
        task = self._fetch_rss_feed(source_url)
        tasks.append(task)
    
    feed_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for result in feed_results:
        if isinstance(result, list):
            news_items.extend(result)
    
    # Sort by date (newest first)
    news_items.sort(key=lambda x: x.get('published_parsed', 0), reverse=True)
    
    # Filter by symbol if provided
    if symbol and news_items:
        news_items = self._filter_by_symbol(news_items, symbol)
    
    return news_items[:20]  # Return top 20 items

async def _fetch_rss_feed(self, url: str) -> List[Dict]:
    """Fetch single RSS feed"""
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, url)
        
        items = []
        for entry in feed.entries[:10]:
            items.append({
                'title': entry.get('title', ''),
                'summary': entry.get('summary', ''),
                'published': entry.get('published', ''),
                'published_parsed': entry.get('published_parsed', 0),
                'link': entry.get('link', ''),
                'source': feed.feed.get('title', 'Unknown')
            })
        
        return items
        
    except Exception as e:
        self.logger.error(f"Error fetching from {url}: {e}")
        return []

def _filter_by_symbol(self, news_items: List[Dict], symbol: str) -> List[Dict]:
    """Filter news by symbol"""
    keywords = {
        'BTCUSDT': ['bitcoin', 'btc', '비트코인', 'bitcoin etf', 'btc price'],
        'ETHUSDT': ['ethereum', 'eth', '이더리움', 'eth 2.0', 'defi'],
        'XRPUSDT': ['ripple', 'xrp', '리플', 'sec ripple', 'xrp lawsuit']
    }
    
    symbol_keywords = keywords.get(symbol, [])
    if not symbol_keywords:
        return news_items[:10]
    
    filtered = []
    for item in news_items:
        text = f"{item['title']} {item['summary']}".lower()
        if any(kw in text for kw in symbol_keywords):
            filtered.append(item)
    
    # If too few symbol-specific news, include general news
    if len(filtered) < 5:
        filtered.extend([item for item in news_items if item not in filtered])
    
    return filtered[:15]

def _check_emergency_keywords(self, news_items: List[Dict]) -> bool:
    """Check for emergency keywords in news"""
    for item in news_items[:5]:  # Check only recent news
        text = f"{item['title']} {item['summary']}".lower()
        if any(keyword in text for keyword in self.emergency_keywords):
            self.logger.warning(f"🚨 Emergency keyword detected: {item['title']}")
            return True
    return False

async def _get_gpt_analysis(self, news_items: List[Dict], symbol: Optional[str]) -> Dict:
    """Get GPT analysis of news"""
    # Prepare news text
    news_text = "\n".join([
        f"[{item['source']}] {item['title']}" 
        for item in news_items[:15]
    ])
    
    prompt = f"""Analyze cryptocurrency news for trading sentiment.
{f'Focus on impact on {symbol}.' if symbol else ''}
News headlines:
{news_text}
Provide analysis in this exact format:

Overall sentiment score (-1.0 to +1.0): [score]
Market impact (high/medium/low): [impact]
Key positive factors: [factors]
Key negative factors: [factors]
Trading recommendation (buy/sell/hold): [recommendation]
Urgency (immediate/normal): [urgency]
Brief summary: [one line summary]"""
 try:
     response = await asyncio.get_event_loop().run_in_executor(
         None,
         lambda: self.openai_client.chat.completions.create(
             model="gpt-4",
             messages=[
                 {"role": "system", "content": "You are a cryptocurrency market analyst. Analyze news impact on prices accurately."},
                 {"role": "user", "content": prompt}
             ],
             temperature=0.3,
             max_tokens=500
         )
     )
     
     return self._parse_gpt_response(response.choices[0].message.content, news_items)
     
 except Exception as e:
     self.logger.error(f"GPT analysis failed: {e}")
     return self._get_basic_analysis(news_items, False)
def _parse_gpt_response(self, response: str, news_items: List[Dict]) -> Dict:
"""Parse GPT response"""
lines = response.split('\n')
 result = {
     'sentiment': 0.0,
     'impact': 'medium',
     'positive_factors': [],
     'negative_factors': [],
     'recommendation': 'hold',
     'urgency': 'normal',
     'summary': '',
     'news_count': len(news_items),
     'latest_news': news_items[0]['title'] if news_items else '',
     'has_emergency': False
 }
 
 for line in lines:
     line = line.strip()
     if not line:
         continue
     
     # Parse sentiment score
     if 'sentiment score' in line.lower() and ':' in line:
         try:
             score_text = line.split(':')[1].strip()
             import re
             numbers = re.findall(r'-?\d*\.?\d+', score_text)
             if numbers:
                 result['sentiment'] = float(numbers[0])
         except:
             pass
     
     # Parse other fields similarly...
     elif 'market impact' in line.lower() and ':' in line:
         impact_text = line.split(':')[1].strip().lower()
         if 'high' in impact_text:
             result['impact'] = 'high'
         elif 'low' in impact_text:
             result['impact'] = 'low'
     
     elif 'recommendation' in line.lower() and ':' in line:
         rec_text = line.split(':')[1].strip().lower()
         if 'buy' in rec_text:
             result['recommendation'] = 'buy'
         elif 'sell' in rec_text:
             result['recommendation'] = 'sell'
     
     elif 'urgency' in line.lower() and ':' in line:
         urg_text = line.split(':')[1].strip().lower()
         if 'immediate' in urg_text or 'urgent' in urg_text:
             result['urgency'] = 'immediate'
     
     elif 'summary' in line.lower() and ':' in line:
         result['summary'] = line.split(':')[1].strip()
 
 # Ensure sentiment is within bounds
 result['sentiment'] = max(-1, min(1, result['sentiment']))
 
 return result
def _get_basic_analysis(self, news_items: List[Dict], has_emergency: bool) -> Dict:
"""Get basic sentiment analysis without GPT"""
if not news_items:
return self._get_default_sentiment()
 # Simple keyword-based analysis
 positive_keywords = ['bullish', 'surge', 'gain', 'rise', 'pump', 'adoption',
                    'institutional', 'approve', 'partnership', 'upgrade']
 negative_keywords = ['bearish', 'crash', 'fall', 'dump', 'ban', 'reject',
                    'hack', 'scam', 'lawsuit', 'investigation']
 
 positive_count = 0
 negative_count = 0
 
 for item in news_items[:10]:
     text = f"{item['title']} {item['summary']}".lower()
     positive_count += sum(1 for kw in positive_keywords if kw in text)
     negative_count += sum(1 for kw in negative_keywords if kw in text)
 
 # Calculate sentiment
 total_signals = positive_count + negative_count
 if total_signals > 0:
     sentiment = (positive_count - negative_count) / total_signals
 else:
     sentiment = 0
 
 return {
     'sentiment': sentiment,
     'impact': 'high' if has_emergency else 'medium',
     'positive_factors': [f"{positive_count} positive signals"],
     'negative_factors': [f"{negative_count} negative signals"],
     'recommendation': 'sell' if sentiment < -0.3 else 'buy' if sentiment > 0.3 else 'hold',
     'urgency': 'immediate' if has_emergency else 'normal',
     'summary': f"Found {positive_count} positive and {negative_count} negative signals",
     'news_count': len(news_items),
     'latest_news': news_items[0]['title'] if news_items else '',
     'has_emergency': has_emergency
 }
def _get_default_sentiment(self) -> Dict[str, Any]:
"""Default sentiment values"""
return {
'sentiment': 0.0,
'impact': 'low',
'positive_factors': [],
'negative_factors': [],
'recommendation': 'hold',
'urgency': 'normal',
'summary': 'No news data available',
'news_count': 0,
'latest_news': '',
'has_emergency': False
}

# ==============================
# Enhanced Notification Manager
# ==============================
class NotificationManager:
"""Multi-channel notification system with rate limiting"""
def __init__(self, config: TradingConfig):
    self.config = config
    self.logger = logging.getLogger(__name__)
    
    # Message queue to prevent spam
    self.message_queue = deque(maxlen=100)
    self.last_message_time = {}
    self.min_interval = 60  # Minimum seconds between similar messages
    
    # Priority queues
    self.emergency_queue = queue.PriorityQueue()
    self.normal_queue = queue.Queue()
    
    # Start message processor
    self.processor_task = None
    self.is_running = True

async def initialize(self):
    """Initialize notification system"""
    self.processor_task = asyncio.create_task(self._message_processor())
    self.logger.info("Notification system initialized")

async def _message_processor(self):
    """Process messages from queues"""
    while self.is_running:
        try:
            # Check emergency queue first
            if not self.emergency_queue.empty():
                _, message = self.emergency_queue.get_nowait()
                await self._send_message(message)
            
            # Then normal queue
            elif not self.normal_queue.empty():
                message = self.normal_queue.get_nowait()
                await self._send_message(message)
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            self.logger.error(f"Message processor error: {e}")
            await asyncio.sleep(1)

async def send_notification(self, message: str, priority: str = 'normal', 
                          channel: str = 'telegram', metadata: Dict = None):
    """Send notification with priority and channel selection"""
    # Check for spam
    message_hash = hashlib.md5(message.encode()).hexdigest()[:8]
    current_time = time.time()
    
    if priority != 'emergency':  # Don't rate limit emergency messages
        if message_hash in self.last_message_time:
            if current_time - self.last_message_time[message_hash] < self.min_interval:
                return  # Skip duplicate message
    
    self.last_message_time[message_hash] = current_time
    
    # Create message object
    msg_obj = {
        'content': message,
        'channel': channel,
        'timestamp': current_time,
        'metadata': metadata or {}
    }
    
    # Queue based on priority
    if priority == 'emergency':
        self.emergency_queue.put((0, msg_obj))  # Highest priority
    elif priority == 'high':
        self.emergency_queue.put((1, msg_obj))
    else:
        self.normal_queue.put(msg_obj)

async def _send_message(self, msg_obj: Dict):
    """Send message to appropriate channel"""
    channel = msg_obj['channel']
    message = msg_obj['content']
    
    if channel == 'telegram':
        await self._send_telegram_message(message)
    # Add other channels here (Discord, Email, etc.)

async def _send_telegram_message(self, message: str):
    """Send Telegram message with retry"""
    if not self.config.TELEGRAM_BOT_TOKEN or not self.config.TELEGRAM_CHAT_ID:
        return
    
    try:
        url = f"https://api.telegram.org/bot{self.config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": self.config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"Telegram send failed: {error_text}")
                    
                    # Retry for important messages
                    if response.status == 429:  # Rate limited
                        retry_after = int(response.headers.get('Retry-After', 60))
                        await asyncio.sleep(retry_after)
                        await session.post(url, data=data)
                        
    except Exception as e:
        self.logger.error(f"Telegram message error: {e}")

async def send_trade_notification(self, symbol: str, action: str, details: Dict):
    """Send formatted trade notification"""
    emoji_map = {
        'open_long': '🟢',
        'open_short': '🔴',
        'close_profit': '💰',
        'close_loss': '🛑',
        'close_neutral': '⏹️',
        'trailing_stop': '📈',
        'take_profit': '🎯'
    }
    
    emoji = emoji_map.get(action, '📊')
    action_text = action.replace('_', ' ').title()
    
    message = f"""
{emoji} {symbol} - {action_text}
💵 Price: ${details.get('price', 0):,.2f}
📊 Quantity: {details.get('quantity', 0)}
"""
    if 'signal_strength' in details:
        message += f"🎯 Signal: {details['signal_strength']:.2f}\n"
    
    if 'confidence' in details:
        message += f"🔮 Confidence: {details['confidence']:.1f}%\n"
    
    if 'pnl' in details:
        pnl = details['pnl']
        pnl_emoji = '💰' if pnl > 0 else '🔻'
        message += f"{pnl_emoji} P&L: {pnl:+.2f}%\n"
    
    if 'reason' in details:
        message += f"📝 Reason: {details['reason']}\n"
    
    # Determine priority
    priority = 'normal'
    if action in ['open_long', 'open_short', 'close_profit', 'close_loss']:
        priority = 'high'
    if 'emergency' in details.get('reason', '').lower():
        priority = 'emergency'
    
    await self.send_notification(message, priority=priority)

async def send_daily_report(self, report: str):
    """Send daily performance report"""
    # Add header
    header = "📊 **Daily Performance Report**\n" + "="*30 + "\n\n"
    full_report = header + report
    
    await self.send_notification(full_report, priority='normal')

async def send_error_notification(self, error: str, details: str = "", component: str = ""):
    """Send error notification"""
    message = f"""
❌ System Error
Component: {component or 'Unknown'}
Error: {error}
{f'Details: {details}' if details else ''}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
await self.send_notification(message, priority='high')
async def send_risk_alert(self, alert_type: str, details: Dict):
    """Send risk management alert"""
    emoji_map = {
        'daily_loss_limit': '🛑',
        'position_limit': '⚠️',
        'drawdown_warning': '📉',
        'correlation_risk': '🔗'
    }
    
    emoji = emoji_map.get(alert_type, '⚠️')
    
    message = f"""
{emoji} Risk Alert: {alert_type.replace('_', ' ').title()}
{details.get('message', '')}
Current Status:

Daily P&L: {details.get('daily_pnl', 0):+.2f}%
Open Positions: {details.get('open_positions', 0)}
Risk Level: {details.get('risk_level', 'Unknown')}
"""
  await self.send_notification(message, priority='high')
async def shutdown(self):
"""Shutdown notification system"""
self.is_running = False
if self.processor_task:
await self.processor_task

# ==============================
# Market Regime Analyzer (Complete)
# ==============================
class MarketRegimeAnalyzer:
"""Enhanced market regime detection with ML integration"""
def __init__(self):
    self.regimes = ['trending_up', 'trending_down', 'ranging', 'volatile']
    self.logger = logging.getLogger(__name__)
    self._regime_cache = TTLCache(maxsize=100, ttl=300)

def analyze_regime(self, df: pd.DataFrame, indicators: Dict) -> Dict:
    """Analyze current market regime with caching"""
    # Create cache key from recent price data
    cache_key = f"regime:{df.index[-1]}:{df['close'].iloc[-1]}"
    cached_result = self._regime_cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # Price position analysis
    price_score = self._analyze_price_position(df, indicators)
    
    # Momentum analysis
    momentum_score = self._analyze_momentum(indicators)
    
    # Trend strength
    trend_strength = self._analyze_trend_strength(indicators)
    
    # Volatility analysis
    volatility_score = self._analyze_volatility(df, indicators)
    
    # Volume profile
    volume_score = self._analyze_volume_profile(df, indicators)
    
    # Determine regime
    regime = self._determine_regime(
        price_score, momentum_score, trend_strength, volatility_score, volume_score
    )
    
    # Calculate confidence
    confidence = self._calculate_confidence(
        price_score, momentum_score, trend_strength, volatility_score
    )
    
    # Get regime-specific parameters
    regime_params = self._get_regime_parameters(regime, volatility_score)
    
    result = {
        'regime': regime,
        'confidence': confidence,
        'characteristics': self._get_regime_characteristics(regime),
        'parameters': regime_params,
        'scores': {
            'price': price_score,
            'momentum': momentum_score,
            'trend': trend_strength,
            'volatility': volatility_score,
            'volume': volume_score
        }
    }
    
    # Cache result
    self._regime_cache[cache_key] = result
    
    return result

def _analyze_price_position(self, df: pd.DataFrame, indicators: Dict) -> float:
    """Analyze price position relative to key levels"""
    score = 0
    current_price = df['close'].iloc[-1]
    
    # Position relative to EMAs
    weights = {'ema_20': 0.3, 'ema_50': 0.25, 'sma_200': 0.2}
    for ma, weight in weights.items():
        if ma in indicators and not indicators[ma].empty:
            if current_price > indicators[ma].iloc[-1]:
                score += weight
            else:
                score -= weight
    
    # EMA alignment
    if (indicators['ema_20'].iloc[-1] > indicators['ema_50'].iloc[-1] > indicators.get('sma_200', indicators['ema_50']).iloc[-1]):
        score += 0.25
    elif (indicators['ema_20'].iloc[-1] < indicators['ema_50'].iloc[-1] < indicators.get('sma_200', indicators['ema_50']).iloc[-1]):
        score -= 0.25
    
    return np.clip(score, -1, 1)

def _analyze_momentum(self, indicators: Dict) -> float:
    """Analyze momentum indicators"""
    score = 0
    weights = {}
    
    # RSI
    rsi = indicators['rsi'].iloc[-1]
    if rsi > 70:
        score -= 0.3  # Overbought
    elif rsi > 50:
        score += 0.2
    elif rsi < 30:
        score += 0.3  # Oversold bounce potential
    else:
        score -= 0.2
    
    # MACD
    if indicators['macd'].iloc[-1] > indicators['macd_signal'].iloc[-1]:
        score += 0.3
        # MACD histogram momentum
        if indicators['macd_hist'].iloc[-1] > indicators['macd_hist'].iloc[-2]:
            score += 0.2
    else:
        score -= 0.3
        if indicators['macd_hist'].iloc[-1] < indicators['macd_hist'].iloc[-2]:
            score -= 0.2
    
    # MFI
    if 'mfi' in indicators:
        mfi = indicators['mfi'].iloc[-1]
        if mfi > 80:
            score -= 0.2
        elif mfi < 20:
            score += 0.2
    
    return np.clip(score, -1, 1)

def _analyze_trend_strength(self, indicators: Dict) -> float:
    """Analyze trend strength using multiple indicators"""
    components = []
    
    # ADX
    adx = indicators['adx'].iloc[-1]
    if adx > 40:
        adx_score = 1.0
    elif adx > 25:
        adx_score = 0.7
    elif adx > 20:
        adx_score = 0.4
    else:
        adx_score = 0.2
    components.append(adx_score * 0.4)
    
    # Directional movement
    if indicators['plus_di'].iloc[-1] > indicators['minus_di'].iloc[-1]:
        di_score = min((indicators['plus_di'].iloc[-1] - indicators['minus_di'].iloc[-1]) / 50, 1)
    else:
        di_score = -min((indicators['minus_di'].iloc[-1] - indicators['plus_di'].iloc[-1]) / 50, 1)
    components.append(di_score * 0.3)
    
    # Supertrend
    if 'supertrend_direction' in indicators:
        st_direction = indicators['supertrend_direction'].iloc[-1]
        components.append(st_direction * 0.3)
    
    return np.clip(sum(components), -1, 1)

def _analyze_volatility(self, df: pd.DataFrame, indicators: Dict) -> float:
    """Analyze market volatility"""
    # ATR ratio
    atr = indicators['atr'].iloc[-1]
    price = df['close'].iloc[-1]
    atr_ratio = atr / price
    
    # Historical comparison
    atr_sma = indicators['atr'].rolling(50).mean().iloc[-1]
    current_vs_historical = atr / atr_sma if atr_sma > 0 else 1
    
    # Bollinger Band width
    bb_width = (indicators['bb_upper'].iloc[-1] - indicators['bb_lower'].iloc[-1]) / indicators['bb_middle'].iloc[-1]
    bb_width_sma = ((indicators['bb_upper'] - indicators['bb_lower']) / indicators['bb_middle']).rolling(20).mean().iloc[-1]
    bb_squeeze = bb_width / bb_width_sma if bb_width_sma > 0 else 1
    
    # Calculate volatility score
    if current_vs_historical > 2:
        vol_score = 1.0
    elif current_vs_historical > 1.5:
        vol_score = 0.7
    elif current_vs_historical > 1.2:
        vol_score = 0.5
    elif bb_squeeze < 0.7:  # Bollinger squeeze
        vol_score = 0.3
    else:
        vol_score = 0.4
    
    return vol_score

def _analyze_volume_profile(self, df: pd.DataFrame, indicators: Dict) -> float:
    """Analyze volume patterns"""
    score = 0
    
    # Volume trend
    recent_volume = df['volume'].iloc[-5:].mean()
    avg_volume = indicators['volume_sma'].iloc[-1]
    
    if recent_volume > avg_volume * 1.5:
        # High volume
        if df['close'].iloc[-1] > df['close'].iloc[-5]:
            score += 0.5  # Bullish volume
        else:
            score -= 0.5  # Bearish volume
    
    # OBV trend
    if 'obv' in indicators:
        obv_slope = np.polyfit(range(20), indicators['obv'].iloc[-20:].values, 1)[0]
        if obv_slope > 0:
            score += 0.3
        else:
            score -= 0.3
    
    # Volume ratio consistency
    vol_ratios = indicators.get('volume_ratio', pd.Series())
    if not vol_ratios.empty:
        vol_consistency = vol_ratios.iloc[-10:].std()
        if vol_consistency < 0.5:  # Consistent volume
            score *= 0.8  # Reduce score magnitude
    
    return np.clip(score, -1, 1)

def _determine_regime(self, price: float, momentum: float, trend: float, 
                     volatility: float, volume: float) -> str:
    """Determine market regime based on scores"""
    # Strong trend detection
    if trend > 0.6:
        if price > 0.4 and momentum > 0:
            return 'trending_up'
        elif price < -0.4 and momentum < 0:
            return 'trending_down'
    
    # High volatility overrides other signals
    if volatility > 0.7:
        return 'volatile'
    
    # Weak trend with momentum
    if abs(trend) < 0.4:
        if abs(price) < 0.3:
            return 'ranging'
    
    # Default based on price and momentum
    combined_score = (price + momentum) / 2
    if combined_score > 0.3:
        return 'trending_up'
    elif combined_score < -0.3:
        return 'trending_down'
    
    return 'ranging'

def _calculate_confidence(self, price: float, momentum: float,
                        trend: float, volatility: float) -> float:
    """Calculate regime confidence"""
    # Base confidence on consistency of signals
    scores = [price, momentum, trend]
    
    # Check alignment
    aligned_positive = sum(1 for s in scores if s > 0.3)
    aligned_negative = sum(1 for s in scores if s < -0.3)
    
    if aligned_positive >= 3 or aligned_negative >= 3:
        base_confidence = 85
    elif aligned_positive >= 2 or aligned_negative >= 2:
        base_confidence = 70
    else:
        base_confidence = 50
    
    # Adjust for trend strength
    base_confidence += abs(trend) * 15
    
    # Reduce for high volatility
    if volatility > 0.8:
        base_confidence *= 0.8
    elif volatility > 0.6:
        base_confidence *= 0.9
    
    return min(95, max(20, base_confidence))

def _get_regime_parameters(self, regime: str, volatility: float) -> Dict:
    """Get regime-specific trading parameters"""
    params = {
        'trending_up': {
            'position_size_multiplier': 1.2,
            'stop_loss_multiplier': 0.9,
            'take_profit_multiplier': 1.1,
            'max_positions': 3,
            'preferred_timeframes': ['4h', '1h']
        },
        'trending_down': {
            'position_size_multiplier': 0.8,
            'stop_loss_multiplier': 0.8,
            'take_profit_multiplier': 1.0,
            'max_positions': 1,
            'preferred_timeframes': ['1h', '30m']
        },
        'ranging': {
            'position_size_multiplier': 1.0,
            'stop_loss_multiplier': 1.0,
            'take_profit_multiplier': 0.8,
            'max_positions': 2,
            'preferred_timeframes': ['30m', '15m']
        },
        'volatile': {
            'position_size_multiplier': 0.6,
            'stop_loss_multiplier': 1.2,
            'take_profit_multiplier': 0.7,
            'max_positions': 1,
            'preferred_timeframes': ['15m', '5m']
        }
    }
    
    # Further adjust for extreme volatility
    if volatility > 0.9:
        params[regime]['position_size_multiplier'] *= 0.7
        params[regime]['stop_loss_multiplier'] *= 1.2
    
    return params.get(regime, params['ranging'])

def _get_regime_characteristics(self, regime: str) -> Dict:
    """Get regime characteristics"""
    characteristics = {
        'trending_up': {
            'description': 'Strong Uptrend',
            'kr_description': '강한 상승 추세',
            'risk_level': 0.3,
            'position_bias': 'long',
            'suggested_strategy': 'trend_following',
            'key_indicators': ['ADX', 'Moving Averages', 'MACD'],
            'warnings': ['Watch for overbought conditions', 'Set trailing stops']
        },
        'trending_down': {
            'description': 'Strong Downtrend',
            'kr_description': '강한 하락 추세',
            'risk_level': 0.7,
            'position_bias': 'short',
            'suggested_strategy': 'trend_following',
            'key_indicators': ['ADX', 'Moving Averages', 'MACD'],
            'warnings': ['High risk environment', 'Use tight stops']
        },
        'ranging': {
            'description': 'Sideways/Range-bound',
            'kr_description': '횡보/박스권',
            'risk_level': 0.5,
            'position_bias': 'neutral',
            'suggested_strategy': 'mean_reversion',
            'key_indicators': ['RSI', 'Bollinger Bands', 'Support/Resistance'],
            'warnings': ['Avoid breakout fakeouts', 'Trade the range']
        },
        'volatile': {
            'description': 'High Volatility',
            'kr_description': '고변동성',
            'risk_level': 0.8,
            'position_bias': 'neutral',
            'suggested_strategy': 'scalping',
            'key_indicators': ['ATR', 'Bollinger Bands', 'Volume'],
            'warnings': ['Reduce position size', 'Wider stops needed']
        }
    }
    
    return characteristics.get(regime, characteristics['ranging'])
# ==============================
# Pattern Recognition System (Already complete in previous parts)
# ==============================
# ==============================
# ML Model Manager (Enhanced)
# ==============================
class MLModelManager:
"""Machine learning model management with online learning"""
def __init__(self, config: TradingConfig):
    self.config = config
    self.logger = logging.getLogger(__name__)
    self.models = {}
    self.scalers = {}
    self.feature_names = []
    self.model_performance = defaultdict(lambda: {'predictions': 0, 'correct': 0})
    
    if config.ENABLE_ML_MODELS:
        self._initialize_models()

def _initialize_models(self):
    """Initialize ML models and scalers"""
    try:
        # Feature configuration
        self.feature_names = [
            'returns_1', 'returns_5', 'returns_20',
            'volume_ratio', 'atr_ratio', 'bb_position',
            'rsi', 'macd_signal', 'adx', 'obv_slope',
            'price_ma_ratio', 'volume_ma_ratio'
        ]
        
        # Initialize scalers
        self.scalers['features'] = StandardScaler()
        self.scalers['target'] = MinMaxScaler()
        
        # Try to load existing models
        self._load_models()
        
        # If no models exist, create default ones
        if not self.models:
            self._create_default_models()
            
    except Exception as e:
        self.logger.error(f"Error initializing ML models: {e}")
        self.config.ENABLE_ML_MODELS = False

def _load_models(self):
    """Load saved models"""
    model_dir = "models"
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
        return
    
    # Load models
    model_files = {
        'random_forest': 'rf_model.pkl',
        'xgboost': 'xgb_model.pkl',
        'ensemble': 'ensemble_model.pkl'
    }
    
    for model_name, filename in model_files.items():
        filepath = os.path.join(model_dir, filename)
        if os.path.exists(filepath):
            try:
                self.models[model_name] = joblib.load(filepath)
                self.logger.info(f"Loaded {model_name} model")
            except Exception as e:
                self.logger.error(f"Failed to load {model_name}: {e}")
    
    # Load scalers
    scaler_path = os.path.join(model_dir, 'scalers.pkl')
    if os.path.exists(scaler_path):
        try:
            self.scalers = joblib.load(scaler_path)
        except:
            pass

def _create_default_models(self):
    """Create default models"""
    # Random Forest
    self.models['random_forest'] = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        random_state=42,
        n_jobs=-1
    )
    
    self.logger.info("Created default ML models")

async def get_predictions(self, symbol: str, features: Dict[str, float]) -> Dict[str, Any]:
    """Get predictions from all models"""
    if not self.config.ENABLE_ML_MODELS or not self.models:
        return self._get_empty_prediction()
    
    try:
        # Prepare features
        feature_array = self._prepare_features(features)
        
        if feature_array is None:
            return self._get_empty_prediction()
        
        # Get predictions from each model
        predictions = {}
        for model_name, model in self.models.items():
            try:
                prediction = await self._predict_with_model(
                    model_name, model, feature_array
                )
                predictions[model_name] = prediction
            except Exception as e:
                self.logger.error(f"Error with {model_name} prediction: {e}")
                predictions[model_name] = None
        
        # Ensemble prediction
        ensemble_prediction = self._ensemble_predictions(predictions)
        
        return {
            'individual_predictions': predictions,
            'ensemble': ensemble_prediction,
            'features_used': self.feature_names,
            'confidence_factors': self._calculate_confidence_factors(features)
        }
        
    except Exception as e:
        self.logger.error(f"ML prediction error: {e}")
        return self._get_empty_prediction()

def _prepare_features(self, raw_features: Dict[str, float]) -> Optional[np.ndarray]:
    """Prepare features for ML models"""
    try:
        # Extract features in correct order
        feature_values = []
        for feature_name in self.feature_names:
            if feature_name in raw_features:
                feature_values.append(raw_features[feature_name])
            else:
                # Use default values for missing features
                feature_values.append(0.0)
        
        # Convert to numpy array
        feature_array = np.array(feature_values).reshape(1, -1)
        
        # Scale features if scaler is fitted
        if hasattr(self.scalers['features'], 'mean_'):
            feature_array = self.scalers['features'].transform(feature_array)
        
        return feature_array
        
    except Exception as e:
        self.logger.error(f"Feature preparation error: {e}")
        return None

async def _predict_with_model(self, model_name: str, model: Any, 
                             features: np.ndarray) -> Dict:
    """Get prediction from single model"""
    try:
        # Run prediction in thread pool
        loop = asyncio.get_event_loop()
        
        # Make prediction
        prediction = await loop.run_in_executor(
            None, model.predict, features
        )
        
        # Get prediction probability/confidence if available
        confidence = 0.5
        if hasattr(model, 'predict_proba'):
            try:
                proba = await loop.run_in_executor(
                    None, model.predict_proba, features
                )
                confidence = np.max(proba)
            except:
                pass
        
        # Convert prediction to direction and magnitude
        pred_value = float(prediction[0])
        
        if abs(pred_value) < 0.001:  # Near zero
            direction = 'neutral'
        elif pred_value > 0:
            direction = 'long'
        else:
            direction = 'short'
        
        return {
            'prediction': pred_value,
            'direction': direction,
            'confidence': float(confidence),
            'model': model_name
        }
        
    except Exception as e:
        self.logger.error(f"Model prediction error: {e}")
        return None

def _ensemble_predictions(self, predictions: Dict) -> Dict:
    """Combine predictions from multiple models"""
    valid_predictions = [
        p for p in predictions.values() 
        if p is not None and 'prediction' in p
    ]
    
    if not valid_predictions:
        return {
            'prediction': 0,
            'direction': 'neutral',
            'confidence': 0,
            'method': 'none'
        }
    
    # Weighted average based on model performance
    total_weight = 0
    weighted_sum = 0
    direction_votes = defaultdict(float)
    
    for pred in valid_predictions:
        # Get model weight based on historical performance
        model_name = pred['model']
        perf = self.model_performance[model_name]
        
        if perf['predictions'] > 0:
            accuracy = perf['correct'] / perf['predictions']
            weight = max(0.1, accuracy)  # Minimum weight of 0.1
        else:
            weight = 0.5  # Default weight for new models
        
        # Weight by confidence too
        weight *= pred['confidence']
        
        weighted_sum += pred['prediction'] * weight
        direction_votes[pred['direction']] += weight
        total_weight += weight
    
    if total_weight == 0:
        ensemble_pred = np.mean([p['prediction'] for p in valid_predictions])
        ensemble_conf = np.mean([p['confidence'] for p in valid_predictions])
    else:
        ensemble_pred = weighted_sum / total_weight
        ensemble_conf = total_weight / len(valid_predictions)
    
    # Determine direction from votes
    ensemble_direction = max(direction_votes.items(), key=lambda x: x[1])[0]
    
    return {
        'prediction': ensemble_pred,
        'direction': ensemble_direction,
        'confidence': min(ensemble_conf, 0.95),
        'method': 'weighted_ensemble',
        'model_count': len(valid_predictions)
    }

def _calculate_confidence_factors(self, features: Dict[str, float]) -> Dict[str, float]:
    """Calculate factors affecting prediction confidence"""
    factors = {}
    
    # Market regime confidence
    if 'trend_strength' in features:
        factors['trend_clarity'] = abs(features['trend_strength'])
    
    # Volatility impact
    if 'atr_ratio' in features:
        # Lower confidence in high volatility
        factors['volatility_penalty'] = max(0, 1 - features['atr_ratio'] * 10)
    
    # Technical alignment
    technical_signals = ['rsi', 'macd_signal', 'bb_position']
    aligned_signals = sum(1 for sig in technical_signals 
                        if sig in features and abs(features[sig]) > 0.3)
    factors['technical_alignment'] = aligned_signals / len(technical_signals)
    
    return factors

def update_model_performance(self, model_name: str, prediction: float, actual: float):
    """Update model performance tracking"""
    self.model_performance[model_name]['predictions'] += 1
    
    # Check if prediction direction was correct
    pred_direction = 'long' if prediction > 0 else 'short'
    actual_direction = 'long' if actual > 0 else 'short'
    
    if pred_direction == actual_direction:
        self.model_performance[model_name]['correct'] += 1

async def retrain_models(self, training_data: pd.DataFrame):
    """Retrain models with new data (implement as needed)"""
    # This would be called periodically with accumulated data
    # For production, consider online learning approaches
    pass

def save_models(self):
    """Save models to disk"""
    model_dir = "models"
    os.makedirs(model_dir, exist_ok=True)
    
    # Save models
    for model_name, model in self.models.items():
        filepath = os.path.join(model_dir, f"{model_name}_model.pkl")
        joblib.dump(model, filepath)
    
    # Save scalers
    scaler_path = os.path.join(model_dir, 'scalers.pkl')
    joblib.dump(self.scalers, scaler_path)
    
    self.logger.info("Models saved successfully")

def _get_empty_prediction(self) -> Dict:
    """Return empty prediction structure"""
    return {
        'individual_predictions': {},
        'ensemble': {
            'prediction': 0,
            'direction': 'neutral',
            'confidence': 0,
            'method': 'none'
        },
        'features_used': [],
        'confidence_factors': {}
    }
# ==============================
# Main Trading Engine (Final Implementation)
# ==============================
class AdvancedTradingEngine:
"""Main trading strategy engine with all components integrated"""
def __init__(self, config: TradingConfig):
    self.config = config
    self.logger = logging.getLogger(__name__)
    
    # Initialize components
    self.db = EnhancedDatabaseManager(config.DATABASE_PATH)
    self.exchange = EnhancedBitgetExchangeManager(config)
    self.position_manager = PositionManager(config, self.exchange, self.db)
    self.risk_manager = RiskManager(config, self.db)
    self.notifier = NotificationManager(config)
    self.performance_analyzer = PerformanceAnalyzer(self.db)
    
    # Analysis components
    self.multi_tf_analyzer = MultiTimeframeAnalyzer(config)
    self.regime_analyzer = MarketRegimeAnalyzer()
    self.pattern_recognizer = PatternRecognitionSystem()
    self.news_analyzer = NewsSentimentAnalyzer(config)
    
    # ML models
    self.ml_manager = MLModelManager(config)
    
    # Trading strategies by symbol
    self.strategies = {
        'BTCUSDT': BTCTradingStrategy(config),
        'ETHUSDT': ETHTradingStrategy(config),
        'XRPUSDT': XRPTradingStrategy(config)
    }
    
    # State tracking
    self.last_analysis_time = {}
    self.is_running = True
    self.startup_time = datetime.now()
    self._analysis_lock = asyncio.Lock()

async def initialize(self):
    """Initialize all components"""
    self.logger.info("="*60)
    self.logger.info("Initializing Advanced Bitget Trading System v2.0")
    self.logger.info("="*60)
    
    try:
        # Initialize exchange
        await self.exchange.initialize()
        
        # Initialize notification system
        await self.notifier.initialize()
        
        # Check balance
        balance = await self.exchange.get_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        
        self.logger.info(f"✅ System initialized successfully")
        self.logger.info(f"💰 USDT Balance: ${usdt_balance:,.2f}")
        self.logger.info(f"📊 Trading symbols: {', '.join(self.config.SYMBOLS)}")
        self.logger.info(f"⚙️ Portfolio allocation: BTC 70%, ETH 20%, XRP 10%")
        self.logger.info(f"🤖 ML Models: {'Enabled' if self.config.ENABLE_ML_MODELS else 'Disabled'}")
        self.logger.info(f"📡 WebSocket: {'Connected' if self.exchange.ws_connected else 'Disconnected'}")
        
        # Log system configuration
        self.db.log_system_event('INFO', 'System', 'Trading system started', {
            'balance':재시도Y계속편집준비하여 거래 시스템 코드 구현 재개2초The user wants me to continue with the trading system code. I need to complete the implementation from where it was cut off. Looking at the code, I was in the middle of implementing the AdvancedTradingEngine class's initialize method. I need to continue from there and complete the rest of the implementation.<artifact identifier="trading-system-part3" type="application/vnd.ant.code" language="python" title="Complete Trading System - Part 3 (Final)">
            # Log system configuration
            self.db.log_system_event('INFO', 'System', 'Trading system started', {
                'balance': usdt_balance,
                'symbols': self.config.SYMBOLS,
                'ml_enabled': self.config.ENABLE_ML_MODELS,
                'websocket': self.exchange.ws_connected
            })
        # Send startup notification
        await self.notifier.send_notification(
            f"🚀 Trading system started\n"
            f"💰 Balance: ${usdt_balance:,.2f}\n"
            f"🤖 ML: {'ON' if self.config.ENABLE_ML_MODELS else 'OFF'}\n"
            f"📡 WS: {'ON' if self.exchange.ws_connected else 'OFF'}",
            priority='high'
        )
        
        # Initialize positions tracking
        await self.position_manager.manage_positions()
        
    except Exception as e:
        self.logger.critical(f"Failed to initialize system: {e}")
        await self.notifier.send_error_notification(
            "System initialization failed",
            str(e),
            "Main"
        )
        raise

async def analyze_and_trade(self, symbol: str):
    """Main analysis and trading logic for a symbol"""
    async with self._analysis_lock:
        try:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Analyzing {symbol} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Check if we should analyze this symbol
            if not self._should_analyze_symbol(symbol):
                self.logger.info(f"Skipping {symbol} - analyzed recently")
                return
            
            # Update analysis time
            self.last_analysis_time[symbol] = datetime.now()
            
            # Risk checks first
            risk_check = await self.risk_manager.check_risk_limits(symbol)
            if not risk_check['can_trade']:
                self.logger.warning(f"Risk limits exceeded for {symbol}: {risk_check['checks']}")
                await self.notifier.send_risk_alert('risk_limit_exceeded', {
                    'symbol': symbol,
                    'message': f"Cannot trade {symbol} due to risk limits",
                    'failed_checks': [k for k, v in risk_check['checks'].items() if not v]
                })
                return
            
            # Multi-timeframe analysis
            self.logger.info(f"Performing multi-timeframe analysis for {symbol}...")
            multi_tf_result = await self.multi_tf_analyzer.analyze_all_timeframes(
                self.exchange, symbol, self.strategies
            )
            
            self.logger.info(
                f"Multi-TF Result: Direction={multi_tf_result['direction']}, "
                f"Score={multi_tf_result['score']:.3f}, "
                f"Alignment={multi_tf_result['alignment_score']:.2f}, "
                f"Divergence={multi_tf_result.get('divergence', False)}"
            )
            
            # Check entry conditions
            entry_conditions = self.config.ENTRY_CONDITIONS[symbol]
            
            # For ETH and XRP, check BTC correlation
            if entry_conditions.get('btc_correlation_check', False):
                btc_result = await self._get_btc_direction()
                if btc_result['direction'] != multi_tf_result['direction']:
                    self.logger.info(f"{symbol} direction conflicts with BTC, skipping")
                    return
            
            # Check alignment threshold
            if not multi_tf_result['is_aligned']:
                self.logger.info(f"{symbol} timeframes not aligned (alignment: {multi_tf_result['alignment_score']:.2f})")
                return
            
            # Get primary timeframe data for detailed analysis
            primary_tf = self._get_primary_timeframe(symbol)
            df = await self.exchange.fetch_ohlcv_with_cache(symbol, primary_tf)
            
            if df is None or len(df) < 200:
                self.logger.warning(f"Insufficient data for {symbol}")
                return
            
            # Calculate comprehensive indicators
            self.logger.info(f"Calculating technical indicators...")
            indicators = EnhancedTechnicalIndicators.calculate_all_indicators(df)
            
            # Market regime analysis
            self.logger.info(f"Analyzing market regime...")
            regime_info = self.regime_analyzer.analyze_regime(df, indicators)
            self.logger.info(
                f"Market Regime: {regime_info['regime']} "
                f"(confidence: {regime_info['confidence']:.1f}%)"
            )
            
            # Pattern recognition
            self.logger.info(f"Detecting chart patterns...")
            patterns = self.pattern_recognizer.identify_patterns(df, indicators)
            if patterns:
                pattern_names = list(patterns.keys())
                self.logger.info(f"Patterns detected: {', '.join(pattern_names)}")
            
            # News sentiment analysis
            self.logger.info(f"Analyzing news sentiment...")
            news_sentiment = await self.news_analyzer.analyze_sentiment(symbol)
            self.logger.info(
                f"News Sentiment: {news_sentiment['sentiment']:+.2f} "
                f"({news_sentiment['impact']} impact)"
            )
            
            # Check for emergency news
            if news_sentiment.get('has_emergency', False):
                await self._handle_emergency(symbol, news_sentiment)
                return
            
            # ML predictions if available
            ml_predictions = {}
            if self.config.ENABLE_ML_MODELS:
                self.logger.info(f"Getting ML predictions...")
                features = self._extract_ml_features(df, indicators, regime_info)
                ml_predictions = await self.ml_manager.get_predictions(symbol, features)
                
                if ml_predictions.get('ensemble'):
                    self.logger.info(
                        f"ML Prediction: {ml_predictions['ensemble']['direction']} "
                        f"(confidence: {ml_predictions['ensemble']['confidence']:.2f})"
                    )
            
            # Generate final trading signal
            trading_signal = self._generate_comprehensive_signal(
                symbol, multi_tf_result, regime_info, patterns, 
                news_sentiment, ml_predictions, indicators
            )
            
            # Log comprehensive signal
            self.logger.info(
                f"\n{'='*40}\n"
                f"TRADING SIGNAL SUMMARY for {symbol}\n"
                f"{'='*40}\n"
                f"Direction: {trading_signal['direction']}\n"
                f"Score: {trading_signal['score']:.3f}\n"
                f"Confidence: {trading_signal['confidence']:.1f}%\n"
                f"Should Trade: {trading_signal['should_trade']}\n"
                f"Expected Move: {trading_signal['expected_move']:.2f}%\n"
                f"{'='*40}"
            )
            
            # Save prediction for tracking
            await self._save_prediction(symbol, df, trading_signal, indicators, regime_info, news_sentiment)
            
            # Execute trade if conditions met
            if trading_signal['should_trade']:
                await self._execute_trade(symbol, trading_signal, df['close'].iloc[-1])
            else:
                self.logger.info(f"No trade signal for {symbol}")
            
            # Always manage existing positions
            await self.position_manager.manage_positions()
            
            # Update performance metrics
            await self.performance_analyzer.update_daily_performance()
            
            self.logger.info(f"Analysis complete for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            self.db.log_system_event('ERROR', 'TradingEngine', 
                                   f"Analysis error for {symbol}", 
                                   {'error': str(e), 'traceback': traceback.format_exc()})
            await self.notifier.send_error_notification(
                f"Analysis failed for {symbol}",
                str(e),
                "TradingEngine"
            )

def _should_analyze_symbol(self, symbol: str) -> bool:
    """Check if enough time has passed since last analysis"""
    if symbol not in self.last_analysis_time:
        return True
    
    # Minimum time between analyses (in minutes)
    min_interval = {
        'BTCUSDT': 5,
        'ETHUSDT': 10,
        'XRPUSDT': 15
    }
    
    time_since_last = (datetime.now() - self.last_analysis_time[symbol]).seconds / 60
    return time_since_last >= min_interval.get(symbol, 10)

def _get_primary_timeframe(self, symbol: str) -> str:
    """Get primary timeframe for analysis"""
    timeframes = self.config.TIMEFRAME_WEIGHTS.get(symbol, {})
    if not timeframes:
        return '4h'
    
    # Return timeframe with highest weight
    return max(timeframes.items(), key=lambda x: x[1])[0]

async def _get_btc_direction(self) -> Dict:
    """Get BTC direction for correlation check"""
    # Quick BTC analysis with caching
    btc_result = await self.multi_tf_analyzer.analyze_all_timeframes(
        self.exchange, 'BTCUSDT', self.strategies
    )
    return btc_result

def _extract_ml_features(self, df: pd.DataFrame, indicators: Dict, 
                       regime_info: Dict) -> Dict[str, float]:
    """Extract features for ML models"""
    features = {}
    
    # Price-based features
    features['returns_1'] = df['close'].pct_change(1).iloc[-1]
    features['returns_5'] = df['close'].pct_change(5).iloc[-1]
    features['returns_20'] = df['close'].pct_change(20).iloc[-1]
    
    # Volume features
    features['volume_ratio'] = indicators['volume_ratio'].iloc[-1]
    features['volume_ma_ratio'] = df['volume'].iloc[-1] / indicators['volume_sma'].iloc[-1]
    
    # Volatility features
    features['atr_ratio'] = indicators['atr_percent'].iloc[-1] / 100
    features['bb_position'] = indicators['price_position'].iloc[-1]
    
    # Technical indicators
    features['rsi'] = (indicators['rsi'].iloc[-1] - 50) / 50  # Normalize
    features['macd_signal'] = np.sign(indicators['macd'].iloc[-1] - indicators['macd_signal'].iloc[-1])
    features['adx'] = indicators['adx'].iloc[-1] / 100
    
    # Trend features
    features['price_ma_ratio'] = df['close'].iloc[-1] / indicators['sma_50'].iloc[-1]
    features['trend_strength'] = indicators['trend_strength'].iloc[-1]
    
    # Volume flow
    if len(indicators['obv']) > 20:
        features['obv_slope'] = np.polyfit(range(20), indicators['obv'].iloc[-20:].values, 1)[0]
    else:
        features['obv_slope'] = 0
    
    # Regime features
    regime_mapping = {
        'trending_up': 1,
        'trending_down': -1,
        'ranging': 0,
        'volatile': 0
    }
    features['regime'] = regime_mapping.get(regime_info['regime'], 0)
    
    return features

def _generate_comprehensive_signal(self, symbol: str, multi_tf: Dict, regime: Dict,
                                 patterns: Dict, news: Dict, ml_predictions: Dict,
                                 indicators: Dict) -> Dict:
    """Generate final trading signal with all components"""
    # Initialize component weights based on market regime
    regime_weights = regime['parameters']['preferred_timeframes']
    base_weights = {
        'multi_timeframe': 0.35,
        'regime': 0.20,
        'patterns': 0.15,
        'news': 0.10,
        'ml': 0.20
    }
    
    # Adjust weights based on regime
    if regime['regime'] == 'volatile':
        base_weights['multi_timeframe'] = 0.45
        base_weights['ml'] = 0.10
    elif regime['regime'] in ['trending_up', 'trending_down']:
        base_weights['regime'] = 0.25
        base_weights['patterns'] = 0.10
    
    # Calculate component scores
    components = {}
    
    # Multi-timeframe score
    if multi_tf['is_aligned']:
        tf_score = multi_tf['score'] * multi_tf['alignment_score']
    else:
        tf_score = multi_tf['score'] * 0.5
    components['multi_timeframe'] = (tf_score, base_weights['multi_timeframe'])
    
    # Regime score
    regime_score = 0
    if regime['regime'] == 'trending_up' and multi_tf['direction'] == 'long':
        regime_score = 0.8
    elif regime['regime'] == 'trending_down' and multi_tf['direction'] == 'short':
        regime_score = 0.8
    elif regime['regime'] == 'ranging':
        # Mean reversion in ranging markets
        rsi = indicators['rsi'].iloc[-1]
        if rsi < 30:
            regime_score = 0.6
        elif rsi > 70:
            regime_score = -0.6
    components['regime'] = (regime_score, base_weights['regime'])
    
    # Pattern score
    pattern_score = self._calculate_pattern_score(patterns, multi_tf['direction'])
    components['patterns'] = (pattern_score, base_weights['patterns'])
    
    # News score
    news_score = news['sentiment']
    if news['impact'] == 'high':
        news_score *= 1.5
    elif news['impact'] == 'low':
        news_score *= 0.5
    components['news'] = (news_score, base_weights['news'])
    
    # ML score
    ml_score = 0
    if ml_predictions and 'ensemble' in ml_predictions:
        ensemble = ml_predictions['ensemble']
        if ensemble['confidence'] > 0.6:
            ml_score = ensemble['prediction']
        else:
            ml_score = ensemble['prediction'] * 0.5
    components['ml'] = (ml_score, base_weights['ml'])
    
    # Calculate final weighted score
    total_weight = sum(weight for _, weight in components.values())
    final_score = sum(score * weight for score, weight in components.values()) / total_weight
    
    # Calculate confidence
    confidence = self._calculate_signal_confidence(
        multi_tf, regime, patterns, news, ml_predictions, components
    )
    
    # Determine if we should trade
    entry_conditions = self.config.ENTRY_CONDITIONS[symbol]
    
    # Apply regime-specific adjustments
    regime_params = regime['parameters']
    adjusted_threshold = entry_conditions['signal_threshold'] * regime_params.get('signal_threshold_multiplier', 1.0)
    
    should_trade = (
        abs(final_score) >= adjusted_threshold and
        confidence >= entry_conditions['confidence_required'] and
        multi_tf['is_aligned']
    )
    
    # Special conditions for XRP
    if symbol == 'XRPUSDT' and entry_conditions.get('extreme_rsi_only', False):
        rsi = indicators['rsi'].iloc[-1]
        if not (rsi < 25 or rsi > 75):
            should_trade = False
    
    # Determine direction
    if final_score > adjusted_threshold:
        direction = 'long'
    elif final_score < -adjusted_threshold:
        direction = 'short'
    else:
        direction = 'neutral'
        should_trade = False
    
    # Calculate expected move based on volatility and confidence
    base_move = abs(final_score) * 0.05
    volatility_adj = 1 + (indicators['atr_percent'].iloc[-1] / 100 - 0.02)
    expected_move = base_move * volatility_adj * (confidence / 100)
    
    # Apply regime position size adjustment
    position_size_multiplier = regime_params.get('position_size_multiplier', 1.0)
    
    return {
        'should_trade': should_trade,
        'direction': direction,
        'score': final_score,
        'confidence': confidence,
        'expected_move': expected_move,
        'components': {k: v[0] for k, v in components.items()},
        'weights': {k: v[1] for k, v in components.items()},
        'stop_loss': self.config.STOP_LOSS[symbol] * regime_params.get('stop_loss_multiplier', 1.0),
        'take_profit': self.config.TAKE_PROFIT[symbol],
        'position_size_multiplier': position_size_multiplier,
        'regime': regime['regime'],
        'alignment_score': multi_tf['alignment_score']
    }

def _calculate_pattern_score(self, patterns: Dict, preferred_direction: str) -> float:
    """Calculate score from detected patterns"""
    if not patterns:
        return 0
    
    score = 0
    pattern_count = 0
    
    for pattern_name, pattern_info in patterns.items():
        if not pattern_info.get('detected', False):
            continue
        
        pattern_count += 1
        expected_move = pattern_info.get('expected_move', 0)
        pattern_confidence = pattern_info.get('confidence', 0.5)
        
        # Check if pattern aligns with preferred direction
        if expected_move > 0 and preferred_direction == 'long':
            score += expected_move * pattern_confidence
        elif expected_move < 0 and preferred_direction == 'short':
            score += abs(expected_move) * pattern_confidence
        else:
            # Pattern conflicts with direction
            score -= abs(expected_move) * pattern_confidence * 0.5
    
    # Normalize by pattern count
    if pattern_count > 0:
        score /= pattern_count
    
    return np.clip(score, -1, 1)

def _calculate_signal_confidence(self, multi_tf: Dict, regime: Dict, patterns: Dict,
                               news: Dict, ml: Dict, components: Dict) -> float:
    """Calculate overall signal confidence"""
    # Base confidence from multi-timeframe analysis
    base_confidence = multi_tf.get('confidence', 50)
    
    # Regime confidence contribution
    regime_confidence = regime.get('confidence', 50)
    
    # ML confidence if available
    ml_confidence = 50
    if ml and 'ensemble' in ml:
        ml_confidence = ml['ensemble'].get('confidence', 50) * 100
    
    # Calculate weighted confidence
    confidence_weights = {
        'base': 0.4,
        'regime': 0.3,
        'ml': 0.2,
        'alignment': 0.1
    }
    
    weighted_confidence = (
        base_confidence * confidence_weights['base'] +
        regime_confidence * confidence_weights['regime'] +
        ml_confidence * confidence_weights['ml'] +
        multi_tf['alignment_score'] * 100 * confidence_weights['alignment']
    )
    
    # Adjust for component agreement
    component_scores = [score for score, _ in components.values()]
    positive_components = sum(1 for s in component_scores if s > 0.1)
    negative_components = sum(1 for s in component_scores if s < -0.1)
    
    if positive_components >= 4 or negative_components >= 4:
        weighted_confidence *= 1.2
    elif positive_components >= 3 or negative_components >= 3:
        weighted_confidence *= 1.1
    else:
        weighted_confidence *= 0.9
    
    # Penalty for high volatility
    if regime['regime'] == 'volatile':
        weighted_confidence *= 0.85
    
    # Penalty for news uncertainty
    if news.get('urgency') == 'immediate' and abs(news['sentiment']) < 0.3:
        weighted_confidence *= 0.8
    
    return min(95, max(20, weighted_confidence))

async def _save_prediction(self, symbol: str, df: pd.DataFrame, signal: Dict, 
                         indicators: Dict, regime: Dict, news: Dict):
    """Save prediction for performance tracking"""
    current_price = df['close'].iloc[-1]
    
    # Extract key indicator values
    indicator_snapshot = {
        'rsi': float(indicators['rsi'].iloc[-1]),
        'macd': float(indicators['macd'].iloc[-1]),
        'macd_signal': float(indicators['macd_signal'].iloc[-1]),
        'adx': float(indicators['adx'].iloc[-1]),
        'atr_percent': float(indicators['atr_percent'].iloc[-1]),
        'bb_position': float(indicators['price_position'].iloc[-1]),
        'volume_ratio': float(indicators['volume_ratio'].iloc[-1])
    }
    
    prediction_data = {
        'symbol': symbol,
        'timeframe': self._get_primary_timeframe(symbol),
        'price': current_price,
        'prediction': signal['expected_move'],
        'confidence': signal['confidence'],
        'direction': signal['direction'],
        'model_predictions': signal.get('ml_predictions', {}),
        'technical_score': signal['score'],
        'news_sentiment': news['sentiment'],
        'multi_tf_score': signal['alignment_score'],
        'regime': regime['regime'],
        'indicators': indicator_snapshot
    }
    
    self.db.save_prediction_with_indicators(prediction_data)

async def _execute_trade(self, symbol: str, signal: Dict, current_price: float):
    """Execute trade with comprehensive checks"""
    try:
        # Double-check risk limits
        risk_check = await self.risk_manager.check_risk_limits(symbol)
        if not risk_check['can_trade']:
            self.logger.warning(f"Risk check failed at execution time for {symbol}")
            return
        
        # Get available capital
        balance = await self.exchange.get_balance()
        total_capital = balance.get('USDT', {}).get('free', 0)
        
        if total_capital <= 100:  # Minimum capital requirement
            self.logger.warning(f"Insufficient USDT balance: ${total_capital:.2f}")
            await self.notifier.send_notification(
                f"⚠️ Low balance alert: ${total_capital:.2f}",
                priority='high'
            )
            return
        
        # Get open positions
        open_positions = self.db.get_open_positions()
        
        # Calculate allocation
        allocated_capital = self.risk_manager.calculate_position_allocation(
            symbol, total_capital, open_positions
        )
        
        # Apply signal's position size multiplier
        allocated_capital *= signal.get('position_size_multiplier', 1.0)
        
        if allocated_capital <= 50:  # Minimum position size
            self.logger.warning(f"Allocated capital too small for {symbol}: ${allocated_capital:.2f}")
            return
        
        # Log pre-trade state
        self.db.log_system_event('INFO', 'TradeExecution', 
                               f"Attempting to open position: {symbol}",
                               {
                                   'signal': signal,
                                   'allocated_capital': allocated_capital,
                                   'current_price': current_price
                               })
        
        # Open position
        result = await self.position_manager.open_position(
            symbol, signal, allocated_capital
        )
        
        if result:
            # Send success notification
            position_data = result['position_data']
            await self.notifier.send_trade_notification(
                symbol,
                f"open_{signal['direction']}",
                {
                    'price': current_price,
                    'quantity': position_data['quantity'],
                    'signal_strength': signal['score'],
                    'confidence': signal['confidence'],
                    'regime': signal['regime'],
                    'allocated_capital': allocated_capital
                }
            )
            
            self.logger.info(f"✅ Trade executed successfully for {symbol}")
            
            # Log successful trade
            self.db.log_system_event('INFO', 'TradeExecution',
                                   f"Position opened: {symbol}",
                                   {'result': result})
        else:
            self.logger.warning(f"Failed to execute trade for {symbol}")
            
    except Exception as e:
        self.logger.error(f"Trade execution error for {symbol}: {e}")
        self.db.log_system_event('ERROR', 'TradeExecution',
                               f"Trade execution failed: {symbol}",
                               {'error': str(e), 'traceback': traceback.format_exc()})
        await self.notifier.send_error_notification(
            f"Trade execution failed for {symbol}",
            str(e),
            "TradeExecution"
        )

async def _handle_emergency(self, symbol: str, news_sentiment: Dict):
    """Handle emergency news situation"""
    self.logger.warning(f"🚨 EMERGENCY SITUATION for {symbol}")
    
    # Log emergency
    self.db.log_system_event('CRITICAL', 'Emergency',
                           f"Emergency detected for {symbol}",
                           {'news': news_sentiment})
    
    # Get all positions for the symbol
    positions = self.db.get_open_positions(symbol)
    
    if positions:
        self.logger.info(f"Closing {len(positions)} positions for {symbol}")
        
        # Close all positions
        for position in positions:
            try:
                await self.position_manager._close_position(
                    position, 'emergency_news', position.get('current_price', 0)
                )
            except Exception as e:
                self.logger.error(f"Failed to close position {position['id']}: {e}")
    
    # Send emergency notification
    await self.notifier.send_notification(
        f"🚨 **EMERGENCY: {symbol}**\n\n"
        f"News: {news_sentiment.get('latest_news', 'Unknown')}\n"
        f"Sentiment: {news_sentiment.get('sentiment', 0):.2f}\n"
        f"Impact: {news_sentiment.get('impact', 'Unknown')}\n\n"
        f"Action: All positions closed",
        priority='emergency'
    )
    
    # Suspend trading for this symbol temporarily
    # This would need to be implemented with a cooldown system

async def run_trading_cycle(self):
    """Run one complete trading cycle"""
    cycle_start = datetime.now()
    self.logger.info("\n" + "="*60)
    self.logger.info(f"Trading cycle started at {cycle_start}")
    
    try:
        # Analyze each symbol
        for symbol in self.config.SYMBOLS:
            try:
                await self.analyze_and_trade(symbol)
                
                # Small delay between symbols to avoid rate limits
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error in trading cycle for {symbol}: {e}")
                await self.notifier.send_error_notification(
                    f"Trading cycle error for {symbol}",
                    str(e),
                    "TradingCycle"
                )
        
        # After analyzing all symbols, manage positions
        self.logger.info("\nManaging all positions...")
        await self.position_manager.manage_positions()
        
        # Update performance metrics
        await self.performance_analyzer.update_daily_performance()
        
        # Log cycle completion
        cycle_duration = (datetime.now() - cycle_start).seconds
        self.logger.info(f"Trading cycle completed in {cycle_duration} seconds")
        
        # Send performance update if it's been an hour
        if hasattr(self, '_last_report_time'):
            time_since_report = (datetime.now() - self._last_report_time).seconds / 3600
            if time_since_report >= 1:
                await self._send_performance_update()
                self._last_report_time = datetime.now()
        else:
            self._last_report_time = datetime.now()
            
    except Exception as e:
        self.logger.critical(f"Critical error in trading cycle: {e}")
        await self.notifier.send_error_notification(
            "Critical trading cycle error",
            str(e),
            "TradingCycle"
        )

async def _send_performance_update(self):
    """Send hourly performance update"""
    try:
        # Get current stats
        daily_perf = self.db.get_daily_performance()
        open_positions = self.db.get_open_positions()
        
        # Format update
        update = f"""
📊 Hourly Update

Open Positions: {len(open_positions)}
Daily P&L: {daily_perf['total_pnl_percent']:+.2f}%
Daily Trades: {daily_perf['total_trades']}
Win Rate: {daily_perf['win_rate']:.1%}
"""
      # Add position details if any
      if open_positions:
          update += "\n**Current Positions:**\n"
          for pos in open_positions:
              symbol = pos['symbol']
              side = pos['side']
              pnl = self.position_manager._calculate_pnl(
                  pos, pos.get('current_price', pos['entry_price'])
              )
              update += f"• {symbol} {side.upper()}: {pnl['pnl_percent']:+.2f}%\n"
      
      await self.notifier.send_notification(update, priority='normal')
      
  except Exception as e:
      self.logger.error(f"Failed to send performance update: {e}")
def get_system_status(self) -> Dict:
"""Get comprehensive system status"""
uptime = datetime.now() - self.startup_time
  return {
      'status': 'running' if self.is_running else 'stopped',
      'uptime_hours': uptime.total_seconds() / 3600,
      'exchange_connected': self.exchange.ws_connected,
      'ml_enabled': self.config.ENABLE_ML_MODELS,
      'last_analysis': {
          symbol: time.isoformat() if isinstance(time, datetime) else str(time)
          for symbol, time in self.last_analysis_time.items()
      }
  }


# ==============================
# Web Dashboard API (Enhanced)
# ==============================
# app = FastAPI(title="Bitget Trading System API", version="2.0")
# Middleware
# app.add_middleware(
# CORSMiddleware,
# allow_origins=[""],
# allow_credentials=True,
# allow_methods=[""],
# allow_headers=["*"],
)
Global reference
trading_engine: Optional[AdvancedTradingEngine] = None
WebSocket manager for multiple connections
class ConnectionManager:
def init(self):
self.active_connections: List[WebSocket] = []
self._lock = asyncio.Lock()
async def connect(self, websocket: WebSocket):
    await websocket.accept()
    async with self._lock:
        self.active_connections.append(websocket)

async def disconnect(self, websocket: WebSocket):
    async with self._lock:
        self.active_connections.remove(websocket)

async def broadcast(self, message: dict):
    """Send message to all connected clients"""
    async with self._lock:
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)
manager = ConnectionManager()
@app.on_event("startup")
async def startup_event():
"""Initialize WebSocket broadcaster"""
asyncio.create_task(websocket_broadcaster())
async def websocket_broadcaster():
"""Broadcast updates to all WebSocket clients"""
while True:
try:
if trading_engine and manager.active_connections:
status = await get_detailed_status()
await manager.broadcast(status)
await asyncio.sleep(1)
except Exception as e:
logging.error(f"WebSocket broadcast error: {e}")
await asyncio.sleep(5)
@app.get("/", response_class=HTMLResponse)
async def root():
"""Serve dashboard HTML"""
return DASHBOARD_HTML
@app.get("/api/status")
async def get_status():
"""Get system status"""
return await get_detailed_status()
async def get_detailed_status():
"""Get detailed system status"""
if not trading_engine:
return {"status": "not_initialized", "error": "System not started"}
try:
    # Get balance
    balance = await trading_engine.exchange.get_balance()
    usdt_balance = balance.get('USDT', {}).get('free', 0)
    
    # Get positions with current P&L
    positions = trading_engine.db.get_open_positions()
    for pos in positions:
        if 'current_price' in pos:
            pnl_data = trading_engine.position_manager._calculate_pnl(
                pos, pos['current_price']
            )
            pos['pnl'] = pnl_data['pnl_value']
            pos['pnl_percent'] = pnl_data['pnl_percent'] * 100
    
    # Get daily performance
    daily_perf = trading_engine.db.get_daily_performance()
    
    # Get trade counts by symbol
    trade_counts = {}
    for symbol in trading_engine.config.SYMBOLS:
        counts = trading_engine.db.get_symbol_trades_today(symbol)
        limits = trading_engine.config.DAILY_TRADE_LIMITS[symbol]
        trade_counts[symbol] = f"{counts['total']}/{limits['max_trades']}"
    
    # Get system status
    system_status = trading_engine.get_system_status()
    
    # Calculate API latency (placeholder)
    api_latency = 45 if trading_engine.exchange.ws_connected else 150
    
    return {
        "type": "update",
        "timestamp": datetime.now().isoformat(),
        "status": system_status['status'],
        "balance": usdt_balance,
        "positions": positions,
        "metrics": {
            "daily_pnl": daily_perf['total_pnl_percent'],
            "win_rate": daily_perf['win_rate'] * 100,
            "sharpe_ratio": daily_perf['sharpe_ratio'],
            "max_drawdown": daily_perf['max_drawdown'],
            "daily_trades": daily_perf['total_trades'],
            "total_volume": daily_perf['total_volume'],
            "total_fees": daily_perf['total_fees']
        },
        "system": {
            "btc_trades": trade_counts.get('BTCUSDT', '0/0'),
            "eth_trades": trade_counts.get('ETHUSDT', '0/0'),
            "xrp_trades": trade_counts.get('XRPUSDT', '0/0'),
            "api_latency": api_latency,
            "uptime_hours": round(system_status['uptime_hours'], 2),
            "ws_connected": system_status['exchange_connected'],
            "ml_enabled": system_status['ml_enabled']
        }
    }
except Exception as e:
    logging.error(f"Error getting status: {e}")
    return {
        "status": "error",
        "error": str(e),
        "timestamp": datetime.now().isoformat()
    }
@app.get("/api/performance/{days}")
async def get_performance(days: int = 7):
"""Get performance report"""
if not trading_engine:
raise HTTPException(status_code=503, detail="System not initialized")
try:
    report = trading_engine.performance_analyzer.generate_performance_report(days)
    return {
        "success": True,
        "report": report,
        "days": days
    }
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/positions")
async def get_positions():
"""Get all positions with details"""
if not trading_engine:
raise HTTPException(status_code=503, detail="System not initialized")
positions = trading_engine.db.get_open_positions()

# Enhance with current market data
for pos in positions:
    symbol = pos['symbol']
    current_price = trading_engine.exchange.get_current_price(symbol)
    if current_price:
        pos['current_price'] = current_price
        pnl_data = trading_engine.position_manager._calculate_pnl(pos, current_price)
        pos['unrealized_pnl'] = pnl_data['pnl_value']
        pos['unrealized_pnl_percent'] = pnl_data['pnl_percent'] * 100

return {"positions": positions}
@app.post("/api/manual/close/{symbol}")
async def close_position_manual(symbol: str):
"""Manually close a position"""
if not trading_engine:
raise HTTPException(status_code=503, detail="System not initialized")
# Verify API key (implement authentication)
# For now, just proceed

positions = trading_engine.db.get_open_positions(symbol)
if not positions:
    raise HTTPException(status_code=404, detail=f"No open positions for {symbol}")

results = []
for pos in positions:
    try:
        await trading_engine.position_manager._close_position(
            pos, 'manual_close', pos.get('current_price', 0)
        )
        results.append({"position_id": pos['id'], "status": "closed"})
    except Exception as e:
        results.append({"position_id": pos['id'], "status": "error", "error": str(e)})

return {"results": results}
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
"""WebSocket endpoint for real-time updates"""
await manager.connect(websocket)
try:
# Send initial status
status = await get_detailed_status()
await websocket.send_json(status)
    # Keep connection alive
    while True:
        # Wait for any message from client (ping/pong)
        data = await websocket.receive_text()
        
        # Echo back as pong
        if data == "ping":
            await websocket.send_text("pong")
            
except WebSocketDisconnect:
    await manager.disconnect(websocket)
except Exception as e:
    logging.error(f"WebSocket error: {e}")
    await manager.disconnect(websocket)
@app.get("/api/logs/recent")
async def get_recent_logs(limit: int = 100):
"""Get recent system logs"""
if not trading_engine:
raise HTTPException(status_code=503, detail="System not initialized")
with trading_engine.db._get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM system_logs 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (limit,))
    
    logs = [dict(row) for row in cursor.fetchall()]

return {"logs": logs}
@app.get("/health")
async def health_check():
"""Health check endpoint"""
return {
"status": "healthy" if trading_engine and trading_engine.is_running else "unhealthy",
"timestamp": datetime.now().isoformat()
}
# ==============================
# Main Application
# ==============================
class BitgetTradingApplication:
"""Main application orchestrator"""
def __init__(self, config: TradingConfig):
    self.config = config
    self.engine = AdvancedTradingEngine(config)
    self.scheduler = AsyncIOScheduler(timezone=timezone(config.TIMEZONE))
    self.logger = logging.getLogger(__name__)
    
    # Set global reference for API
    global trading_engine
    trading_engine = self.engine

async def initialize(self):
    """Initialize application"""
    try:
        await self.engine.initialize()
        
        # Run initial analysis cycle
        await self.engine.run_trading_cycle()
        
        self.logger.info("Application initialized successfully")
        
    except Exception as e:
        self.logger.critical(f"Failed to initialize application: {e}")
        raise

def setup_schedule(self):
    """Setup trading schedule"""
    # Main trading cycles - every 15 minutes
    self.scheduler.add_job(
        self.engine.run_trading_cycle,
        'cron',
        minute='*/15',
        id='main_trading_cycle',
        misfire_grace_time=300
    )
    
    # Position management - every 5 minutes
    self.scheduler.add_job(
        self.engine.position_manager.manage_positions,
        'cron',
        minute='*/5',
        id='position_management',
        misfire_grace_time=120
    )
    
    # Performance update - every hour
    self.scheduler.add_job(
        self.engine.performance_analyzer.update_daily_performance,
        'cron',
        minute=0,
        id='performance_update'
    )
    
    # Daily report - 9 AM and 9 PM
    self.scheduler.add_job(
        self._send_daily_report,
        'cron',
        hour='9,21',
        minute=0,
        id='daily_report'
    )
    
    # Model performance update - every 4 hours
    if self.config.ENABLE_ML_MODELS:
        self.scheduler.add_job(
            self._update_ml_performance,
            'cron',
            hour='*/4',
            id='ml_performance_update'
        )
    
    self.logger.info("Schedule configured:")
    self.logger.info("- Main cycle: Every 15 minutes")
    self.logger.info("- Position check: Every 5 minutes")
    self.logger.info("- Performance update: Every hour")
    self.logger.info("- Daily report: 9:00 AM and 9:00 PM")

async def _send_daily_report(self):
    """Send daily performance report"""
    try:
        report = self.engine.performance_analyzer.generate_performance_report(1)
        await self.engine.notifier.send_daily_report(report)
    except Exception as e:
        self.logger.error(f"Failed to send daily report: {e}")

async def _update_ml_performance(self):
    """Update ML model performance metrics"""
    # This would track prediction accuracy over time
    pass

async def start_api_server(self):
    """Start FastAPI server"""
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )
    server = uvicorn.Server(config)
    await server.serve()

async def start(self):
    """Start the application"""
    try:
        # Initialize
        await self.initialize()
        
        # Setup schedule
        self.setup_schedule()
        self.scheduler.start()
        
        # Start API server in background
        api_task = asyncio.create_task(self.start_api_server())
        
        self.logger.info("\n" + "="*60)
        self.logger.info("🚀 Bitget Trading System v2.0 Started")
        self.logger.info("📊 Dashboard: http://localhost:8000")
        self.logger.info("📡 WebSocket: ws://localhost:8000/ws")
        self.logger.info("="*60 + "\n")
        
        # Keep running
        while self.engine.is_running:
            await asyncio.sleep(60)
            
            # Periodic health check
            if hasattr(self, '_last_health_check'):
                if (datetime.now() - self._last_health_check).seconds > 300:
                    await self._health_check()
            else:
                self._last_health_check = datetime.now()
            
    except KeyboardInterrupt:
        self.logger.info("Received shutdown signal...")
        await self.shutdown()
        
    except Exception as e:
        self.logger.critical(f"Critical error in main loop: {e}")
        await self.engine.notifier.send_error_notification(
            "System critical error",
            str(e),
            "Main"
        )
        raise

async def _health_check(self):
    """Perform system health check"""
    try:
        # Check exchange connection
        if not self.engine.exchange.ws_connected:
            self.logger.warning("WebSocket disconnected, attempting reconnect...")
            # Exchange will auto-reconnect
        
        # Check database
        self.engine.db.get_daily_performance()
        
        # Update last check time
        self._last_health_check = datetime.now()
        
    except Exception as e:
        self.logger.error(f"Health check failed: {e}")

async def shutdown(self):
    """Gracefully shutdown the application"""
    self.logger.info("Shutting down trading system...")
    
    # Stop trading
    self.engine.is_running = False
    
    # Stop scheduler
    self.scheduler.shutdown(wait=False)
    
    # Close all positions (optional - comment out if you want to keep positions)
    # await self._close_all_positions()
    
    # Save ML models
    if self.config.ENABLE_ML_MODELS:
        self.engine.ml_manager.save_models()
    
    # Final notification
    await self.engine.notifier.send_notification(
        "🛑 Trading system shutdown complete",
        priority='high'
    )
    
    # Shutdown notification system
    await self.engine.notifier.shutdown()
    
    self.logger.info("Shutdown complete")

async def _close_all_positions(self):
    """Close all open positions"""
    positions = self.engine.db.get_open_positions()
    for pos in positions:
        try:
            await self.engine.position_manager._close_position(
                pos, 'system_shutdown', pos.get('current_price', 0)
            )
        except Exception as e:
            self.logger.error(f"Failed to close position {pos['id']}: {e}")
# ==============================
# Entry Point
# ==============================
def setup_logging(config: TradingConfig):
"""Setup comprehensive logging"""
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# Create logs directory
os.makedirs('logs', exist_ok=True)

# File handler with rotation
from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler(
    'logs/trading_system.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(log_format))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(log_format))

# Configure root logger
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    handlers=[file_handler, console_handler]
)

# Reduce noise from some libraries
logging.getLogger('ccxt').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
async def main():
"""Main entry point"""
try:
# Load configuration
config = TradingConfig.from_env()
    # Validate configuration
    missing = config.validate()
    if missing:
        print(f"❌ Missing configuration: {', '.join(missing)}")
        print("Please check your .env file")
        print("\nRequired variables:")
        for var in missing:
            print(f"  - {var}")
        return
    
    # Setup logging
    setup_logging(config)
    
    # Print startup banner
    print("\n" + "="*60)
    print("🚀 Bitget Auto Trading System v2.0")
    print("="*60)
    print(f"📊 Symbols: {', '.join(config.SYMBOLS)}")
    print(f"💰 Allocation: BTC 70%, ETH 20%, XRP 10%")
    print(f"🔧 Leverage: BTC {config.LEVERAGE['BTCUSDT']}x, "
          f"ETH {config.LEVERAGE['ETHUSDT']}x, "
          f"XRP {config.LEVERAGE['XRPUSDT']}x")
    print(f"🤖 ML Models: {'Enabled' if config.ENABLE_ML_MODELS else 'Disabled'}")
    print("="*60 + "\n")
    
    # Create and start application
    app = BitgetTradingApplication(config)
    await app.start()
    
except Exception as e:
    print(f"\n❌ Fatal error: {e}")
    traceback.print_exc()
    sys.exit(1)
if __name__ == "__main__":
# Handle platform-specific event loop policies
if sys.platform == 'win32':
# Windows specific
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# Run the application
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\n👋 Goodbye!")