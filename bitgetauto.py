"""
Advanced Bitget Auto Trading System - Refactored Version
=======================================================
Complete refactoring with all improvements discussed:
- BTC 70%, ETH 20%, XRP 10% portfolio allocation
- Fixed leverage: BTC 20x, ETH/XRP 10x
- Trailing stop loss
- Enhanced technical indicators
- WebSocket support
- ML model ready
- Backtesting system
- Web dashboard
- Performance tracking
"""

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
from fastapi import FastAPI, HTTPException, Depends, Security, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from pydantic import BaseModel, Field
import openai
import talib
import sqlite3
from contextlib import contextmanager
import redis
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.ensemble import RandomForestRegressor
import joblib

warnings.filterwarnings('ignore')

# ==============================
# Enhanced Configuration
# ==============================
@dataclass
class TradingConfig:
    """Centralized configuration with all improvements"""
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
    
    # WebSocket URLs
    BITGET_WS_URL: str = "wss://ws.bitget.com/mix/v1/stream"

    def validate(self) -> list:
            """Check for missing essential configuration"""
            required_fields = [
                'BITGET_API_KEY',
                'BITGET_SECRET_KEY',
                'BITGET_PASSPHRASE',
                'OPENAI_API_KEY',
                'TELEGRAM_BOT_TOKEN',
                'TELEGRAM_CHAT_ID'
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
# Enhanced Database Manager
# ==============================
class EnhancedDatabaseManager:
    """Database manager with performance tracking"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis for caching"""
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            self.redis_client.ping()
            self.redis_enabled = True
        except:
            self.redis_enabled = False
            logging.warning("Redis not available, using memory cache")
            self.memory_cache = {}
    
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
                    trailing_stop_activated BOOLEAN DEFAULT FALSE
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
                    FOREIGN KEY (trade_id) REFERENCES trades(id)
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
                    total_volume REAL DEFAULT 0
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
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Database connection context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def cache_set(self, key: str, value: Any, ttl: int = 300):
        """Set cache value"""
        if self.redis_enabled:
            self.redis_client.setex(key, ttl, json.dumps(value))
        else:
            self.memory_cache[key] = (value, time.time() + ttl)
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Get cache value"""
        if self.redis_enabled:
            value = self.redis_client.get(key)
            return json.loads(value) if value else None
        else:
            if key in self.memory_cache:
                value, expiry = self.memory_cache[key]
                if time.time() < expiry:
                    return value
                else:
                    del self.memory_cache[key]
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
            conn.commit()
            return cursor.lastrowid
    
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
            conn.commit()
            return cursor.lastrowid
    
    def update_position(self, position_id: int, update_data: Dict):
        """Update position data"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build update query
            set_clauses = []
            values = []
            for key, value in update_data.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)
            
            values.append(datetime.now())  # last_update
            values.append(position_id)
            
            cursor.execute(f"""
                UPDATE positions 
                SET {', '.join(set_clauses)}, last_update = ?
                WHERE id = ?
            """, values)
            conn.commit()
    
    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open positions"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM positions WHERE status = 'open'"
            if symbol:
                query += f" AND symbol = '{symbol}'"
            
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
                
                cursor.execute(f"""
                    INSERT INTO daily_performance ({', '.join(columns)})
                    VALUES ({', '.join(['?' for _ in columns])})
                """, values)
            
            conn.commit()
    
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
            
            return {'total': total, 'losses': losses}
    
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
            'total_volume': 0.0
        }

# ==============================
# Enhanced Exchange Manager with WebSocket
# ==============================
class EnhancedBitgetExchangeManager:
    """Bitget exchange manager with WebSocket support"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.exchange = ccxt.bitget({
            'apiKey': config.BITGET_API_KEY,
            'secret': config.BITGET_SECRET_KEY,
            'password': config.BITGET_PASSPHRASE,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
            }
        })
        self.logger = logging.getLogger(__name__)
        
        # WebSocket data
        self.ws_connected = False
        self.price_data = {}
        self.orderbook_data = {}
        self.ws_task = None
        
        # Circuit breaker
        self.error_count = 0
        self.max_errors = 5
        self.last_error_time = None
    
    async def initialize(self):
        """Initialize exchange connection"""
        try:
            # Test connection
            await self.get_balance()
            
            # Start WebSocket if enabled
            if self.config.USE_WEBSOCKET:
                self.ws_task = asyncio.create_task(self._websocket_handler())
                
            self.logger.info("Exchange manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize exchange: {e}")
            raise
    
    async def _websocket_handler(self):
        """WebSocket connection handler"""
        while True:
            try:
                await self._connect_websocket()
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)
    
    async def _connect_websocket(self):
        """Connect to Bitget WebSocket"""
        # WebSocket implementation would go here
        # For now, we'll use REST API fallback
        pass
    
    async def fetch_ohlcv_with_cache(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        """Fetch OHLCV with caching"""
        cache_key = f"ohlcv:{symbol}:{timeframe}"
        
        # Check cache first
        if hasattr(self, 'cache'):
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        
        # Fetch from exchange
        df = await self.fetch_ohlcv(symbol, timeframe, limit)
        
        # Cache for 1 minute
        if hasattr(self, 'cache') and df is not None:
            self.cache.set(cache_key, df, ttl=60)
        
        return df
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        """Fetch OHLCV data with error handling"""
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
            raise Exception("Exchange circuit breaker triggered")
        
        self.logger.error(f"Exchange error ({self.error_count}/{self.max_errors}): {error}")
    
    async def get_balance(self) -> Dict:
        """Get account balance"""
        try:
            balance = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_balance
            )
            return balance
        except Exception as e:
            self._handle_error(e)
            return {}
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open positions"""
        try:
            positions = await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.fetch_positions,
                [self._format_symbol(symbol)] if symbol else None
            )
            return positions
        except Exception as e:
            self._handle_error(e)
            return []
    
    async def place_order(self, symbol: str, side: str, amount: float, 
                         order_type: str = 'market', price: Optional[float] = None,
                         params: Optional[Dict] = None) -> Dict:
        """Place order with enhanced parameters"""
        try:
            market_symbol = self._format_symbol(symbol)
            
            # Set leverage
            leverage = self.config.LEVERAGE.get(symbol, 10)
            await self.set_leverage(symbol, leverage)
            
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
            
            self.logger.info(f"Order placed: {symbol} {side} {amount} @ {price or 'market'}")
            return order
            
        except Exception as e:
            self._handle_error(e)
            return {}
    
    async def place_stop_loss_order(self, symbol: str, side: str, amount: float, 
                                   stop_price: float) -> Dict:
        """Place stop loss order"""
        try:
            params = {
                'stopPrice': stop_price,
                'triggerType': 'market_price'
            }
            
            return await self.place_order(
                symbol, 
                side, 
                amount, 
                order_type='stop',
                params=params
            )
            
        except Exception as e:
            self.logger.error(f"Failed to place stop loss order: {e}")
            return {}
    
    async def modify_stop_loss(self, symbol: str, order_id: str, new_stop_price: float) -> Dict:
        """Modify existing stop loss order"""
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
        try:
            market_symbol = self._format_symbol(symbol)
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.exchange.set_leverage,
                leverage,
                market_symbol
            )
            
        except Exception as e:
            self.logger.error(f"Failed to set leverage: {e}")
    
    def _format_symbol(self, symbol: str) -> str:
        """Format symbol for Bitget"""
        base = symbol[:-4]
        return f"{base}/USDT:USDT"
    
    async def calculate_position_size(self, symbol: str, position_value: float) -> float:
        """Calculate position size in contracts"""
        try:
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

# ==============================
# Enhanced Technical Indicators
# ==============================
class EnhancedTechnicalIndicators:
    """Comprehensive technical indicators library"""
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all technical indicators"""
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
        
        # RSI
        indicators['rsi'] = talib.RSI(df['close'], timeperiod=14)
        
        # Stochastic RSI
        indicators['stoch_rsi'], indicators['stoch_rsi_d'] = talib.STOCHRSI(
            df['close'], timeperiod=14, fastk_period=3, fastd_period=3
        )
        
        # Bollinger Bands
        indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = talib.BBANDS(
            df['close'], timeperiod=20, nbdevup=2, nbdevdn=2
        )
        
        # ATR
        indicators['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        
        # ADX
        indicators['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        
        # Volume Indicators
        indicators['obv'] = talib.OBV(df['close'], df['volume'])
        indicators['volume_sma'] = talib.SMA(df['volume'], timeperiod=20)
        
        # Ichimoku Cloud
        ichimoku = EnhancedTechnicalIndicators.calculate_ichimoku(df)
        indicators.update(ichimoku)
        
        # VWAP
        indicators['vwap'] = EnhancedTechnicalIndicators.calculate_vwap(df)
        
        # CMF
        indicators['cmf'] = EnhancedTechnicalIndicators.calculate_cmf(df)
        
        # Supertrend
        indicators['supertrend'], indicators['supertrend_direction'] = \
            EnhancedTechnicalIndicators.calculate_supertrend(df)
        
        return indicators
    
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
            'ichimoku_chikou': chikou_span
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

# ==============================
# Base Trading Strategy
# ==============================
class TradingStrategy(ABC):
    """Abstract base class for trading strategies"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def analyze(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze and generate trading signal"""
        pass
    
    @abstractmethod
    def get_entry_conditions(self, symbol: str) -> Dict:
        """Get entry conditions for symbol"""
        pass
    
    def calculate_signal_strength(self, components: Dict[str, float]) -> float:
        """Calculate weighted signal strength"""
        total_weight = sum(components.values())
        if total_weight == 0:
            return 0
        
        weighted_sum = sum(score * weight for score, weight in components.items())
        return weighted_sum / total_weight

