"""
Enhanced Database Manager with Connection Pooling and Error Handling
Author: Enhanced by Claude Code  
Version: 4.0
"""

import sqlite3
import asyncio
import aiosqlite
import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, List, Dict, Any, Tuple, AsyncGenerator
from datetime import datetime, timedelta
import json
import threading
from queue import Queue
import time

from .exceptions import DatabaseError, DatabaseConnectionError, DatabaseQueryError, handle_async_exceptions
from .config import TradingConfig

logger = logging.getLogger(__name__)

class DatabasePool:
    """Connection pool for SQLite database"""
    
    def __init__(self, database_path: str, max_connections: int = 10):
        self.database_path = database_path
        self.max_connections = max_connections
        self._pool = Queue(maxsize=max_connections)
        self._active_connections = 0
        self._lock = threading.Lock()
        
        # Initialize pool
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        try:
            for _ in range(self.max_connections):
                conn = sqlite3.connect(
                    self.database_path,
                    check_same_thread=False,
                    timeout=30
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=MEMORY")
                self._pool.put(conn)
            
            logger.info(f"Database pool initialized with {self.max_connections} connections")
        except Exception as e:
            raise DatabaseConnectionError(
                f"Failed to initialize database pool: {str(e)}",
                context={'database_path': self.database_path}
            )
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool"""
        conn = None
        try:
            with self._lock:
                if self._pool.empty() and self._active_connections < self.max_connections:
                    conn = sqlite3.connect(
                        self.database_path,
                        check_same_thread=False,
                        timeout=30
                    )
                    conn.row_factory = sqlite3.Row
                    self._active_connections += 1
                else:
                    conn = self._pool.get(timeout=30)
            
            yield conn
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise DatabaseConnectionError(
                f"Failed to get database connection: {str(e)}"
            )
        finally:
            if conn:
                try:
                    if not self._pool.full():
                        self._pool.put(conn)
                    else:
                        conn.close()
                        with self._lock:
                            self._active_connections -= 1
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")

class EnhancedDatabaseManager:
    """Enhanced database manager with connection pooling and async support"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.database_path = config.DATABASE_URL.replace('sqlite:///', '')
        self.pool = DatabasePool(self.database_path, config.DATABASE_POOL_SIZE)
        self._initialized = False
        self.logger = logging.getLogger(__name__)
        
        # Metrics
        self.query_count = 0
        self.error_count = 0
        self.last_health_check = datetime.utcnow()
    
    async def initialize(self):
        """Initialize database schema"""
        if self._initialized:
            return
            
        try:
            await self._create_tables()
            await self._create_indexes()
            self._initialized = True
            logger.info("Database initialized successfully")
        except Exception as e:
            raise DatabaseError(
                f"Failed to initialize database: {str(e)}",
                operation="initialize"
            )
    
    async def _create_tables(self):
        """Create database tables"""
        tables = {
            'trades': '''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    order_id TEXT UNIQUE,
                    status TEXT DEFAULT 'pending',
                    strategy TEXT,
                    pnl REAL DEFAULT 0,
                    fees REAL DEFAULT 0,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'positions': '''
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    unrealized_pnl REAL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0,
                    leverage INTEGER DEFAULT 1,
                    stop_loss REAL,
                    take_profit REAL,
                    status TEXT DEFAULT 'open',
                    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    closed_at DATETIME,
                    strategy TEXT,
                    metadata TEXT
                )
            ''',
            'market_data': '''
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    timeframe TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    indicators TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'performance': '''
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    total_pnl REAL DEFAULT 0,
                    daily_pnl REAL DEFAULT 0,
                    trades_count INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    portfolio_value REAL DEFAULT 0,
                    strategy TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'signals': '''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    strength REAL NOT NULL,
                    price REAL NOT NULL,
                    timeframe TEXT,
                    strategy TEXT,
                    indicators TEXT,
                    executed BOOLEAN DEFAULT FALSE,
                    metadata TEXT
                )
            ''',
            'risk_metrics': '''
                CREATE TABLE IF NOT EXISTS risk_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT,
                    portfolio_risk REAL,
                    position_risk REAL,
                    var_1d REAL,
                    var_7d REAL,
                    correlation_risk REAL,
                    leverage_risk REAL,
                    liquidity_risk REAL,
                    metadata TEXT
                )
            '''
        }
        
        async with aiosqlite.connect(self.database_path) as db:
            for table_name, sql in tables.items():
                try:
                    await db.execute(sql)
                    logger.debug(f"Created table: {table_name}")
                except Exception as e:
                    raise DatabaseQueryError(
                        f"Failed to create table {table_name}: {str(e)}",
                        operation="create_table",
                        table=table_name
                    )
            await db.commit()
    
    async def _create_indexes(self):
        """Create database indexes for performance"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp ON trades(symbol, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)", 
            "CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy)",
            "CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)",
            "CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe ON market_data(symbol, timeframe, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp ON signals(symbol, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_signals_executed ON signals(executed)",
            "CREATE INDEX IF NOT EXISTS idx_performance_date ON performance(date)",
            "CREATE INDEX IF NOT EXISTS idx_risk_metrics_timestamp ON risk_metrics(timestamp)"
        ]
        
        async with aiosqlite.connect(self.database_path) as db:
            for index_sql in indexes:
                try:
                    await db.execute(index_sql)
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")
            await db.commit()
    
    @handle_async_exceptions()
    async def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results"""
        start_time = time.time()
        try:
            async with aiosqlite.connect(self.database_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params or ()) as cursor:
                    rows = await cursor.fetchall()
                    result = [dict(row) for row in rows]
                    
                    self.query_count += 1
                    query_time = time.time() - start_time
                    
                    if query_time > 1.0:  # Log slow queries
                        logger.warning(f"Slow query ({query_time:.2f}s): {query[:100]}...")
                    
                    return result
                    
        except Exception as e:
            self.error_count += 1
            raise DatabaseQueryError(
                f"Query execution failed: {str(e)}",
                operation="select",
                context={'query': query[:100], 'params': str(params)}
            )
    
    @handle_async_exceptions()
    async def execute_write(self, query: str, params: Optional[Tuple] = None) -> int:
        """Execute INSERT/UPDATE/DELETE query and return affected rows"""
        start_time = time.time()
        try:
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute(query, params or ())
                await db.commit()
                
                affected_rows = db.total_changes
                self.query_count += 1
                
                query_time = time.time() - start_time
                if query_time > 1.0:
                    logger.warning(f"Slow write query ({query_time:.2f}s): {query[:100]}...")
                
                return affected_rows
                
        except Exception as e:
            self.error_count += 1
            raise DatabaseQueryError(
                f"Write query execution failed: {str(e)}",
                operation="write",
                context={'query': query[:100], 'params': str(params)}
            )
    
    @handle_async_exceptions()
    async def execute_transaction(self, queries: List[Tuple[str, Optional[Tuple]]]) -> bool:
        """Execute multiple queries in a transaction"""
        try:
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute("BEGIN TRANSACTION")
                
                try:
                    for query, params in queries:
                        await db.execute(query, params or ())
                    
                    await db.commit()
                    self.query_count += len(queries)
                    return True
                    
                except Exception as e:
                    await db.rollback()
                    raise e
                    
        except Exception as e:
            self.error_count += 1
            raise DatabaseQueryError(
                f"Transaction execution failed: {str(e)}",
                operation="transaction",
                context={'queries_count': len(queries)}
            )
    
    # Trade operations
    async def save_trade(self, trade_data: Dict[str, Any]) -> int:
        """Save trade to database"""
        query = '''
            INSERT INTO trades (symbol, side, amount, price, order_id, status, strategy, pnl, fees, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            trade_data.get('symbol'),
            trade_data.get('side'),
            trade_data.get('amount'),
            trade_data.get('price'),
            trade_data.get('order_id'),
            trade_data.get('status', 'pending'),
            trade_data.get('strategy'),
            trade_data.get('pnl', 0),
            trade_data.get('fees', 0),
            json.dumps(trade_data.get('metadata', {}))
        )
        return await self.execute_write(query, params)
    
    async def get_trades(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades from database"""
        query = "SELECT * FROM trades"
        params = ()
        
        if symbol:
            query += " WHERE symbol = ?"
            params = (symbol,)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params += (limit,)
        
        return await self.execute_query(query, params)
    
    # Position operations
    async def save_position(self, position_data: Dict[str, Any]) -> int:
        """Save position to database"""
        query = '''
            INSERT INTO positions (symbol, side, size, entry_price, current_price, leverage, 
                                 stop_loss, take_profit, strategy, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            position_data.get('symbol'),
            position_data.get('side'),
            position_data.get('size'),
            position_data.get('entry_price'),
            position_data.get('current_price'),
            position_data.get('leverage', 1),
            position_data.get('stop_loss'),
            position_data.get('take_profit'),
            position_data.get('strategy'),
            json.dumps(position_data.get('metadata', {}))
        )
        return await self.execute_write(query, params)
    
    async def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get open positions"""
        query = "SELECT * FROM positions WHERE status = 'open'"
        params = ()
        
        if symbol:
            query += " AND symbol = ?"
            params = (symbol,)
        
        return await self.execute_query(query, params)
    
    # Market data operations
    async def save_market_data(self, market_data: Dict[str, Any]) -> int:
        """Save market data"""
        query = '''
            INSERT INTO market_data (symbol, timestamp, timeframe, open, high, low, close, volume, indicators)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            market_data.get('symbol'),
            market_data.get('timestamp'),
            market_data.get('timeframe'),
            market_data.get('open'),
            market_data.get('high'),
            market_data.get('low'),
            market_data.get('close'),
            market_data.get('volume'),
            json.dumps(market_data.get('indicators', {}))
        )
        return await self.execute_write(query, params)
    
    async def get_market_data(self, symbol: str, timeframe: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get market data"""
        query = '''
            SELECT * FROM market_data 
            WHERE symbol = ? AND timeframe = ? 
            ORDER BY timestamp DESC LIMIT ?
        '''
        return await self.execute_query(query, (symbol, timeframe, limit))
    
    # Performance tracking
    async def save_performance(self, performance_data: Dict[str, Any]) -> int:
        """Save performance metrics"""
        query = '''
            INSERT OR REPLACE INTO performance 
            (date, total_pnl, daily_pnl, trades_count, win_rate, sharpe_ratio, max_drawdown, portfolio_value, strategy, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            performance_data.get('date'),
            performance_data.get('total_pnl', 0),
            performance_data.get('daily_pnl', 0),
            performance_data.get('trades_count', 0),
            performance_data.get('win_rate', 0),
            performance_data.get('sharpe_ratio', 0),
            performance_data.get('max_drawdown', 0),
            performance_data.get('portfolio_value', 0),
            performance_data.get('strategy'),
            json.dumps(performance_data.get('metadata', {}))
        )
        return await self.execute_write(query, params)
    
    # Health check
    async def health_check(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            start_time = time.time()
            await self.execute_query("SELECT 1")
            response_time = time.time() - start_time
            
            # Get database size
            result = await self.execute_query("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = result[0]['size'] if result else 0
            
            self.last_health_check = datetime.utcnow()
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'query_count': self.query_count,
                'error_count': self.error_count,
                'database_size': db_size,
                'last_check': self.last_health_check.isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': self.last_health_check.isoformat()
            }
    
    # Cleanup operations
    async def cleanup_old_data(self, days: int = 30):
        """Clean up old data"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        cleanup_queries = [
            ("DELETE FROM market_data WHERE created_at < ?", (cutoff_date,)),
            ("DELETE FROM signals WHERE timestamp < ? AND executed = TRUE", (cutoff_date,)),
            ("DELETE FROM risk_metrics WHERE timestamp < ?", (cutoff_date,))
        ]
        
        return await self.execute_transaction(cleanup_queries)