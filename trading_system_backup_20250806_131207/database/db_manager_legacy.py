"""
Enhanced Database Manager
Complete database operations for the trading system
"""

import sqlite3
import threading
import logging
import json
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime
from cachetools import TTLCache

try:
    import redis
except ImportError:
    redis = None


class EnhancedDatabaseManager:
    """Database manager with complete implementation"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
        self._init_redis()
        
    async def initialize(self):
        """Initialize database (async compatibility)"""
        # Already initialized in __init__, this is for compatibility
        return True
    
    def _init_redis(self):
        """Initialize Redis for caching"""
        try:
            if redis:
                self.redis_client = redis.Redis(
                    host='localhost', 
                    port=6379, 
                    decode_responses=True,
                    socket_connect_timeout=5
                )
                self.redis_client.ping()
                self.redis_enabled = True
            else:
                raise ImportError("Redis not available")
        except (ConnectionError, ImportError, Exception) as e:
            self.redis_enabled = False
            logging.warning(f"Redis를 사용할 수 없습니다. 메모리 캐시를 사용합니다. 오류: {e}")
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
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp
                ON predictions (symbol, timestamp)
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
                    kelly_fraction REAL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_status
                ON trades (status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp
                ON trades (symbol, timestamp)
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
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_status
                ON positions (status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol
                ON positions (symbol)
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
                    total_fees REAL DEFAULT 0,
                    kelly_fraction REAL
                )
            """)

            # Kelly Criterion tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kelly_tracking (
                    symbol TEXT PRIMARY KEY,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    total_wins REAL DEFAULT 0,
                    total_losses REAL DEFAULT 0,
                    avg_win REAL DEFAULT 0,
                    avg_loss REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    kelly_fraction REAL DEFAULT 0,
                    last_update DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ML Model performance tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ml_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    model_name TEXT NOT NULL,
                    symbol TEXT,
                    prediction REAL NOT NULL,
                    actual REAL,
                    correct BOOLEAN,
                    confidence REAL,
                    features TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_timestamp
                ON ml_performance (model_name, timestamp)
            """)

            # News tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    title TEXT NOT NULL,
                    source TEXT,
                    url TEXT,
                    sentiment REAL,
                    confidence REAL,
                    impact TEXT,
                    symbols TEXT,
                    used_for_trading BOOLEAN DEFAULT FALSE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_news_timestamp
                ON news_history (timestamp)
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

            # Trade history table (for statistics and analysis)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    leverage INTEGER DEFAULT 1,
                    entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    exit_time DATETIME,
                    pnl REAL DEFAULT 0,
                    pnl_percent REAL DEFAULT 0,
                    fees REAL DEFAULT 0,
                    status TEXT DEFAULT 'open',
                    reason TEXT,
                    signal_strength REAL,
                    confidence REAL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_history_symbol_date
                ON trade_history (symbol, entry_time)
            """)

            # Balance history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    total_balance REAL NOT NULL,
                    usdt_balance REAL NOT NULL,
                    btc_balance REAL DEFAULT 0,
                    eth_balance REAL DEFAULT 0
                )
            """)

            # Kelly tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kelly_tracking (
                    symbol TEXT PRIMARY KEY,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    total_wins REAL DEFAULT 0,
                    total_losses REAL DEFAULT 0,
                    kelly_fraction REAL DEFAULT 0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
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
    
    def update_kelly_tracking(self, symbol: str, trade_pnl: float):
        """Update Kelly Criterion tracking data"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if record exists
            cursor.execute("SELECT * FROM kelly_tracking WHERE symbol = ?", (symbol,))
            record = cursor.fetchone()
            
            if record:
                total_trades = record['total_trades'] + 1
                winning_trades = record['winning_trades'] + (1 if trade_pnl > 0 else 0)
                total_wins = record['total_wins'] + (trade_pnl if trade_pnl > 0 else 0)
                total_losses = record['total_losses'] + (abs(trade_pnl) if trade_pnl < 0 else 0)
                
                # Calculate averages
                avg_win = total_wins / winning_trades if winning_trades > 0 else 0
                avg_loss = total_losses / (total_trades - winning_trades) if total_trades > winning_trades else 0
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                
                # Calculate Kelly fraction
                if avg_loss > 0:
                    kelly_raw = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
                    kelly_fraction = max(0, min(0.25, kelly_raw))  # Cap at 25%
                else:
                    kelly_fraction = 0.1  # Default
                
                cursor.execute("""
                    UPDATE kelly_tracking 
                    SET total_trades = ?, winning_trades = ?, total_wins = ?, 
                        total_losses = ?, avg_win = ?, avg_loss = ?, 
                        win_rate = ?, kelly_fraction = ?, last_update = CURRENT_TIMESTAMP
                    WHERE symbol = ?
                """, (total_trades, winning_trades, total_wins, total_losses, 
                      avg_win, avg_loss, win_rate, kelly_fraction, symbol))
            else:
                # Create new record
                winning = 1 if trade_pnl > 0 else 0
                wins = trade_pnl if trade_pnl > 0 else 0
                losses = abs(trade_pnl) if trade_pnl < 0 else 0
                
                cursor.execute("""
                    INSERT INTO kelly_tracking 
                    (symbol, total_trades, winning_trades, total_wins, total_losses, 
                     avg_win, avg_loss, win_rate, kelly_fraction)
                    VALUES (?, 1, ?, ?, ?, ?, ?, ?, 0.1)
                """, (symbol, winning, wins, losses, wins, losses, float(winning), ))
    
    def get_kelly_fraction(self, symbol: str) -> float:
        """Get Kelly fraction for symbol"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT kelly_fraction, total_trades 
                FROM kelly_tracking 
                WHERE symbol = ?
            """, (symbol,))
            record = cursor.fetchone()
            
            if record and record['total_trades'] >= 20:  # Minimum trades for reliability
                return record['kelly_fraction']
            else:
                return 0.1  # Default safe value
    
    def save_ml_prediction(self, model_name: str, symbol: str, prediction: float, 
                           confidence: float, features: Dict):
        """Save ML prediction for tracking"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ml_performance 
                (model_name, symbol, prediction, confidence, features)
                VALUES (?, ?, ?, ?, ?)
            """, (model_name, symbol, prediction, confidence, json.dumps(features)))
            return cursor.lastrowid
    
    def update_ml_prediction_result(self, prediction_id: int, actual: float):
        """Update ML prediction with actual result"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ml_performance 
                SET actual = ?, correct = (SIGN(prediction) = SIGN(?))
                WHERE id = ?
            """, (actual, actual, prediction_id))
    
    def get_ml_model_performance(self, model_name: str, window: int = 1000) -> Dict:
        """Get ML model performance metrics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END) as correct,
                       AVG(confidence) as avg_confidence
                FROM (
                    SELECT * FROM ml_performance 
                    WHERE model_name = ? AND actual IS NOT NULL
                    ORDER BY timestamp DESC 
                    LIMIT ?
                )
            """, (model_name, window))
            
            result = cursor.fetchone()
            if result and result['total'] > 0:
                return {
                    'accuracy': result['correct'] / result['total'],
                    'total_predictions': result['total'],
                    'avg_confidence': result['avg_confidence'] or 0.5
                }
            else:
                return {
                    'accuracy': 0.5,
                    'total_predictions': 0,
                    'avg_confidence': 0.5
                }
    
    def save_news_item(self, news_data: Dict):
        """Save news item with sentiment analysis"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO news_history 
                (title, source, url, sentiment, confidence, impact, symbols, used_for_trading)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                news_data['title'],
                news_data['source'],
                news_data.get('url', ''),
                news_data['sentiment'],
                news_data['confidence'],
                news_data['impact'],
                json.dumps(news_data.get('symbols', [])),
                news_data.get('used_for_trading', False)
            ))
    
    def cache_set(self, key: str, value: Any, ttl: int = 300):
        """Set cache value with error handling"""
        try:
            if self.redis_enabled:
                self.redis_client.setex(key, ttl, json.dumps(value))
            else:
                self.memory_cache[key] = value
        except Exception as e:
            logging.error(f"캐시 설정 오류: {e}")
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Get cache value with error handling"""
        try:
            if self.redis_enabled:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logging.error(f"캐시 조회 오류: {e}")
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
            'total_fees': 0.0,
            'kelly_fraction': 0.0
        }
    
    def get_latest_balance(self) -> Dict:
        """Get latest balance information"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Try to get the most recent balance record
                cursor.execute("""
                    SELECT total_balance, usdt_balance, btc_balance, eth_balance, timestamp
                    FROM balance_history 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                if result:
                    return {
                        'total_balance': float(result[0]),
                        'usdt_balance': float(result[1]),
                        'btc_balance': float(result[2] or 0),
                        'eth_balance': float(result[3] or 0),
                        'timestamp': result[4]
                    }
                else:
                    # No balance history, return default values
                    return {
                        'total_balance': 10000.0,  # Default for testing
                        'usdt_balance': 10000.0,
                        'btc_balance': 0.0,
                        'eth_balance': 0.0,
                        'timestamp': datetime.now().isoformat()
                    }
                    
            except sqlite3.Error as e:
                logging.error(f"잔고 조회 오류: {e}")
                # Return default fallback values
                return {
                    'total_balance': 10000.0,  # Default for testing
                    'usdt_balance': 10000.0,
                    'btc_balance': 0.0,
                    'eth_balance': 0.0,
                    'timestamp': datetime.now().isoformat()
                }
    
    def save_balance_snapshot(self, balance_data: Dict):
        """Save balance snapshot to database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO balance_history 
                    (total_balance, usdt_balance, btc_balance, eth_balance, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    balance_data.get('total_balance', 0),
                    balance_data.get('usdt_balance', 0),
                    balance_data.get('btc_balance', 0),
                    balance_data.get('eth_balance', 0),
                    datetime.now().isoformat()
                ))
                
            except sqlite3.Error as e:
                logging.error(f"잔고 저장 오류: {e}")
    
    def get_symbol_trades_today(self, symbol: str) -> Dict:
        """Get today's trade statistics for a symbol"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN pnl_percent < 0 THEN 1 ELSE 0 END) as losses,
                           MAX(entry_time) as last_trade
                    FROM trade_history 
                    WHERE symbol = ? AND DATE(entry_time) = ?
                """, (symbol, today))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'total': result[0] or 0,
                        'losses': result[1] or 0,
                        'last_trade': result[2]
                    }
                else:
                    return {'total': 0, 'losses': 0, 'last_trade': None}
                    
            except sqlite3.Error as e:
                logging.error(f"심볼 거래 통계 조회 오류: {e}")
                return {'total': 0, 'losses': 0, 'last_trade': None}