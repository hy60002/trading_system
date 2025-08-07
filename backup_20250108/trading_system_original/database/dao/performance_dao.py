"""
Performance DAO
성과 관련 데이터베이스 접근 객체
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base_dao import BaseDAO


class PerformanceDAO(BaseDAO):
    """성과 관련 데이터베이스 접근 객체"""
    
    def __init__(self, db_path: str):
        super().__init__(db_path)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """성과 관련 테이블 생성"""
        tables = {
            'daily_performance': '''
                CREATE TABLE IF NOT EXISTS daily_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    total_pnl_usdt REAL DEFAULT 0,
                    total_pnl_percent REAL DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    profit_factor REAL DEFAULT 0,
                    total_volume REAL DEFAULT 0,
                    total_fees REAL DEFAULT 0,
                    starting_balance REAL DEFAULT 0,
                    ending_balance REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'symbol_performance': '''
                CREATE TABLE IF NOT EXISTS symbol_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    symbol TEXT NOT NULL,
                    pnl_usdt REAL DEFAULT 0,
                    pnl_percent REAL DEFAULT 0,
                    trades_count INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    volume REAL DEFAULT 0,
                    fees REAL DEFAULT 0,
                    avg_trade_duration REAL DEFAULT 0,
                    max_profit REAL DEFAULT 0,
                    max_loss REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, symbol)
                )
            ''',
            'kelly_tracking': '''
                CREATE TABLE IF NOT EXISTS kelly_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    trade_pnl_percent REAL NOT NULL,
                    win_rate REAL DEFAULT 0,
                    avg_win REAL DEFAULT 0,
                    avg_loss REAL DEFAULT 0,
                    kelly_fraction REAL DEFAULT 0,
                    sample_size INTEGER DEFAULT 0
                )
            ''',
            'drawdown_tracking': '''
                CREATE TABLE IF NOT EXISTS drawdown_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    peak_balance REAL NOT NULL,
                    current_balance REAL NOT NULL,
                    drawdown_percent REAL NOT NULL,
                    drawdown_duration INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                )
            '''
        }
        
        for table_name, create_sql in tables.items():
            self._execute_query(create_sql, fetch_all=False)
    
    def get_daily_performance(self, date: str = None) -> Dict[str, Any]:
        """일일 성과 조회"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        cache_key = f"daily_performance:{date}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        query = '''
            SELECT * FROM daily_performance 
            WHERE date = ?
        '''
        
        result = self._execute_query(query, (date,), fetch_one=True)
        
        if result:
            performance = dict(result)
        else:
            # 기본값 반환
            performance = {
                'date': date,
                'total_pnl_usdt': 0.0,
                'total_pnl_percent': 0.0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_trades': 0,
                'win_rate': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'profit_factor': 0.0,
                'total_volume': 0.0,
                'total_fees': 0.0,
                'starting_balance': 0.0,
                'ending_balance': 0.0
            }
        
        self._set_cached_data(cache_key, performance, ttl=300)  # 5분 캐시
        return performance
    
    def update_daily_performance(self, date: str, performance_data: Dict[str, Any]) -> bool:
        """일일 성과 업데이트"""
        sanitized_data = self._sanitize_data(performance_data)
        
        # 캐시 무효화
        self._clear_cache_pattern(f"daily_performance:{date}")
        
        query = '''
            INSERT OR REPLACE INTO daily_performance (
                date, total_pnl_usdt, total_pnl_percent, winning_trades, losing_trades,
                total_trades, win_rate, max_drawdown, sharpe_ratio, profit_factor,
                total_volume, total_fees, starting_balance, ending_balance, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''
        
        params = (
            date,
            sanitized_data.get('total_pnl_usdt', 0),
            sanitized_data.get('total_pnl_percent', 0),
            sanitized_data.get('winning_trades', 0),
            sanitized_data.get('losing_trades', 0),
            sanitized_data.get('total_trades', 0),
            sanitized_data.get('win_rate', 0),
            sanitized_data.get('max_drawdown', 0),
            sanitized_data.get('sharpe_ratio', 0),
            sanitized_data.get('profit_factor', 0),
            sanitized_data.get('total_volume', 0),
            sanitized_data.get('total_fees', 0),
            sanitized_data.get('starting_balance', 0),
            sanitized_data.get('ending_balance', 0)
        )
        
        result = self._execute_query(query, params, fetch_all=False)
        return result > 0
    
    def get_symbol_performance(self, symbol: str, days: int = 30) -> List[Dict[str, Any]]:
        """심볼별 성과 조회"""
        cache_key = f"symbol_performance:{symbol}:days:{days}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        query = '''
            SELECT * FROM symbol_performance 
            WHERE symbol = ? AND date >= date('now', '-{} days')
            ORDER BY date DESC
        '''.format(days)
        
        result = self._execute_query(query, (symbol,))
        self._set_cached_data(cache_key, result, ttl=600)  # 10분 캐시
        return result
    
    def update_symbol_performance(self, date: str, symbol: str, performance_data: Dict[str, Any]) -> bool:
        """심볼별 성과 업데이트"""
        sanitized_data = self._sanitize_data(performance_data)
        
        # 캐시 무효화
        self._clear_cache_pattern(f"symbol_performance:{symbol}:*")
        
        query = '''
            INSERT OR REPLACE INTO symbol_performance (
                date, symbol, pnl_usdt, pnl_percent, trades_count, winning_trades,
                volume, fees, avg_trade_duration, max_profit, max_loss
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            date,
            symbol,
            sanitized_data.get('pnl_usdt', 0),
            sanitized_data.get('pnl_percent', 0),
            sanitized_data.get('trades_count', 0),
            sanitized_data.get('winning_trades', 0),
            sanitized_data.get('volume', 0),
            sanitized_data.get('fees', 0),
            sanitized_data.get('avg_trade_duration', 0),
            sanitized_data.get('max_profit', 0),
            sanitized_data.get('max_loss', 0)
        )
        
        result = self._execute_query(query, params, fetch_all=False)
        return result > 0
    
    def get_kelly_fraction(self, symbol: str) -> float:
        """Kelly 지수 조회"""
        cache_key = f"kelly_fraction:{symbol}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data is not None:
            return cached_data
        
        query = '''
            SELECT kelly_fraction FROM kelly_tracking 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        '''
        
        result = self._execute_query(query, (symbol,), fetch_one=True)
        
        kelly_fraction = result['kelly_fraction'] if result else 0.25  # 기본값 25%
        
        self._set_cached_data(cache_key, kelly_fraction, ttl=1800)  # 30분 캐시
        return kelly_fraction
    
    def update_kelly_tracking(self, symbol: str, trade_pnl_percent: float) -> bool:
        """Kelly 추적 업데이트"""
        # 최근 20거래 데이터로 Kelly 계산
        query = '''
            SELECT trade_pnl_percent FROM kelly_tracking 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT 19
        '''
        
        recent_trades = self._execute_query(query, (symbol,))
        all_trades = [trade_pnl_percent] + [trade['trade_pnl_percent'] for trade in recent_trades]
        
        # Kelly 계산
        wins = [pnl for pnl in all_trades if pnl > 0]
        losses = [abs(pnl) for pnl in all_trades if pnl < 0]
        
        if len(wins) > 0 and len(losses) > 0:
            win_rate = len(wins) / len(all_trades)
            avg_win = sum(wins) / len(wins)
            avg_loss = sum(losses) / len(losses)
            
            # Kelly Formula: f = (bp - q) / b
            # b = avg_win/avg_loss, p = win_rate, q = 1-win_rate
            if avg_loss > 0:
                b = avg_win / avg_loss
                kelly_fraction = (b * win_rate - (1 - win_rate)) / b
                kelly_fraction = max(0, min(kelly_fraction, 0.25))  # 0-25% 제한
            else:
                kelly_fraction = 0.25
        else:
            kelly_fraction = 0.25
            win_rate = 0.5
            avg_win = 0.02
            avg_loss = 0.02
        
        # 캐시 무효화
        self._clear_cache_pattern(f"kelly_fraction:{symbol}")
        
        # 데이터베이스 업데이트
        insert_query = '''
            INSERT INTO kelly_tracking (
                symbol, trade_pnl_percent, win_rate, avg_win, avg_loss, kelly_fraction, sample_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (symbol, trade_pnl_percent, win_rate, avg_win, avg_loss, kelly_fraction, len(all_trades))
        
        result = self._execute_insert(insert_query, params)
        return result is not None
    
    def get_performance_summary(self, days: int = 30) -> Dict[str, Any]:
        """성과 요약 조회"""
        cache_key = f"performance_summary:days:{days}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        # 일별 성과 합계
        query = '''
            SELECT 
                COUNT(*) as trading_days,
                SUM(total_pnl_usdt) as total_pnl,
                AVG(total_pnl_percent) as avg_daily_return,
                SUM(total_trades) as total_trades,
                SUM(winning_trades) as total_wins,
                SUM(losing_trades) as total_losses,
                MAX(max_drawdown) as worst_drawdown,
                AVG(win_rate) as avg_win_rate
            FROM daily_performance 
            WHERE date >= date('now', '-{} days')
        '''.format(days)
        
        result = self._execute_query(query, (), fetch_one=True)
        
        if result and result['trading_days'] > 0:
            summary = {
                'trading_days': result['trading_days'],
                'total_pnl_usdt': result['total_pnl'] or 0.0,
                'avg_daily_return': result['avg_daily_return'] or 0.0,
                'total_trades': result['total_trades'] or 0,
                'total_wins': result['total_wins'] or 0,
                'total_losses': result['total_losses'] or 0,
                'overall_win_rate': (result['total_wins'] or 0) / max(result['total_trades'] or 1, 1),
                'worst_drawdown': result['worst_drawdown'] or 0.0,
                'avg_win_rate': result['avg_win_rate'] or 0.0
            }
            
            # 연환산 수익률 계산
            if summary['avg_daily_return'] != 0:
                summary['annualized_return'] = (1 + summary['avg_daily_return']) ** 365 - 1
            else:
                summary['annualized_return'] = 0.0
        else:
            summary = {
                'trading_days': 0,
                'total_pnl_usdt': 0.0,
                'avg_daily_return': 0.0,
                'total_trades': 0,
                'total_wins': 0,
                'total_losses': 0,
                'overall_win_rate': 0.0,
                'worst_drawdown': 0.0,
                'avg_win_rate': 0.0,
                'annualized_return': 0.0
            }
        
        self._set_cached_data(cache_key, summary, ttl=1800)  # 30분 캐시
        return summary
    
    def record_drawdown(self, peak_balance: float, current_balance: float) -> bool:
        """드로우다운 기록"""
        drawdown_percent = (peak_balance - current_balance) / peak_balance if peak_balance > 0 else 0
        
        query = '''
            INSERT INTO drawdown_tracking (
                peak_balance, current_balance, drawdown_percent, is_active
            ) VALUES (?, ?, ?, ?)
        '''
        
        params = (peak_balance, current_balance, drawdown_percent, drawdown_percent > 0)
        
        result = self._execute_insert(query, params)
        return result is not None
    
    def get_current_drawdown(self) -> Dict[str, Any]:
        """현재 드로우다운 조회"""
        query = '''
            SELECT * FROM drawdown_tracking 
            WHERE is_active = 1 
            ORDER BY timestamp DESC 
            LIMIT 1
        '''
        
        result = self._execute_query(query, (), fetch_one=True)
        
        if result:
            return {
                'peak_balance': result['peak_balance'],
                'current_balance': result['current_balance'],
                'drawdown_percent': result['drawdown_percent'],
                'duration_hours': 0  # 계산 필요시 추가
            }
        else:
            return {
                'peak_balance': 0.0,
                'current_balance': 0.0,
                'drawdown_percent': 0.0,
                'duration_hours': 0
            }