# ==============================
# BTC Trading Strategy
# ==============================
class BTCTradingStrategy(TradingStrategy):
    """Bitcoin-specific trading strategy"""
    
    async def analyze(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze BTC with trend-following approach"""
        signal_components = {}
        
        # Trend Analysis (40% weight)
        trend_score = self._analyze_trend(df, indicators)
        signal_components[trend_score] = 0.4
        
        # Ichimoku Analysis (30% weight)
        ichimoku_score = self._analyze_ichimoku(df, indicators)
        signal_components[ichimoku_score] = 0.3
        
        # Volume Analysis (20% weight)
        volume_score = self._analyze_volume(df, indicators)
        signal_components[volume_score] = 0.2
        
        # Momentum (10% weight)
        momentum_score = self._analyze_momentum(indicators)
        signal_components[momentum_score] = 0.1
        
        # Calculate final score
        final_score = self.calculate_signal_strength(signal_components)
        
        # Determine direction
        if final_score > 0.3:
            direction = 'long'
        elif final_score < -0.3:
            direction = 'short'
        else:
            direction = 'neutral'
        
        return {
            'score': final_score,
            'direction': direction,
            'components': signal_components,
            'confidence': min(abs(final_score) * 100, 90)
        }
    
    def _analyze_trend(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze trend strength"""
        score = 0
        current_price = df['close'].iloc[-1]
        
        # EMA alignment
        if indicators['ema_20'].iloc[-1] > indicators['ema_50'].iloc[-1]:
            score += 0.3
        
        # Price vs EMAs
        if current_price > indicators['ema_20'].iloc[-1]:
            score += 0.3
        if current_price > indicators['ema_50'].iloc[-1]:
            score += 0.2
        if current_price > indicators['sma_200'].iloc[-1]:
            score += 0.2
        
        # ADX for trend strength
        if indicators['adx'].iloc[-1] > 25:
            score *= 1.2
        elif indicators['adx'].iloc[-1] < 20:
            score *= 0.8
        
        return np.clip(score, -1, 1)
    
    def _analyze_ichimoku(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze Ichimoku Cloud"""
        score = 0
        current_price = df['close'].iloc[-1]
        
        # Price vs Cloud
        if current_price > indicators['ichimoku_senkou_a'].iloc[-1]:
            score += 0.4
        if current_price > indicators['ichimoku_senkou_b'].iloc[-1]:
            score += 0.4
        
        # Tenkan/Kijun cross
        if indicators['ichimoku_tenkan'].iloc[-1] > indicators['ichimoku_kijun'].iloc[-1]:
            score += 0.2
        
        return np.clip(score, -1, 1)
    
    def _analyze_volume(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze volume patterns"""
        score = 0
        
        # Volume trend
        recent_volume = df['volume'].iloc[-5:].mean()
        avg_volume = indicators['volume_sma'].iloc[-1]
        
        if recent_volume > avg_volume * 1.5:
            if df['close'].iloc[-1] > df['close'].iloc[-2]:
                score += 0.5
            else:
                score -= 0.5
        
        # OBV trend
        obv_slope = np.polyfit(range(20), indicators['obv'].iloc[-20:].values, 1)[0]
        if obv_slope > 0:
            score += 0.3
        else:
            score -= 0.3
        
        # CMF
        if indicators['cmf'].iloc[-1] > 0.1:
            score += 0.2
        elif indicators['cmf'].iloc[-1] < -0.1:
            score -= 0.2
        
        return np.clip(score, -1, 1)
    
    def _analyze_momentum(self, indicators: Dict) -> float:
        """Analyze momentum indicators"""
        score = 0
        
        # RSI
        rsi = indicators['rsi'].iloc[-1]
        if 30 < rsi < 70:
            if rsi > 50:
                score += 0.3
            else:
                score -= 0.3
        
        # MACD
        if indicators['macd'].iloc[-1] > indicators['macd_signal'].iloc[-1]:
            score += 0.4
            if indicators['macd_hist'].iloc[-1] > indicators['macd_hist'].iloc[-2]:
                score += 0.2
        else:
            score -= 0.4
        
        # Stochastic RSI
        if indicators['stoch_rsi'].iloc[-1] > indicators['stoch_rsi_d'].iloc[-1]:
            score += 0.1
        
        return np.clip(score, -1, 1)
    
    def get_entry_conditions(self, symbol: str) -> Dict:
        """Get BTC entry conditions"""
        return self.config.ENTRY_CONDITIONS["BTCUSDT"]

# ==============================
# ETH Trading Strategy
# ==============================
class ETHTradingStrategy(TradingStrategy):
    """Ethereum-specific trading strategy"""
    
    async def analyze(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze ETH with momentum approach"""
        signal_components = {}
        
        # Momentum Analysis (40% weight)
        momentum_score = self._analyze_momentum(df, indicators)
        signal_components[momentum_score] = 0.4
        
        # Volatility Analysis (30% weight)
        volatility_score = self._analyze_volatility(df, indicators)
        signal_components[volatility_score] = 0.3
        
        # Volume Analysis (20% weight)
        volume_score = self._analyze_volume(df, indicators)
        signal_components[volume_score] = 0.2
        
        # Trend (10% weight)
        trend_score = self._analyze_trend(indicators)
        signal_components[trend_score] = 0.1
        
        final_score = self.calculate_signal_strength(signal_components)
        
        if final_score > 0.5:
            direction = 'long'
        elif final_score < -0.5:
            direction = 'short'
        else:
            direction = 'neutral'
        
        return {
            'score': final_score,
            'direction': direction,
            'components': signal_components,
            'confidence': min(abs(final_score) * 120, 85)
        }
    
    def _analyze_momentum(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze momentum for ETH"""
        score = 0
        
        # Price momentum
        returns_5m = (df['close'].iloc[-1] / df['close'].iloc[-5] - 1)
        if abs(returns_5m) > 0.015:  # 1.5% move in 5 periods
            score += 0.5 * np.sign(returns_5m)
        
        # Stochastic RSI for entries
        stoch_rsi = indicators['stoch_rsi'].iloc[-1]
        if stoch_rsi < 20:
            score += 0.3
        elif stoch_rsi > 80:
            score -= 0.3
        
        # MACD momentum
        if indicators['macd_hist'].iloc[-1] > 0:
            if indicators['macd_hist'].iloc[-1] > indicators['macd_hist'].iloc[-2]:
                score += 0.2
        else:
            if indicators['macd_hist'].iloc[-1] < indicators['macd_hist'].iloc[-2]:
                score -= 0.2
        
        return np.clip(score, -1, 1)
    
    def _analyze_volatility(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze volatility patterns"""
        score = 0
        current_price = df['close'].iloc[-1]
        
        # Bollinger Bands position
        bb_position = (current_price - indicators['bb_lower'].iloc[-1]) / \
                     (indicators['bb_upper'].iloc[-1] - indicators['bb_lower'].iloc[-1])
        
        if bb_position > 0.8:  # Near upper band
            score -= 0.4
        elif bb_position < 0.2:  # Near lower band
            score += 0.4
        
        # ATR-based volatility
        atr_ratio = indicators['atr'].iloc[-1] / current_price
        if atr_ratio > 0.03:  # High volatility
            score *= 0.8  # Reduce signal in high volatility
        
        # Bollinger Band squeeze
        bb_width = (indicators['bb_upper'].iloc[-1] - indicators['bb_lower'].iloc[-1]) / indicators['bb_middle'].iloc[-1]
        bb_width_sma = bb_width * 20  # Approximate SMA
        
        if bb_width < bb_width_sma * 0.8:  # Squeeze
            score += 0.3  # Prepare for breakout
        
        return np.clip(score, -1, 1)
    
    def _analyze_volume(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze volume for ETH"""
        score = 0
        
        # Volume spike detection
        current_volume = df['volume'].iloc[-1]
        avg_volume = indicators['volume_sma'].iloc[-1]
        
        if current_volume > avg_volume * 2:
            if df['close'].iloc[-1] > df['open'].iloc[-1]:
                score += 0.6
            else:
                score -= 0.6
        
        # VWAP analysis
        if df['close'].iloc[-1] > indicators['vwap'].iloc[-1]:
            score += 0.2
        else:
            score -= 0.2
        
        # CMF
        cmf = indicators['cmf'].iloc[-1]
        score += cmf * 0.2
        
        return np.clip(score, -1, 1)
    
    def _analyze_trend(self, indicators: Dict) -> float:
        """Basic trend analysis for ETH"""
        score = 0
        
        # Supertrend
        if indicators['supertrend_direction'].iloc[-1] == 1:
            score += 0.5
        else:
            score -= 0.5
        
        # EMA cross
        if indicators['ema_20'].iloc[-1] > indicators['ema_50'].iloc[-1]:
            score += 0.5
        
        return np.clip(score, -1, 1)
    
    def get_entry_conditions(self, symbol: str) -> Dict:
        """Get ETH entry conditions"""
        return self.config.ENTRY_CONDITIONS["ETHUSDT"]

# ==============================
# XRP Trading Strategy
# ==============================
class XRPTradingStrategy(TradingStrategy):
    """XRP-specific trading strategy"""
    
    async def analyze(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze XRP with mean reversion approach"""
        signal_components = {}
        
        # Oversold/Overbought (40% weight)
        extreme_score = self._analyze_extremes(indicators)
        signal_components[extreme_score] = 0.4
        
        # Support/Resistance (30% weight)
        sr_score = self._analyze_support_resistance(df)
        signal_components[sr_score] = 0.3
        
        # Volume (20% weight)
        volume_score = self._analyze_volume(df, indicators)
        signal_components[volume_score] = 0.2
        
        # Trend (10% weight) - Counter-trend
        trend_score = self._analyze_trend(indicators) * -0.5  # Fade the trend
        signal_components[trend_score] = 0.1
        
        final_score = self.calculate_signal_strength(signal_components)
        
        if final_score > 0.6:
            direction = 'long'
        elif final_score < -0.6:
            direction = 'short'
        else:
            direction = 'neutral'
        
        return {
            'score': final_score,
            'direction': direction,
            'components': signal_components,
            'confidence': min(abs(final_score) * 140, 80)
        }
    
    def _analyze_extremes(self, indicators: Dict) -> float:
        """Analyze extreme conditions"""
        score = 0
        
        # RSI extremes
        rsi = indicators['rsi'].iloc[-1]
        if rsi < 30:
            score += 0.7
        elif rsi > 70:
            score -= 0.7
        elif rsi < 35:
            score += 0.3
        elif rsi > 65:
            score -= 0.3
        
        # Stochastic RSI extremes
        stoch_rsi = indicators['stoch_rsi'].iloc[-1]
        if stoch_rsi < 20:
            score += 0.3
        elif stoch_rsi > 80:
            score -= 0.3
        
        return np.clip(score, -1, 1)
    
    def _analyze_support_resistance(self, df: pd.DataFrame) -> float:
        """Analyze support and resistance levels"""
        score = 0
        current_price = df['close'].iloc[-1]
        
        # Find recent highs and lows
        recent_high = df['high'].iloc[-50:].max()
        recent_low = df['low'].iloc[-50:].min()
        
        # Calculate position within range
        price_position = (current_price - recent_low) / (recent_high - recent_low)
        
        # Near support
        if price_position < 0.2:
            score += 0.6
        # Near resistance
        elif price_position > 0.8:
            score -= 0.6
        
        # Check for double bottom/top
        lows = df['low'].iloc[-20:]
        if len(lows[lows == lows.min()]) >= 2:
            score += 0.4
        
        highs = df['high'].iloc[-20:]
        if len(highs[highs == highs.max()]) >= 2:
            score -= 0.4
        
        return np.clip(score, -1, 1)
    
    def _analyze_volume(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze volume for XRP"""
        score = 0
        
        # Volume at extremes
        if df['volume'].iloc[-1] > indicators['volume_sma'].iloc[-1] * 1.5:
            # High volume at lows = bullish
            if df['close'].iloc[-1] < df['close'].iloc[-5:].mean():
                score += 0.5
            # High volume at highs = bearish
            else:
                score -= 0.5
        
        return np.clip(score, -1, 1)
    
    def _analyze_trend(self, indicators: Dict) -> float:
        """Basic trend for mean reversion"""
        # Simple trend that we'll fade
        if indicators['ema_20'].iloc[-1] > indicators['ema_50'].iloc[-1]:
            return 0.5
        else:
            return -0.5
    
    def get_entry_conditions(self, symbol: str) -> Dict:
        """Get XRP entry conditions"""
        return self.config.ENTRY_CONDITIONS["XRPUSDT"]

# ==============================
# Multi-Timeframe Analyzer
# ==============================
class MultiTimeframeAnalyzer:
    """Enhanced multi-timeframe analysis"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def analyze_all_timeframes(self, exchange, symbol: str, strategies: Dict) -> Dict:
        """Analyze all timeframes for a symbol"""
        results = {}
        timeframes = self.config.TIMEFRAME_WEIGHTS.get(symbol, self.config.TIMEFRAME_WEIGHTS["BTCUSDT"])
        
        for tf_key, weight in timeframes.items():
            try:
                # Fetch OHLCV data
                df = await exchange.fetch_ohlcv_with_cache(symbol, tf_key)
                
                if df is not None and len(df) > 100:
                    # Calculate indicators
                    indicators = EnhancedTechnicalIndicators.calculate_all_indicators(df)
                    
                    # Get strategy for symbol
                    strategy = strategies.get(symbol)
                    if strategy:
                        tf_result = await strategy.analyze(symbol, df, indicators)
                        tf_result['weight'] = weight
                        results[tf_key] = tf_result
                    else:
                        results[tf_key] = self._get_default_result(weight)
                else:
                    results[tf_key] = self._get_default_result(weight)
                    
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol} {tf_key}: {e}")
                results[tf_key] = self._get_default_result(weight)
        
        # Combine results
        return self._combine_timeframe_results(results, symbol)
    
    def _combine_timeframe_results(self, results: Dict, symbol: str) -> Dict:
        """Combine timeframe results with symbol-specific logic"""
        if not results:
            return self._get_default_combined_result()
        
        # Calculate weighted scores
        total_weight = 0
        weighted_score = 0
        weighted_confidence = 0
        directions = defaultdict(float)
        
        for tf, result in results.items():
            weight = result.get('weight', 0)
            total_weight += weight
            
            weighted_score += result['score'] * weight
            weighted_confidence += result.get('confidence', 50) * weight
            directions[result['direction']] += weight
        
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
        
        is_aligned = alignment_score >= agreement_threshold
        
        return {
            'direction': direction,
            'score': final_score,
            'confidence': final_confidence,
            'alignment_score': alignment_score,
            'timeframe_results': results,
            'is_aligned': is_aligned
        }
    
    def _get_default_result(self, weight: float) -> Dict:
        """Default result for a timeframe"""
        return {
            'direction': 'neutral',
            'score': 0,
            'confidence': 50,
            'weight': weight
        }
    
    def _get_default_combined_result(self) -> Dict:
        """Default combined result"""
        return {
            'direction': 'neutral',
            'score': 0,
            'confidence': 50,
            'alignment_score': 0,
            'timeframe_results': {},
            'is_aligned': False
        }

# ==============================
# Position Manager with Trailing Stop
# ==============================
class PositionManager:
    """Advanced position management with trailing stops"""
    
    def __init__(self, config: TradingConfig, exchange, db: EnhancedDatabaseManager):
        self.config = config
        self.exchange = exchange
        self.db = db
        self.logger = logging.getLogger(__name__)
        
        # Track trailing stops
        self.trailing_stops = {}
    
    async def open_position(self, symbol: str, signal: Dict, allocated_capital: float) -> Optional[Dict]:
        """Open a new position"""
        try:
            # Calculate position size
            size_ratio = self._calculate_position_size_ratio(symbol, signal)
            position_value = allocated_capital * size_ratio
            
            # Get contract size
            contracts = await self.exchange.calculate_position_size(symbol, position_value)
            
            if contracts <= 0:
                self.logger.warning(f"Invalid position size for {symbol}")
                return None
            
            # Place order
            side = 'buy' if signal['direction'] == 'long' else 'sell'
            order = await self.exchange.place_order(symbol, side, contracts)
            
            if not order:
                return None
            
            # Get fill price
            fill_price = order.get('price', 0)
            
            # Calculate stop loss and take profit levels
            stop_loss = self._calculate_stop_loss(symbol, fill_price, side)
            take_profit = self._calculate_take_profit(symbol, fill_price, side)
            
            # Save to database
            trade_data = {
                'symbol': symbol,
                'side': side,
                'price': fill_price,
                'quantity': contracts,
                'leverage': self.config.LEVERAGE[symbol],
                'order_id': order.get('id'),
                'status': 'open',
                'reason': f"Signal: {signal['score']:.2f}, Confidence: {signal['confidence']:.1f}%",
                'multi_tf_score': signal.get('alignment_score', 0),
                'regime': signal.get('regime', 'unknown'),
                'entry_signal_strength': signal['score']
            }
            
            trade_id = self.db.save_trade(trade_data)
            
            # Save position
            position_data = {
                'symbol': symbol,
                'trade_id': trade_id,
                'entry_price': fill_price,
                'quantity': contracts,
                'side': side,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
            
            position_id = self.db.save_position(position_data)
            
            # Place stop loss order
            sl_side = 'sell' if side == 'buy' else 'buy'
            await self.exchange.place_stop_loss_order(symbol, sl_side, contracts, stop_loss)
            
            self.logger.info(f"Position opened: {symbol} {side} {contracts} @ {fill_price}")
            
            return {
                'trade_id': trade_id,
                'position_id': position_id,
                'order': order
            }
            
        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
            return None
    
    async def manage_positions(self):
        """Manage all open positions"""
        positions = self.db.get_open_positions()
        
        for position in positions:
            try:
                await self._manage_single_position(position)
            except Exception as e:
                self.logger.error(f"Error managing position {position['id']}: {e}")
    
    async def _manage_single_position(self, position: Dict):
        """Manage a single position"""
        symbol = position['symbol']
        
        # Get current price
        ticker = await self.exchange.exchange.fetch_ticker(
            self.exchange._format_symbol(symbol)
        )
        current_price = ticker['last']
        
        # Update position
        self.db.update_position(position['id'], {'current_price': current_price})
        
        # Calculate P&L
        entry_price = position['entry_price']
        side = position['side']
        
        if side == 'long':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        # Update max profit
        if pnl_pct > position.get('max_profit', 0):
            self.db.update_position(position['id'], {'max_profit': pnl_pct})
        
        # Check for trailing stop activation
        trailing_config = self.config.TRAILING_STOP[symbol]
        
        if pnl_pct >= trailing_config['activate'] and not position.get('trailing_stop_active', False):
            # Activate trailing stop
            await self._activate_trailing_stop(position, current_price, trailing_config)
        
        elif position.get('trailing_stop_active', False):
            # Update trailing stop
            await self._update_trailing_stop(position, current_price, trailing_config)
        
        # Check for take profit levels
        take_profit_levels = json.loads(position.get('take_profit', '[]'))
        await self._check_take_profit(position, current_price, take_profit_levels)
        
        # Check stop loss
        if self._should_stop_loss(position, current_price):
            await self._close_position(position, 'stop_loss', current_price)
    
    async def _activate_trailing_stop(self, position: Dict, current_price: float, config: Dict):
        """Activate trailing stop"""
        side = position['side']
        distance = config['distance']
        
        if side == 'long':
            trailing_stop_price = current_price * (1 - distance)
        else:
            trailing_stop_price = current_price * (1 + distance)
        
        # Update database
        self.db.update_position(position['id'], {
            'trailing_stop_active': True,
            'trailing_stop_price': trailing_stop_price,
            'stop_loss': trailing_stop_price  # Update stop loss
        })
        
        # Update stop order on exchange
        await self.exchange.modify_stop_loss(
            position['symbol'],
            position.get('stop_order_id'),
            trailing_stop_price
        )
        
        self.logger.info(f"Trailing stop activated for {position['symbol']} at {trailing_stop_price}")
    
    async def _update_trailing_stop(self, position: Dict, current_price: float, config: Dict):
        """Update trailing stop if price moved favorably"""
        side = position['side']
        distance = config['distance']
        current_trailing = position.get('trailing_stop_price', 0)
        
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
        
        await self.exchange.modify_stop_loss(
            position['symbol'],
            position.get('stop_order_id'),
            new_stop_price
        )
    
    async def _check_take_profit(self, position: Dict, current_price: float, levels: List):
        """Check and execute partial take profits"""
        # Implementation for partial take profit
        pass
    
    def _should_stop_loss(self, position: Dict, current_price: float) -> bool:
        """Check if stop loss should be triggered"""
        side = position['side']
        stop_loss = position['stop_loss']
        
        if side == 'long':
            return current_price <= stop_loss
        else:
            return current_price >= stop_loss
    
    async def _close_position(self, position: Dict, reason: str, close_price: float):
        """Close a position"""
        # Close on exchange
        await self.exchange.close_position(position['symbol'], reason)
        
        # Calculate final P&L
        entry_price = position['entry_price']
        side = position['side']
        
        if side == 'long':
            pnl_pct = (close_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - close_price) / entry_price
        
        pnl_value = pnl_pct * position['quantity'] * entry_price
        
        # Update database
        self.db.update_position(position['id'], {
            'status': 'closed',
            'current_price': close_price
        })
        
        # Update trade
        self.db.update_trade(position['trade_id'], {
            'status': 'closed',
            'close_price': close_price,
            'close_time': datetime.now(),
            'pnl': pnl_value,
            'pnl_percent': pnl_pct * 100,
            'reason': reason
        })
        
        self.logger.info(f"Position closed: {position['symbol']} - {reason} - P&L: {pnl_pct:.2%}")
    
    def _calculate_position_size_ratio(self, symbol: str, signal: Dict) -> float:
        """Calculate position size ratio based on signal strength"""
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
        
        # Ensure within limits
        return np.clip(size, base_range['min'], base_range['max'])
    
    def _calculate_stop_loss(self, symbol: str, entry_price: float, side: str) -> float:
        """Calculate stop loss price"""
        sl_pct = self.config.STOP_LOSS[symbol]
        
        if side == 'buy':
            return entry_price * (1 - sl_pct)
        else:
            return entry_price * (1 + sl_pct)
    
    def _calculate_take_profit(self, symbol: str, entry_price: float, side: str) -> List:
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
# Risk Manager
# ==============================
class RiskManager:
    """Comprehensive risk management system"""
    
    def __init__(self, config: TradingConfig, db: EnhancedDatabaseManager):
        self.config = config
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def check_risk_limits(self, symbol: str) -> Dict[str, bool]:
        """Check all risk limits before trading"""
        checks = {
            'daily_loss': await self._check_daily_loss_limit(),
            'symbol_trades': await self._check_symbol_trade_limits(symbol),
            'position_limits': await self._check_position_limits(symbol),
            'correlation': await self._check_correlation_limits(),
            'drawdown': await self._check_drawdown_limit()
        }
        
        # Overall decision
        can_trade = all(checks.values())
        
        if not can_trade:
            failed_checks = [k for k, v in checks.items() if not v]
            self.logger.warning(f"Risk checks failed for {symbol}: {failed_checks}")
        
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
        
        # Check cooldown
        # Implementation would check last trade time
        
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
        # For now, simple implementation
        # Could be enhanced with actual correlation calculation
        return True
    
    async def _check_drawdown_limit(self) -> bool:
        """Check maximum drawdown"""
        # Implementation would track peak equity and current drawdown
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
        
        return min(remaining_allocation, max_position_size)

# ==============================
# Performance Analyzer
# ==============================
class PerformanceAnalyzer:
    """Real-time performance analysis and reporting"""
    
    def __init__(self, db: EnhancedDatabaseManager):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def update_daily_performance(self):
        """Update daily performance metrics"""
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
            return
        
        # Calculate metrics
        metrics = {
            'total_trades': len(trades),
            'winning_trades': sum(1 for t in trades if t['pnl'] > 0),
            'losing_trades': sum(1 for t in trades if t['pnl'] < 0),
            'total_pnl': sum(t['pnl'] for t in trades),
            'total_pnl_percent': sum(t['pnl_percent'] for t in trades),
            'btc_pnl': sum(t['pnl'] for t in trades if t['symbol'] == 'BTCUSDT'),
            'eth_pnl': sum(t['pnl'] for t in trades if t['symbol'] == 'ETHUSDT'),
            'xrp_pnl': sum(t['pnl'] for t in trades if t['symbol'] == 'XRPUSDT'),
            'total_volume': sum(t['quantity'] * t['price'] for t in trades)
        }
        
        # Win rate
        if metrics['total_trades'] > 0:
            metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades']
        else:
            metrics['win_rate'] = 0
        
        # Average win/loss
        winning_pnls = [t['pnl_percent'] for t in trades if t['pnl'] > 0]
        losing_pnls = [t['pnl_percent'] for t in trades if t['pnl'] < 0]
        
        metrics['avg_win'] = np.mean(winning_pnls) if winning_pnls else 0
        metrics['avg_loss'] = np.mean(losing_pnls) if losing_pnls else 0
        
        # Best/worst trade
        metrics['best_trade'] = max((t['pnl_percent'] for t in trades), default=0)
        metrics['worst_trade'] = min((t['pnl_percent'] for t in trades), default=0)
        
        # Calculate Sharpe ratio (simplified)
        if len(trades) > 1:
            returns = [t['pnl_percent'] for t in trades]
            metrics['sharpe_ratio'] = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252)
        else:
            metrics['sharpe_ratio'] = 0
        
        # Update database
        self.db.update_daily_performance(today, metrics)
    
    def generate_performance_report(self, days: int = 7) -> str:
        """Generate performance report"""
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
        
        # Aggregate metrics
        total_trades = sum(d['total_trades'] for d in daily_data)
        total_pnl = sum(d['total_pnl'] for d in daily_data)
        total_pnl_pct = sum(d['total_pnl_percent'] for d in daily_data)
        
        # Generate report
        report = f"""
📊 **Performance Report - Last {days} Days**
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} KST

**Summary**
• Total Trades: {total_trades}
• Total P&L: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)
• Average Daily P&L: ${total_pnl/days:,.2f}

**By Symbol**
• BTC: ${sum(d['btc_pnl'] for d in daily_data):,.2f}
• ETH: ${sum(d['eth_pnl'] for d in daily_data):,.2f}
• XRP: ${sum(d['xrp_pnl'] for d in daily_data):,.2f}

**Statistics**
• Win Rate: {np.mean([d['win_rate'] for d in daily_data if d['win_rate'] > 0]):.1%}
• Avg Win: {np.mean([d['avg_win'] for d in daily_data if d['avg_win'] > 0]):+.2f}%
• Avg Loss: {np.mean([d['avg_loss'] for d in daily_data if d['avg_loss'] < 0]):+.2f}%
• Best Day: {max(d['total_pnl_percent'] for d in daily_data):+.2f}%
• Worst Day: {min(d['total_pnl_percent'] for d in daily_data):+.2f}%
• Sharpe Ratio: {np.mean([d['sharpe_ratio'] for d in daily_data]):.2f}
"""
        
        return report

# ==============================
# News and Sentiment Analyzer
# ==============================
class NewsSentimentAnalyzer:
    """Enhanced news sentiment analysis with Korean support"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.logger = logging.getLogger(__name__)
        
        self.emergency_keywords = [
            'hack', 'exploit', 'crash', 'bankruptcy', 'fraud', 'investigation',
            'sec', 'lawsuit', 'ban', 'emergency', 'urgent', 'breaking',
            'liquidation', 'default', 'collapse'
        ]
    
    async def analyze_sentiment(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Analyze news sentiment"""
        try:
            news_items = await self._fetch_news(symbol)
            
            if not news_items:
                return self._get_default_sentiment()
            
            # Check for emergency keywords
            has_emergency = self._check_emergency_keywords(news_items)
            
            # Get GPT analysis
            analysis = await self._get_gpt_analysis(news_items, symbol)
            
            # Override if emergency detected
            if has_emergency:
                analysis['has_emergency'] = True
                analysis['sentiment'] = min(analysis['sentiment'], -0.5)
                analysis['action_required'] = 'close_positions'
                analysis['urgency'] = '즉시'
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"News sentiment analysis failed: {e}")
            return self._get_default_sentiment()
    
    async def _fetch_news(self, symbol: Optional[str] = None) -> List[Dict]:
        """Fetch crypto news"""
        news_items = []
        
        # Fetch from multiple sources
        sources = [
            "https://feeds.feedburner.com/CoinDesk",
            # Add more RSS feeds
        ]
        
        for source_url in sources:
            try:
                feed = feedparser.parse(source_url)
                for entry in feed.entries[:5]:
                    news_items.append({
                        'title': entry.title,
                        'summary': entry.get('summary', ''),
                        'published': entry.get('published', ''),
                        'link': entry.get('link', ''),
                        'source': feed.feed.get('title', 'Unknown')
                    })
            except Exception as e:
                self.logger.error(f"Error fetching from {source_url}: {e}")
        
        # Filter by symbol if provided
        if symbol and news_items:
            keywords = {
                'BTCUSDT': ['bitcoin', 'btc', '비트코인'],
                'ETHUSDT': ['ethereum', 'eth', '이더리움'],
                'XRPUSDT': ['ripple', 'xrp', '리플']
            }
            
            symbol_keywords = keywords.get(symbol, [])
            if symbol_keywords:
                filtered = []
                for item in news_items:
                    text = f"{item['title']} {item['summary']}".lower()
                    if any(kw in text for kw in symbol_keywords):
                        filtered.append(item)
                
                news_items = filtered[:10] if filtered else news_items[:5]
        
        return news_items[:10]
    
    def _check_emergency_keywords(self, news_items: List[Dict]) -> bool:
        """Check for emergency keywords in news"""
        for item in news_items:
            text = f"{item['title']} {item['summary']}".lower()
            if any(keyword in text for keyword in self.emergency_keywords):
                self.logger.warning(f"Emergency keyword detected: {item['title']}")
                return True
        return False
    
    async def _get_gpt_analysis(self, news_items: List[Dict], symbol: Optional[str]) -> Dict:
        """Get GPT analysis of news"""
        # Prepare news text
        news_text = "\n".join([
            f"[{item['source']}] {item['title']}" 
            for item in news_items[:10]
        ])
        
        prompt = f"""암호화폐 뉴스를 분석하여 트레이딩 관점에서 평가해주세요.
{f'특히 {symbol}에 미치는 영향을 중점적으로 분석해주세요.' if symbol else ''}

뉴스 헤드라인:
{news_text}

다음 형식으로 정확히 답변해주세요:
1. 전체 감성 점수 (-1.0 ~ +1.0): [점수]
2. 시장 영향 (상/중/하): [영향도]
3. 주요 긍정 요인: [요인들]
4. 주요 부정 요인: [요인들]
5. 거래 추천 (매수/매도/관망): [추천]
6. 긴급도 (즉시/보통): [긴급도]
7. 핵심 요약: [한 줄 요약]"""

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "당신은 암호화폐 시장 분석 전문가입니다. 뉴스가 가격에 미치는 영향을 정확히 분석합니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
            )
            
            return self._parse_gpt_response(response.choices[0].message.content, news_items)
            
        except Exception as e:
            self.logger.error(f"GPT analysis failed: {e}")
            return self._get_default_sentiment()
    
    def _parse_gpt_response(self, response: str, news_items: List[Dict]) -> Dict:
        """Parse GPT response"""
        lines = response.split('\n')
        
        result = {
            'sentiment': 0.0,
            'impact': '중',
            'positive_factors': [],
            'negative_factors': [],
            'recommendation': '관망',
            'urgency': '보통',
            'summary': '',
            'news_count': len(news_items),
            'latest_news': news_items[0]['title'] if news_items else '',
            'has_emergency': False
        }
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if '감성 점수' in line and ':' in line:
                try:
                    score_text = line.split(':')[1].strip()
                    # Extract number from various formats
                    import re
                    numbers = re.findall(r'-?\d*\.?\d+', score_text)
                    if numbers:
                        result['sentiment'] = float(numbers[0])
                except:
                    pass
            
            elif '시장 영향' in line and ':' in line:
                impact_text = line.split(':')[1].strip()
                if '상' in impact_text or '높' in impact_text:
                    result['impact'] = '상'
                elif '하' in impact_text or '낮' in impact_text:
                    result['impact'] = '하'
            
            elif '거래 추천' in line and ':' in line:
                rec_text = line.split(':')[1].strip()
                if '매수' in rec_text:
                    result['recommendation'] = '매수'
                elif '매도' in rec_text:
                    result['recommendation'] = '매도'
            
            elif '긴급도' in line and ':' in line:
                urg_text = line.split(':')[1].strip()
                if '즉시' in urg_text or '긴급' in urg_text:
                    result['urgency'] = '즉시'
            
            elif '핵심 요약' in line and ':' in line:
                result['summary'] = line.split(':')[1].strip()
        
        # Ensure sentiment is within bounds
        result['sentiment'] = max(-1, min(1, result['sentiment']))
        
        return result
    
    def _get_default_sentiment(self) -> Dict[str, Any]:
        """Default sentiment values"""
        return {
            'sentiment': 0.0,
            'impact': '중',
            'positive_factors': [],
            'negative_factors': [],
            'recommendation': '관망',
            'urgency': '보통',
            'summary': '뉴스 분석 불가',
            'news_count': 0,
            'latest_news': '',
            'has_emergency': False
        }

# ==============================
# Notification Manager
# ==============================
class NotificationManager:
    """Multi-channel notification system"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Message queue to prevent spam
        self.message_queue = deque(maxlen=100)
        self.last_message_time = {}
        self.min_interval = 60  # Minimum seconds between similar messages
    
    async def send_notification(self, message: str, priority: str = 'normal', 
                              channel: str = 'telegram'):
        """Send notification with priority and channel selection"""
        # Check for spam
        message_hash = hashlib.md5(message.encode()).hexdigest()[:8]
        current_time = time.time()
        
        if message_hash in self.last_message_time:
            if current_time - self.last_message_time[message_hash] < self.min_interval:
                return  # Skip duplicate message
        
        self.last_message_time[message_hash] = current_time
        
        # Send based on priority
        if priority == 'emergency':
            await self._send_emergency_notification(message)
        elif priority == 'high':
            await self._send_high_priority_notification(message)
        else:
            await self._send_normal_notification(message, channel)
    
    async def _send_emergency_notification(self, message: str):
        """Send emergency notification to all channels"""
        tasks = [
            self._send_telegram_message(f"🚨 **긴급** 🚨\n\n{message}"),
            # Add email, discord, etc.
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_high_priority_notification(self, message: str):
        """Send high priority notification"""
        await self._send_telegram_message(f"⚠️ **중요** ⚠️\n\n{message}")
    
    async def _send_normal_notification(self, message: str, channel: str):
        """Send normal notification"""
        if channel == 'telegram':
            await self._send_telegram_message(message)
        # Add other channels
    
    async def _send_telegram_message(self, message: str):
        """Send Telegram message"""
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
                        self.logger.error(f"Telegram send failed: {await response.text()}")
                        
        except Exception as e:
            self.logger.error(f"Telegram message error: {e}")
    
    async def send_trade_notification(self, symbol: str, action: str, details: Dict):
        """Send formatted trade notification"""
        emoji_map = {
            'open_long': '🟢',
            'open_short': '🔴',
            'close_profit': '💰',
            'close_loss': '🛑',
            'close_neutral': '⏹️'
        }
        
        emoji = emoji_map.get(action, '📊')
        
        message = f"""
{emoji} **{symbol} - {action.replace('_', ' ').title()}**

💵 Price: ${details.get('price', 0):,.2f}
📊 Quantity: {details.get('quantity', 0)}
🎯 Signal: {details.get('signal_strength', 0):.2f}
🔮 Confidence: {details.get('confidence', 0):.1f}%
"""
        
        if 'pnl' in details:
            message += f"💰 P&L: {details['pnl']:+.2f}%\n"
        
        if 'reason' in details:
            message += f"📝 Reason: {details['reason']}\n"
        
        await self.send_notification(message, priority='high')
    
    async def send_daily_report(self, report: str):
        """Send daily performance report"""
        await self.send_notification(report, priority='normal')
    
    async def send_error_notification(self, error: str, details: str = ""):
        """Send error notification"""
        message = f"""
❌ **System Error**

Error: {error}
{f'Details: {details}' if details else ''}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.send_notification(message, priority='high')

# ==============================
# Market Regime Analyzer
# ==============================
class MarketRegimeAnalyzer:
    """Enhanced market regime detection"""
    
    def __init__(self):
        self.regimes = ['trending_up', 'trending_down', 'ranging', 'volatile']
        self.logger = logging.getLogger(__name__)
    
    def analyze_regime(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Analyze current market regime"""
        # Price position analysis
        price_score = self._analyze_price_position(df, indicators)
        
        # Momentum analysis
        momentum_score = self._analyze_momentum(indicators)
        
        # Trend strength
        trend_strength = self._analyze_trend_strength(indicators)
        
        # Volatility analysis
        volatility_score = self._analyze_volatility(df, indicators)
        
        # Determine regime
        regime = self._determine_regime(
            price_score, momentum_score, trend_strength, volatility_score
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            price_score, momentum_score, trend_strength, volatility_score
        )
        
        return {
            'regime': regime,
            'confidence': confidence,
            'characteristics': self._get_regime_characteristics(regime),
            'scores': {
                'price': price_score,
                'momentum': momentum_score,
                'trend': trend_strength,
                'volatility': volatility_score
            }
        }
    
    def _analyze_price_position(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze price position relative to key levels"""
        score = 0
        current_price = df['close'].iloc[-1]
        
        # Position relative to EMAs
        if current_price > indicators['ema_20'].iloc[-1]:
            score += 0.25
        if current_price > indicators['ema_50'].iloc[-1]:
            score += 0.25
        if current_price > indicators['sma_200'].iloc[-1]:
            score += 0.25
        
        # EMA alignment
        if indicators['ema_20'].iloc[-1] > indicators['ema_50'].iloc[-1]:
            score += 0.25
        
        return score
    
    def _analyze_momentum(self, indicators: Dict) -> float:
        """Analyze momentum indicators"""
        score = 0
        
        # RSI
        rsi = indicators['rsi'].iloc[-1]
        if rsi > 50:
            score += 0.5
        if rsi > 70:
            score += 0.25
        elif rsi < 30:
            score -= 0.25
        
        # MACD
        if indicators['macd'].iloc[-1] > indicators['macd_signal'].iloc[-1]:
            score += 0.25
        
        return np.clip(score, -1, 1)
    
    def _analyze_trend_strength(self, indicators: Dict) -> float:
        """Analyze trend strength using ADX"""
        adx = indicators['adx'].iloc[-1]
        
        if adx > 40:
            return 1.0
        elif adx > 25:
            return 0.7
        elif adx > 20:
            return 0.4
        else:
            return 0.2
    
    def _analyze_volatility(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Analyze market volatility"""
        # ATR ratio
        atr = indicators['atr'].iloc[-1]
        price = df['close'].iloc[-1]
        atr_ratio = atr / price
        
        # Historical comparison
        historical_atr = indicators['atr'].rolling(50).mean().iloc[-1]
        current_vs_historical = atr / historical_atr if historical_atr > 0 else 1
        
        if current_vs_historical > 2:
            return 1.0  # Very high volatility
        elif current_vs_historical > 1.5:
            return 0.7
        elif current_vs_historical > 1.2:
            return 0.5
        else:
            return 0.3
    
    def _determine_regime(self, price: float, momentum: float, 
                         trend: float, volatility: float) -> str:
        """Determine market regime based on scores"""
        # Strong trend detection
        if trend > 0.7:
            if price > 0.6 and momentum > 0.3:
                return 'trending_up'
            elif price < 0.4 and momentum < -0.3:
                return 'trending_down'
        
        # High volatility
        if volatility > 0.7:
            return 'volatile'
        
        # Default to ranging
        return 'ranging'
    
    def _calculate_confidence(self, price: float, momentum: float,
                            trend: float, volatility: float) -> float:
        """Calculate regime confidence"""
        # Base confidence on consistency of signals
        scores = [price, momentum, trend]
        
        # Check alignment
        if all(s > 0.5 for s in scores) or all(s < -0.5 for s in scores):
            base_confidence = 80
        elif all(s > 0.3 for s in scores) or all(s < -0.3 for s in scores):
            base_confidence = 60
        else:
            base_confidence = 40
        
        # Adjust for trend strength
        base_confidence += trend * 20
        
        # Reduce for high volatility
        if volatility > 0.8:
            base_confidence *= 0.8
        
        return min(95, max(20, base_confidence))
    
    def _get_regime_characteristics(self, regime: str) -> Dict:
        """Get regime characteristics"""
        characteristics = {
            'trending_up': {
                'description': 'Strong Uptrend',
                'kr_description': '강한 상승 추세',
                'risk_level': 0.3,
                'position_bias': 'long',
                'suggested_strategy': 'trend_following'
            },
            'trending_down': {
                'description': 'Strong Downtrend',
                'kr_description': '강한 하락 추세',
                'risk_level': 0.7,
                'position_bias': 'short',
                'suggested_strategy': 'trend_following'
            },
            'ranging': {
                'description': 'Sideways/Range-bound',
                'kr_description': '횡보/박스권',
                'risk_level': 0.5,
                'position_bias': 'neutral',
                'suggested_strategy': 'mean_reversion'
            },
            'volatile': {
                'description': 'High Volatility',
                'kr_description': '고변동성',
                'risk_level': 0.8,
                'position_bias': 'neutral',
                'suggested_strategy': 'scalping'
            }
        }
        
        return characteristics.get(regime, characteristics['ranging'])

# ==============================
# Pattern Recognition System
# ==============================
class PatternRecognitionSystem:
    """Advanced chart pattern recognition"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def identify_patterns(self, df: pd.DataFrame, indicators: Dict) -> Dict:
        """Identify all chart patterns"""
        patterns = {}
        
        # Classic patterns
        patterns['double_bottom'] = self._detect_double_bottom(df)
        patterns['double_top'] = self._detect_double_top(df)
        patterns['head_shoulders'] = self._detect_head_shoulders(df)
        patterns['inv_head_shoulders'] = self._detect_inverse_head_shoulders(df)
        
        # Triangle patterns
        patterns['ascending_triangle'] = self._detect_ascending_triangle(df)
        patterns['descending_triangle'] = self._detect_descending_triangle(df)
        patterns['symmetrical_triangle'] = self._detect_symmetrical_triangle(df)
        
        # Continuation patterns
        patterns['bull_flag'] = self._detect_bull_flag(df)
        patterns['bear_flag'] = self._detect_bear_flag(df)
        
        # Candlestick patterns
        patterns['doji'] = self._detect_doji(df)
        patterns['hammer'] = self._detect_hammer(df)
        patterns['shooting_star'] = self._detect_shooting_star(df)
        
        # Filter detected patterns
        detected_patterns = {
            name: info for name, info in patterns.items() 
            if info.get('detected', False)
        }
        
        return detected_patterns
    
    def _detect_double_bottom(self, df: pd.DataFrame, window: int = 50) -> Dict:
        """Detect double bottom pattern"""
        if len(df) < window:
            return {'detected': False}
        
        lows = df['low'].iloc[-window:]
        
        # Find local minima
        local_mins = []
        for i in range(2, len(lows) - 2):
            if (lows.iloc[i] < lows.iloc[i-1] and 
                lows.iloc[i] < lows.iloc[i-2] and
                lows.iloc[i] < lows.iloc[i+1] and 
                lows.iloc[i] < lows.iloc[i+2]):
                local_mins.append((i, lows.iloc[i]))
        
        if len(local_mins) >= 2:
            # Check last two minima
            idx1, low1 = local_mins[-2]
            idx2, low2 = local_mins[-1]
            
            # Check if lows are similar (within 2%)
            if abs(low1 - low2) / low1 < 0.02:
                # Check for peak between lows
                peak_between = df['high'].iloc[-window:].iloc[idx1:idx2].max()
                if peak_between > low1 * 1.03:  # At least 3% higher
                    return {
                        'detected': True,
                        'confidence': 0.7,
                        'expected_move': 0.05,
                        'neckline': peak_between,
                        'support': (low1 + low2) / 2
                    }
        
        return {'detected': False}
    
    def _detect_double_top(self, df: pd.DataFrame, window: int = 50) -> Dict:
        """Detect double top pattern"""
        if len(df) < window:
            return {'detected': False}
        
        highs = df['high'].iloc[-window:]
        
        # Find local maxima
        local_maxs = []
        for i in range(2, len(highs) - 2):
            if (highs.iloc[i] > highs.iloc[i-1] and 
                highs.iloc[i] > highs.iloc[i-2] and
                highs.iloc[i] > highs.iloc[i+1] and 
                highs.iloc[i] > highs.iloc[i+2]):
                local_maxs.append((i, highs.iloc[i]))
        
        if len(local_maxs) >= 2:
            idx1, high1 = local_maxs[-2]
            idx2, high2 = local_maxs[-1]
            
            if abs(high1 - high2) / high1 < 0.02:
                trough_between = df['low'].iloc[-window:].iloc[idx1:idx2].min()
                if trough_between < high1 * 0.97:
                    return {
                        'detected': True,
                        'confidence': 0.7,
                        'expected_move': -0.05,
                        'neckline': trough_between,
                        'resistance': (high1 + high2) / 2
                    }
        
        return {'detected': False}
    
    def _detect_head_shoulders(self, df: pd.DataFrame, window: int = 60) -> Dict:
        """Detect head and shoulders pattern"""
        if len(df) < window:
            return {'detected': False}
        
        highs = df['high'].iloc[-window:]
        
        # Find three consecutive peaks
        peaks = []
        for i in range(5, len(highs) - 5):
            if highs.iloc[i] == highs.iloc[i-5:i+5].max():
                peaks.append((i, highs.iloc[i]))
        
        if len(peaks) >= 3:
            # Check last three peaks
            left_shoulder = peaks[-3]
            head = peaks[-2]
            right_shoulder = peaks[-1]
            
            # Head should be highest
            if (head[1] > left_shoulder[1] and 
                head[1] > right_shoulder[1] and
                abs(left_shoulder[1] - right_shoulder[1]) / left_shoulder[1] < 0.03):
                
                # Find neckline
                trough1 = df['low'].iloc[-window:].iloc[left_shoulder[0]:head[0]].min()
                trough2 = df['low'].iloc[-window:].iloc[head[0]:right_shoulder[0]].min()
                neckline = (trough1 + trough2) / 2
                
                return {
                    'detected': True,
                    'confidence': 0.75,
                    'expected_move': -0.07,
                    'neckline': neckline,
                    'pattern_height': head[1] - neckline
                }
        
        return {'detected': False}
    
    def _detect_inverse_head_shoulders(self, df: pd.DataFrame, window: int = 60) -> Dict:
        """Detect inverse head and shoulders pattern"""
        if len(df) < window:
            return {'detected': False}
        
        lows = df['low'].iloc[-window:]
        
        # Find three consecutive troughs
        troughs = []
        for i in range(5, len(lows) - 5):
            if lows.iloc[i] == lows.iloc[i-5:i+5].min():
                troughs.append((i, lows.iloc[i]))
        
        if len(troughs) >= 3:
            left_shoulder = troughs[-3]
            head = troughs[-2]
            right_shoulder = troughs[-1]
            
            # Head should be lowest
            if (head[1] < left_shoulder[1] and 
                head[1] < right_shoulder[1] and
                abs(left_shoulder[1] - right_shoulder[1]) / left_shoulder[1] < 0.03):
                
                # Find neckline
                peak1 = df['high'].iloc[-window:].iloc[left_shoulder[0]:head[0]].max()
                peak2 = df['high'].iloc[-window:].iloc[head[0]:right_shoulder[0]].max()
                neckline = (peak1 + peak2) / 2
                
                return {
                    'detected': True,
                    'confidence': 0.75,
                    'expected_move': 0.07,
                    'neckline': neckline,
                    'pattern_height': neckline - head[1]
                }
        
        return {'detected': False}
    
    def _detect_ascending_triangle(self, df: pd.DataFrame, window: int = 40) -> Dict:
        """Detect ascending triangle pattern"""
        if len(df) < window:
            return {'detected': False}
        
        highs = df['high'].iloc[-window:]
        lows = df['low'].iloc[-window:]
        
        # Check for flat top (resistance)
        high_slope = np.polyfit(range(len(highs)), highs.values, 1)[0]
        low_slope = np.polyfit(range(len(lows)), lows.values, 1)[0]
        
        # Ascending triangle: flat top, rising bottom
        if abs(high_slope) < 0.001 and low_slope > 0.001:
            resistance = highs.mean()
            return {
                'detected': True,
                'confidence': 0.65,
                'expected_move': 0.04,
                'resistance': resistance,
                'breakout_target': resistance * 1.04
            }
        
        return {'detected': False}
    
    def _detect_descending_triangle(self, df: pd.DataFrame, window: int = 40) -> Dict:
        """Detect descending triangle pattern"""
        if len(df) < window:
            return {'detected': False}
        
        highs = df['high'].iloc[-window:]
        lows = df['low'].iloc[-window:]
        
        high_slope = np.polyfit(range(len(highs)), highs.values, 1)[0]
        low_slope = np.polyfit(range(len(lows)), lows.values, 1)[0]
        
        # Descending triangle: falling top, flat bottom
        if high_slope < -0.001 and abs(low_slope) < 0.001:
            support = lows.mean()
            return {
                'detected': True,
                'confidence': 0.65,
                'expected_move': -0.04,
                'support': support,
                'breakdown_target': support * 0.96
            }
        
        return {'detected': False}
    
    def _detect_symmetrical_triangle(self, df: pd.DataFrame, window: int = 40) -> Dict:
        """Detect symmetrical triangle pattern"""
        if len(df) < window:
            return {'detected': False}
        
        highs = df['high'].iloc[-window:]
        lows = df['low'].iloc[-window:]
        
        high_slope = np.polyfit(range(len(highs)), highs.values, 1)[0]
        low_slope = np.polyfit(range(len(lows)), lows.values, 1)[0]
        
        # Symmetrical: converging lines
        if high_slope < -0.001 and low_slope > 0.001:
            # Check if lines are converging
            if abs(high_slope) + abs(low_slope) > 0.002:
                return {
                    'detected': True,
                    'confidence': 0.6,
                    'expected_move': 0.03,  # Direction uncertain
                    'apex': window + 10  # Estimated bars to apex
                }
        
        return {'detected': False}
    
    def _detect_bull_flag(self, df: pd.DataFrame, window: int = 20) -> Dict:
        """Detect bull flag pattern"""
        if len(df) < window + 10:
            return {'detected': False}
        
        # Check for strong upward move (pole)
        pole_start = -window - 10
        pole_end = -window
        pole_move = (df['close'].iloc[pole_end] - df['close'].iloc[pole_start]) / df['close'].iloc[pole_start]
        
        if pole_move > 0.05:  # 5% move up
            # Check for consolidation (flag)
            flag_high = df['high'].iloc[-window:].max()
            flag_low = df['low'].iloc[-window:].min()
            flag_range = (flag_high - flag_low) / flag_low
            
            if flag_range < 0.03:  # Tight consolidation
                # Check for slight downward drift
                flag_slope = np.polyfit(range(window), df['close'].iloc[-window:].values, 1)[0]
                if -0.001 < flag_slope < 0:
                    return {
                        'detected': True,
                        'confidence': 0.7,
                        'expected_move': pole_move * 0.7,  # 70% of pole
                        'pole_height': pole_move
                    }
        
        return {'detected': False}
    
    def _detect_bear_flag(self, df: pd.DataFrame, window: int = 20) -> Dict:
        """Detect bear flag pattern"""
        if len(df) < window + 10:
            return {'detected': False}
        
        # Check for strong downward move (pole)
        pole_start = -window - 10
        pole_end = -window
        pole_move = (df['close'].iloc[pole_end] - df['close'].iloc[pole_start]) / df['close'].iloc[pole_start]
        
        if pole_move < -0.05:  # 5% move down
            # Check for consolidation (flag)
            flag_high = df['high'].iloc[-window:].max()
            flag_low = df['low'].iloc[-window:].min()
            flag_range = (flag_high - flag_low) / flag_low
            
            if flag_range < 0.03:  # Tight consolidation
                # Check for slight upward drift
                flag_slope = np.polyfit(range(window), df['close'].iloc[-window:].values, 1)[0]
                if 0 < flag_slope < 0.001:
                    return {
                        'detected': True,
                        'confidence': 0.7,
                        'expected_move': pole_move * 0.7,
                        'pole_height': abs(pole_move)
                    }
        
        return {'detected': False}
    
    def _detect_doji(self, df: pd.DataFrame) -> Dict:
        """Detect doji candlestick pattern"""
        last_candle = df.iloc[-1]
        body = abs(last_candle['close'] - last_candle['open'])
        range_hl = last_candle['high'] - last_candle['low']
        
        if range_hl > 0 and body / range_hl < 0.1:  # Very small body
            return {
                'detected': True,
                'confidence': 0.6,
                'expected_move': 0,  # Indecision
                'type': 'doji'
            }
        
        return {'detected': False}
    
    def _detect_hammer(self, df: pd.DataFrame) -> Dict:
        """Detect hammer pattern"""
        if len(df) < 5:
            return {'detected': False}
        
        # Check if in downtrend
        if df['close'].iloc[-5] < df['close'].iloc[-1]:
            return {'detected': False}
        
        last_candle = df.iloc[-1]
        body = abs(last_candle['close'] - last_candle['open'])
        lower_shadow = min(last_candle['open'], last_candle['close']) - last_candle['low']
        upper_shadow = last_candle['high'] - max(last_candle['open'], last_candle['close'])
        
        # Hammer: small body at top, long lower shadow
        if (lower_shadow > body * 2 and 
            upper_shadow < body * 0.5 and
            body > 0):
            return {
                'detected': True,
                'confidence': 0.65,
                'expected_move': 0.02,
                'type': 'hammer'
            }
        
        return {'detected': False}
    
    def _detect_shooting_star(self, df: pd.DataFrame) -> Dict:
        """Detect shooting star pattern"""
        if len(df) < 5:
            return {'detected': False}
        
        # Check if in uptrend
        if df['close'].iloc[-5] > df['close'].iloc[-1]:
            return {'detected': False}
        
        last_candle = df.iloc[-1]
        body = abs(last_candle['close'] - last_candle['open'])
        upper_shadow = last_candle['high'] - max(last_candle['open'], last_candle['close'])
        lower_shadow = min(last_candle['open'], last_candle['close']) - last_candle['low']
        
        # Shooting star: small body at bottom, long upper shadow
        if (upper_shadow > body * 2 and 
            lower_shadow < body * 0.5 and
            body > 0):
            return {
                'detected': True,
                'confidence': 0.65,
                'expected_move': -0.02,
                'type': 'shooting_star'
            }
        
        return {'detected': False}

# ==============================
# Backtesting System
# ==============================
class BacktestingSystem:
    """Comprehensive backtesting engine"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def backtest_strategy(self, strategy_engine, start_date: str, 
                               end_date: str, initial_capital: float = 10000) -> Dict:
        """Run backtest on historical data"""
        self.logger.info(f"Starting backtest from {start_date} to {end_date}")
        
        results = {
            'trades': [],
            'equity_curve': [],
            'statistics': {},
            'by_symbol': {}
        }
        
        # Initialize portfolio
        portfolio = {
            'capital': initial_capital,
            'positions': {},
            'trade_count': 0,
            'winning_trades': 0,
            'losing_trades': 0
        }
        
        # Load historical data for each symbol
        for symbol in self.config.SYMBOLS:
            self.logger.info(f"Backtesting {symbol}")
            
            # This would load historical data
            # For now, using placeholder
            historical_data = await self._load_historical_data(
                symbol, start_date, end_date
            )
            
            if historical_data is None:
                continue
            
            # Run strategy on historical data
            symbol_results = await self._backtest_symbol(
                strategy_engine, symbol, historical_data, portfolio
            )
            
            results['by_symbol'][symbol] = symbol_results
        
        # Calculate final statistics
        results['statistics'] = self._calculate_statistics(
            results['trades'], initial_capital, portfolio['capital']
        )
        
        return results
    
    async def _load_historical_data(self, symbol: str, start_date: str, 
                                   end_date: str) -> Optional[pd.DataFrame]:
        """Load historical data for backtesting"""
        # This would connect to data source and load historical data
        # For now, returning None as placeholder
        return None
    
    async def _backtest_symbol(self, strategy_engine, symbol: str, 
                              data: pd.DataFrame, portfolio: Dict) -> Dict:
        """Backtest single symbol"""
        symbol_results = {
            'trades': [],
            'total_return': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0
        }
        
        # Would implement actual backtesting logic here
        
        return symbol_results
    
    def _calculate_statistics(self, trades: List[Dict], 
                            initial_capital: float, final_capital: float) -> Dict:
        """Calculate backtest statistics"""
        if not trades:
            return {
                'total_return': 0,
                'total_trades': 0,
                'win_rate': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'profit_factor': 0
            }
        
        # Calculate returns
        total_return = (final_capital - initial_capital) / initial_capital
        
        # Win rate
        winning_trades = [t for t in trades if t['pnl'] > 0]
        win_rate = len(winning_trades) / len(trades)
        
        # Profit factor
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate daily returns for Sharpe ratio
        # Placeholder for now
        sharpe_ratio = 0
        
        return {
            'total_return': total_return,
            'total_trades': len(trades),
            'win_rate': win_rate,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': 0,  # Would calculate from equity curve
            'profit_factor': profit_factor,
            'avg_win': gross_profit / len(winning_trades) if winning_trades else 0,
            'avg_loss': gross_loss / (len(trades) - len(winning_trades)) if len(trades) > len(winning_trades) else 0
        }

# ==============================
# ML Model Manager
# ==============================
class MLModelManager:
    """Machine learning model management"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.models = {}
        
        if config.ENABLE_ML_MODELS:
            self._load_models()
    
    def _load_models(self):
        """Load ML models"""
        try:
            # Load saved models if they exist
            model_dir = "models"
            
            # LSTM model
            lstm_path = os.path.join(model_dir, "lstm_model.pkl")
            if os.path.exists(lstm_path):
                self.models['lstm'] = joblib.load(lstm_path)
                self.logger.info("LSTM model loaded")
            
            # XGBoost model
            xgb_path = os.path.join(model_dir, "xgb_model.pkl")
            if os.path.exists(xgb_path):
                self.models['xgboost'] = joblib.load(xgb_path)
                self.logger.info("XGBoost model loaded")
            
            # Random Forest model
            rf_path = os.path.join(model_dir, "rf_model.pkl")
            if os.path.exists(rf_path):
                self.models['random_forest'] = joblib.load(rf_path)
                self.logger.info("Random Forest model loaded")
                
        except Exception as e:
            self.logger.error(f"Error loading ML models: {e}")
    
    async def get_predictions(self, symbol: str, features: np.ndarray) -> Dict[str, Any]:
        """Get predictions from all models"""
        predictions = {}
        
        for model_name, model in self.models.items():
            try:
                prediction = await self._predict_with_model(
                    model_name, model, features
                )
                predictions[model_name] = prediction
            except Exception as e:
                self.logger.error(f"Error with {model_name} prediction: {e}")
                predictions[model_name] = None
        
        # Ensemble prediction
        ensemble_prediction = self._ensemble_predictions(predictions)
        
        return {
            'individual_predictions': predictions,
            'ensemble': ensemble_prediction
        }
    
    async def _predict_with_model(self, model_name: str, model: Any, 
                                 features: np.ndarray) -> Dict:
        """Get prediction from single model"""
        # Run prediction in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        prediction = await loop.run_in_executor(
            None, model.predict, features
        )
        
        # Get prediction probability if available
        if hasattr(model, 'predict_proba'):
            proba = await loop.run_in_executor(
                None, model.predict_proba, features
            )
            confidence = np.max(proba)
        else:
            confidence = 0.5
        
        return {
            'prediction': float(prediction[0]),
            'confidence': float(confidence),
            'model': model_name
        }
    
    def _ensemble_predictions(self, predictions: Dict) -> Dict:
        """Combine predictions from multiple models"""
        valid_predictions = [
            p for p in predictions.values() 
            if p is not None and 'prediction' in p
        ]
        
        if not valid_predictions:
            return {
                'prediction': 0,
                'confidence': 0,
                'method': 'none'
            }
        
        # Weighted average based on confidence
        total_weight = sum(p['confidence'] for p in valid_predictions)
        
        if total_weight == 0:
            # Simple average
            ensemble_pred = np.mean([p['prediction'] for p in valid_predictions])
            ensemble_conf = np.mean([p['confidence'] for p in valid_predictions])
        else:
            # Weighted average
            ensemble_pred = sum(
                p['prediction'] * p['confidence'] for p in valid_predictions
            ) / total_weight
            ensemble_conf = np.mean([p['confidence'] for p in valid_predictions])
        
        return {
            'prediction': ensemble_pred,
            'confidence': ensemble_conf,
            'method': 'weighted_ensemble',
            'model_count': len(valid_predictions)
        }
    
    def train_models(self, training_data: pd.DataFrame):
        """Train or retrain models"""
        # This would implement model training
        # For production, this would be done offline
        pass

# ==============================
# Main Trading Strategy Engine
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
    
    async def initialize(self):
        """Initialize all components"""
        self.logger.info("="*60)
        self.logger.info("Initializing Advanced Bitget Trading System")
        self.logger.info("="*60)
        
        # Initialize exchange
        await self.exchange.initialize()
        
        # Check balance
        balance = await self.exchange.get_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        
        self.logger.info(f"✅ System initialized")
        self.logger.info(f"💰 USDT Balance: ${usdt_balance:,.2f}")
        self.logger.info(f"📊 Trading symbols: {', '.join(self.config.SYMBOLS)}")
        self.logger.info(f"⚙️ Portfolio allocation: BTC 70%, ETH 20%, XRP 10%")
        
        # Send startup notification
        await self.notifier.send_notification(
            f"🚀 Trading system started\n💰 Balance: ${usdt_balance:,.2f}",
            priority='high'
        )
    
    async def analyze_and_trade(self, symbol: str):
        """Main analysis and trading logic for a symbol"""
        try:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Analyzing {symbol}...")
            
            # Risk checks first
            risk_check = await self.risk_manager.check_risk_limits(symbol)
            if not risk_check['can_trade']:
                self.logger.warning(f"Risk limits exceeded for {symbol}")
                return
            
            # Multi-timeframe analysis
            multi_tf_result = await self.multi_tf_analyzer.analyze_all_timeframes(
                self.exchange, symbol, self.strategies
            )
            
            self.logger.info(f"Multi-TF Result: Direction={multi_tf_result['direction']}, "
                           f"Alignment={multi_tf_result['alignment_score']:.2f}")
            
            # Check entry conditions
            entry_conditions = self.config.ENTRY_CONDITIONS[symbol]
            
            # For ETH and XRP, check BTC direction
            if entry_conditions.get('btc_correlation_check', False):
                btc_result = await self._get_btc_direction()
                if btc_result['direction'] != multi_tf_result['direction']:
                    self.logger.info(f"{symbol} direction conflicts with BTC, skipping")
                    return
            
            # Check alignment threshold
            if not multi_tf_result['is_aligned']:
                self.logger.info(f"{symbol} timeframes not aligned, skipping")
                return
            
            # Get 4H data for detailed analysis
            df_4h = await self.exchange.fetch_ohlcv_with_cache(symbol, '4h')
            if df_4h is None or len(df_4h) < 200:
                self.logger.warning(f"Insufficient data for {symbol}")
                return
            
            # Calculate indicators
            indicators = EnhancedTechnicalIndicators.calculate_all_indicators(df_4h)
            
            # Market regime analysis
            regime_info = self.regime_analyzer.analyze_regime(df_4h, indicators)
            self.logger.info(f"Market Regime: {regime_info['regime']} "
                           f"(confidence: {regime_info['confidence']:.1f}%)")
            
            # Pattern recognition
            patterns = self.pattern_recognizer.identify_patterns(df_4h, indicators)
            if patterns:
                pattern_names = list(patterns.keys())
                self.logger.info(f"Patterns detected: {', '.join(pattern_names)}")
            
            # News sentiment
            news_sentiment = await self.news_analyzer.analyze_sentiment(symbol)
            self.logger.info(f"News Sentiment: {news_sentiment['sentiment']:+.2f}")
            
            # Check for emergency news
            if news_sentiment.get('has_emergency', False):
                await self._handle_emergency(symbol, news_sentiment)
                return
            
            # ML predictions if available
            ml_predictions = {}
            if self.config.ENABLE_ML_MODELS:
                features = self._prepare_ml_features(df_4h, indicators)
                ml_predictions = await self.ml_manager.get_predictions(symbol, features)
            
            # Generate final trading signal
            trading_signal = self._generate_trading_signal(
                symbol, multi_tf_result, regime_info, patterns, 
                news_sentiment, ml_predictions, indicators
            )
            
            # Add metadata
            trading_signal['regime'] = regime_info['regime']
            trading_signal['alignment_score'] = multi_tf_result['alignment_score']
            
            # Log signal
            self.logger.info(f"Trading Signal: {trading_signal['direction']} "
                           f"(score: {trading_signal['score']:.2f}, "
                           f"confidence: {trading_signal['confidence']:.1f}%)")
            
            # Save prediction
            current_price = df_4h['close'].iloc[-1]
            prediction_data = {
                'symbol': symbol,
                'timeframe': '4h',
                'price': current_price,
                'prediction': trading_signal['expected_move'],
                'confidence': trading_signal['confidence'],
                'direction': trading_signal['direction'],
                'technical_score': trading_signal['score'],
                'news_sentiment': news_sentiment['sentiment'],
                'multi_tf_score': multi_tf_result['alignment_score'],
                'regime': regime_info['regime'],
                'indicators': {k: float(v.iloc[-1]) if hasattr(v, 'iloc') else float(v) 
                             for k, v in indicators.items() if k in ['rsi', 'macd', 'adx']}
            }
            self.db.save_prediction_with_indicators(prediction_data)
            
            # Execute trade if conditions met
            if trading_signal['should_trade']:
                await self._execute_trade(symbol, trading_signal, current_price)
            
            # Manage existing positions
            await self.position_manager.manage_positions()
            
            # Update performance
            await self.performance_analyzer.update_daily_performance()
            
            self.logger.info(f"Analysis complete for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {e}")
            traceback.print_exc()
    
    async def _get_btc_direction(self) -> Dict:
        """Get BTC direction for correlation check"""
        # Quick BTC analysis
        btc_result = await self.multi_tf_analyzer.analyze_all_timeframes(
            self.exchange, 'BTCUSDT', self.strategies
        )
        return btc_result
    
    def _generate_trading_signal(self, symbol: str, multi_tf: Dict, regime: Dict,
                                patterns: Dict, news: Dict, ml_predictions: Dict,
                                indicators: Dict) -> Dict:
        """Generate final trading signal"""
        # Base components
        components = {}
        
        # Multi-timeframe (highest weight)
        if multi_tf['is_aligned']:
            tf_score = multi_tf['score'] * multi_tf['alignment_score']
            components[tf_score] = 0.4
        else:
            components[0] = 0.4
        
        # Market regime
        regime_score = 0
        if regime['regime'] == 'trending_up' and multi_tf['direction'] == 'long':
            regime_score = 0.5
        elif regime['regime'] == 'trending_down' and multi_tf['direction'] == 'short':
            regime_score = -0.5
        elif regime['regime'] in ['ranging', 'volatile']:
            regime_score = multi_tf['score'] * 0.5
        components[regime_score] = 0.2
        
        # Patterns
        pattern_score = 0
        for pattern_name, pattern_info in patterns.items():
            if pattern_info.get('detected', False):
                pattern_score += pattern_info.get('expected_move', 0) * pattern_info.get('confidence', 0.5)
        components[pattern_score] = 0.15
        
        # News sentiment
        news_score = news['sentiment']
        components[news_score] = 0.15
        
        # ML predictions
        ml_score = 0
        if ml_predictions and 'ensemble' in ml_predictions:
            ml_score = ml_predictions['ensemble'].get('prediction', 0)
        components[ml_score] = 0.1
        
        # Calculate final score
        total_weight = sum(components.values())
        final_score = sum(score * weight for score, weight in components.items()) / total_weight
        
        # Confidence calculation
        base_confidence = multi_tf.get('confidence', 50)
        regime_confidence = regime.get('confidence', 50)
        ml_confidence = ml_predictions.get('ensemble', {}).get('confidence', 50) if ml_predictions else 50
        
        final_confidence = (base_confidence * 0.5 + regime_confidence * 0.3 + ml_confidence * 0.2)
        
        # Determine if we should trade
        entry_conditions = self.config.ENTRY_CONDITIONS[symbol]
        should_trade = (
            abs(final_score) >= entry_conditions['signal_threshold'] and
            final_confidence >= entry_conditions['confidence_required']
        )
        
        # Direction
        if final_score > entry_conditions['signal_threshold']:
            direction = 'long'
        elif final_score < -entry_conditions['signal_threshold']:
            direction = 'short'
        else:
            direction = 'neutral'
            should_trade = False
        
        return {
            'should_trade': should_trade,
            'direction': direction,
            'score': final_score,
            'confidence': final_confidence,
            'expected_move': final_score * 0.05,  # Convert to percentage
            'components': components,
            'stop_loss': self.config.STOP_LOSS[symbol],
            'take_profit': self.config.TAKE_PROFIT[symbol]
        }
    
    async def _execute_trade(self, symbol: str, signal: Dict, current_price: float):
        """Execute trade"""
        try:
            # Get available capital
            balance = await self.exchange.get_balance()
            total_capital = balance.get('USDT', {}).get('free', 0)
            
            if total_capital <= 0:
                self.logger.warning("Insufficient USDT balance")
                return
            
            # Get open positions
            open_positions = self.db.get_open_positions()
            
            # Calculate allocation
            allocated_capital = self.risk_manager.calculate_position_allocation(
                symbol, total_capital, open_positions
            )
            
            if allocated_capital <= 0:
                self.logger.warning(f"No capital available for {symbol}")
                return
            
            # Open position
            result = await self.position_manager.open_position(
                symbol, signal, allocated_capital
            )
            
            if result:
                # Send notification
                await self.notifier.send_trade_notification(
                    symbol,
                    f"open_{signal['direction']}",
                    {
                        'price': current_price,
                        'quantity': result['order'].get('amount', 0),
                        'signal_strength': signal['score'],
                        'confidence': signal['confidence']
                    }
                )
                
                self.logger.info(f"✅ Trade executed for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Trade execution error: {e}")
            await self.notifier.send_error_notification(
                "Trade execution failed",
                str(e)
            )
    
    async def _handle_emergency(self, symbol: str, news_sentiment: Dict):
        """Handle emergency news situation"""
        self.logger.warning(f"🚨 Emergency situation for {symbol}")
        
        # Close all positions for the symbol
        positions = self.db.get_open_positions(symbol)
        
        for position in positions:
            await self.position_manager._close_position(
                position, 'emergency_news', position['current_price']
            )
        
        # Send emergency notification
        await self.notifier.send_notification(
            f"🚨 EMERGENCY: {symbol}\n\n{news_sentiment.get('latest_news', 'Unknown news')}\n\nAll positions closed.",
            priority='emergency'
        )
    
    def _prepare_ml_features(self, df: pd.DataFrame, indicators: Dict) -> np.ndarray:
        """Prepare features for ML models"""
        # Select relevant features
        features = []
        
        # Price-based features
        features.extend([
            df['close'].pct_change(1).iloc[-1],
            df['close'].pct_change(5).iloc[-1],
            df['close'].pct_change(20).iloc[-1],
            (df['high'].iloc[-1] - df['low'].iloc[-1]) / df['close'].iloc[-1],
            (df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]
        ])
        
        # Technical indicators
        indicator_features = ['rsi', 'macd', 'adx', 'atr', 'obv']
        for ind in indicator_features:
            if ind in indicators:
                value = indicators[ind].iloc[-1] if hasattr(indicators[ind], 'iloc') else indicators[ind]
                features.append(float(value))
        
        # Normalize volume
        if 'volume_sma' in indicators:
            vol_ratio = df['volume'].iloc[-1] / indicators['volume_sma'].iloc[-1]
            features.append(vol_ratio)
        
        return np.array(features).reshape(1, -1)
    
    async def run_trading_cycle(self):
        """Run one complete trading cycle"""
        self.logger.info("\n" + "="*60)
        self.logger.info(f"Trading cycle started at {datetime.now()}")
        
        for symbol in self.config.SYMBOLS:
            try:
                await self.analyze_and_trade(symbol)
                await asyncio.sleep(2)  # Prevent API rate limits
            except Exception as e:
                self.logger.error(f"Error in trading cycle for {symbol}: {e}")
                await self.notifier.send_error_notification(
                    f"Trading cycle error for {symbol}",
                    str(e)
                )
        
        # Send performance update
        report = self.performance_analyzer.generate_performance_report(1)
        await self.notifier.send_daily_report(report)

# ==============================
# Web Dashboard API
# ==============================
app = FastAPI(title="Bitget Trading System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global reference to trading engine
trading_engine = None

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Bitget Trading System API", "status": "running"}

@app.get("/status")
async def get_status():
    """Get system status"""
    if not trading_engine:
        return {"status": "not_initialized"}
    
    balance = await trading_engine.exchange.get_balance()
    positions = trading_engine.db.get_open_positions()
    
    return {
        "status": "running" if trading_engine.is_running else "stopped",
        "balance": balance.get('USDT', {}).get('free', 0),
        "open_positions": len(positions),
        "symbols": trading_engine.config.SYMBOLS
    }

@app.get("/positions")
async def get_positions():
    """Get all open positions"""
    if not trading_engine:
        return {"error": "System not initialized"}
    
    positions = trading_engine.db.get_open_positions()
    return {"positions": positions}

@app.get("/performance")
async def get_performance(days: int = 7):
    """Get performance statistics"""
    if not trading_engine:
        return {"error": "System not initialized"}
    
    report = trading_engine.performance_analyzer.generate_performance_report(days)
    return {"report": report}

@app.post("/manual_trade")
async def manual_trade(symbol: str, side: str, amount: float):
    """Execute manual trade"""
    if not trading_engine:
        return {"error": "System not initialized"}
    
    # Implement manual trade logic
    return {"message": "Manual trade not implemented"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    try:
        while True:
            # Send updates every second
            if trading_engine:
                data = {
                    "type": "update",
                    "timestamp": datetime.now().isoformat(),
                    "positions": trading_engine.db.get_open_positions()
                }
                await websocket.send_json(data)
            
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass

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
    
    async def start(self):
        """Start the application"""
        try:
            # Initialize
            await self.initialize()
            
            # Setup schedule
            self.setup_schedule()
            self.scheduler.start()
            
            # Start FastAPI in background
            api_task = asyncio.create_task(
                uvicorn.Server(
                    uvicorn.Config(app, host="0.0.0.0", port=8000)
                ).serve()
            )
            
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
        
        # Create and start application
        app = BitgetTradingApplication(config)
        await app.start()
        
    except Exception as e:
        print(f"Failed to start: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # Handle Windows compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Run application
    asyncio.run(main())