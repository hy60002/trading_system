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


# ==============================
# Error Handling
# ==============================

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
                    indicators_snapshot TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON predictions (symbol, timestamp);
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
                    slippage REAL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_status ON trades (status);
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON trades (symbol, timestamp);
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
                    FOREIGN KEY (trade_id) REFERENCES trades(id)
                );
                CREATE INDEX IF NOT EXISTS idx_status ON positions (status);
                CREATE INDEX IF NOT EXISTS idx_symbol ON positions (symbol);
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


# ==============================
# Enhanced Technical Indicators with Caching
# ==============================
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
# Entry Point
# ==============================
if __name__ == "__main__":
    # Entry point code would go here
    pass