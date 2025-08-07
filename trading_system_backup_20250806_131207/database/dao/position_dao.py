"""
Position DAO
포지션 관련 데이터베이스 접근 객체
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from .base_dao import BaseDAO


class PositionDAO(BaseDAO):
    """포지션 관련 데이터베이스 접근 객체"""
    
    def __init__(self, db_path: str):
        super().__init__(db_path)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """포지션 관련 테이블 생성"""
        tables = {
            'positions': '''
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    trade_id INTEGER,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    quantity REAL NOT NULL,
                    side TEXT NOT NULL,
                    pnl REAL DEFAULT 0,
                    pnl_percent REAL DEFAULT 0,
                    entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    stop_loss REAL,
                    take_profit REAL,
                    trailing_stop REAL,
                    status TEXT DEFAULT 'open',
                    margin_used REAL DEFAULT 0,
                    leverage REAL DEFAULT 1,
                    liquidation_price REAL,
                    unrealized_pnl REAL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0,
                    fees_paid REAL DEFAULT 0,
                    last_update DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'balance_history': '''
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    total_balance REAL NOT NULL,
                    usdt_balance REAL NOT NULL,
                    btc_balance REAL DEFAULT 0,
                    eth_balance REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    margin_used REAL DEFAULT 0,
                    free_balance REAL DEFAULT 0
                )
            '''
        }
        
        for table_name, create_sql in tables.items():
            self._execute_query(create_sql, fetch_all=False)
    
    def add_position(self, position_data: Dict[str, Any]) -> int:
        """포지션 추가"""
        required_fields = ['symbol', 'entry_price', 'quantity', 'side']
        self._validate_required_fields(position_data, required_fields)
        
        sanitized_data = self._sanitize_data(position_data)
        
        # 캐시 무효화
        self._clear_cache_pattern(f"positions:{sanitized_data['symbol']}:*")
        self._clear_cache_pattern("positions:active:*")
        
        query = '''
            INSERT INTO positions (
                symbol, trade_id, entry_price, current_price, quantity, side,
                pnl, pnl_percent, stop_loss, take_profit, trailing_stop,
                status, margin_used, leverage, liquidation_price,
                unrealized_pnl, realized_pnl, fees_paid
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            sanitized_data['symbol'],
            sanitized_data.get('trade_id'),
            sanitized_data['entry_price'],
            sanitized_data.get('current_price', sanitized_data['entry_price']),
            sanitized_data['quantity'],
            sanitized_data['side'],
            sanitized_data.get('pnl', 0),
            sanitized_data.get('pnl_percent', 0),
            sanitized_data.get('stop_loss'),
            sanitized_data.get('take_profit'),
            sanitized_data.get('trailing_stop'),
            sanitized_data.get('status', 'open'),
            sanitized_data.get('margin_used', 0),
            sanitized_data.get('leverage', 1),
            sanitized_data.get('liquidation_price'),
            sanitized_data.get('unrealized_pnl', 0),
            sanitized_data.get('realized_pnl', 0),
            sanitized_data.get('fees_paid', 0)
        )
        
        return self._execute_insert(query, params)
    
    def get_active_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """활성 포지션 조회"""
        if symbol:
            cache_key = f"positions:{symbol}:active"
            query = '''
                SELECT * FROM positions 
                WHERE symbol = ? AND status = 'open' 
                ORDER BY entry_time DESC
            '''
            params = (symbol,)
        else:
            cache_key = "positions:active:all"
            query = '''
                SELECT * FROM positions 
                WHERE status = 'open' 
                ORDER BY entry_time DESC
            '''
            params = ()
        
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        result = self._execute_query(query, params)
        self._set_cached_data(cache_key, result, ttl=60)  # 1분 캐시 (포지션은 자주 변경)
        return result
    
    def update_position(self, position_id: int, update_data: Dict[str, Any]) -> bool:
        """포지션 업데이트"""
        sanitized_data = self._sanitize_data(update_data)
        
        # 업데이트할 필드 구성
        set_clauses = []
        params = []
        
        for field, value in sanitized_data.items():
            if field != 'id':  # ID는 업데이트하지 않음
                set_clauses.append(f"{field} = ?")
                params.append(value)
        
        if not set_clauses:
            return False
        
        # last_update 자동 추가
        set_clauses.append("last_update = CURRENT_TIMESTAMP")
        
        query = f"UPDATE positions SET {', '.join(set_clauses)} WHERE id = ?"
        params.append(position_id)
        
        # 캐시 무효화
        self._clear_cache_pattern("positions:*")
        
        result = self._execute_query(query, tuple(params), fetch_all=False)
        return result > 0
    
    def close_position(self, position_id: int, exit_price: float, exit_reason: str = 'manual') -> bool:
        """포지션 종료"""
        # 포지션 정보 조회
        position = self.get_position_by_id(position_id)
        if not position:
            return False
        
        # PnL 계산
        entry_price = position['entry_price']
        quantity = position['quantity']
        side = position['side']
        
        if side.lower() == 'long':
            pnl = (exit_price - entry_price) * quantity
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        else:  # short
            pnl = (entry_price - exit_price) * quantity
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        
        # 포지션 업데이트
        update_data = {
            'current_price': exit_price,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'status': 'closed',
            'realized_pnl': pnl
        }
        
        return self.update_position(position_id, update_data)
    
    def get_position_by_id(self, position_id: int) -> Optional[Dict[str, Any]]:
        """ID로 포지션 조회"""
        cache_key = f"position:id:{position_id}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        query = "SELECT * FROM positions WHERE id = ?"
        result = self._execute_query(query, (position_id,), fetch_one=True)
        
        if result:
            self._set_cached_data(cache_key, result, ttl=300)  # 5분 캐시
        
        return result
    
    def get_positions_by_symbol(self, symbol: str, status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """심볼별 포지션 조회"""
        cache_key = f"positions:{symbol}:status:{status or 'all'}:limit:{limit}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        if status:
            query = '''
                SELECT * FROM positions 
                WHERE symbol = ? AND status = ? 
                ORDER BY entry_time DESC 
                LIMIT ?
            '''
            params = (symbol, status, limit)
        else:
            query = '''
                SELECT * FROM positions 
                WHERE symbol = ? 
                ORDER BY entry_time DESC 
                LIMIT ?
            '''
            params = (symbol, limit)
        
        result = self._execute_query(query, params)
        self._set_cached_data(cache_key, result, ttl=300)  # 5분 캐시
        return result
    
    def get_position_summary(self, symbol: str = None) -> Dict[str, Any]:
        """포지션 요약 정보"""
        if symbol:
            cache_key = f"position_summary:{symbol}"
            query = '''
                SELECT 
                    COUNT(*) as total_positions,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_positions,
                    SUM(CASE WHEN status = 'open' THEN unrealized_pnl ELSE 0 END) as total_unrealized_pnl,
                    SUM(CASE WHEN status = 'closed' THEN realized_pnl ELSE 0 END) as total_realized_pnl,
                    SUM(CASE WHEN status = 'open' THEN margin_used ELSE 0 END) as total_margin_used,
                    AVG(CASE WHEN status = 'closed' THEN pnl_percent END) as avg_pnl_percent
                FROM positions 
                WHERE symbol = ?
            '''
            params = (symbol,)
        else:
            cache_key = "position_summary:all"
            query = '''
                SELECT 
                    COUNT(*) as total_positions,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_positions,
                    SUM(CASE WHEN status = 'open' THEN unrealized_pnl ELSE 0 END) as total_unrealized_pnl,
                    SUM(CASE WHEN status = 'closed' THEN realized_pnl ELSE 0 END) as total_realized_pnl,
                    SUM(CASE WHEN status = 'open' THEN margin_used ELSE 0 END) as total_margin_used,
                    AVG(CASE WHEN status = 'closed' THEN pnl_percent END) as avg_pnl_percent
                FROM positions
            '''
            params = ()
        
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        result = self._execute_query(query, params, fetch_one=True)
        
        if result:
            summary = {
                'total_positions': result['total_positions'] or 0,
                'open_positions': result['open_positions'] or 0,
                'closed_positions': result['closed_positions'] or 0,
                'total_unrealized_pnl': result['total_unrealized_pnl'] or 0.0,
                'total_realized_pnl': result['total_realized_pnl'] or 0.0,
                'total_margin_used': result['total_margin_used'] or 0.0,
                'avg_pnl_percent': result['avg_pnl_percent'] or 0.0
            }
        else:
            summary = {
                'total_positions': 0, 'open_positions': 0, 'closed_positions': 0,
                'total_unrealized_pnl': 0.0, 'total_realized_pnl': 0.0,
                'total_margin_used': 0.0, 'avg_pnl_percent': 0.0
            }
        
        self._set_cached_data(cache_key, summary, ttl=300)  # 5분 캐시
        return summary
    
    def add_balance_record(self, balance_data: Dict[str, Any]) -> int:
        """잔액 기록 추가"""
        required_fields = ['total_balance', 'usdt_balance']
        self._validate_required_fields(balance_data, required_fields)
        
        sanitized_data = self._sanitize_data(balance_data)
        
        query = '''
            INSERT INTO balance_history (
                total_balance, usdt_balance, btc_balance, eth_balance,
                unrealized_pnl, margin_used, free_balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            sanitized_data['total_balance'],
            sanitized_data['usdt_balance'],
            sanitized_data.get('btc_balance', 0),
            sanitized_data.get('eth_balance', 0),
            sanitized_data.get('unrealized_pnl', 0),
            sanitized_data.get('margin_used', 0),
            sanitized_data.get('free_balance', 0)
        )
        
        # 캐시 무효화
        self._clear_cache_pattern("balance:*")
        
        return self._execute_insert(query, params)
    
    def get_latest_balance(self) -> Optional[Dict[str, Any]]:
        """최신 잔액 조회"""
        cache_key = "balance:latest"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        query = '''
            SELECT * FROM balance_history 
            ORDER BY timestamp DESC 
            LIMIT 1
        '''
        
        result = self._execute_query(query, fetch_one=True)
        
        if result:
            self._set_cached_data(cache_key, result, ttl=60)  # 1분 캐시
        
        return result
    
    def get_balance_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """잔액 히스토리 조회"""
        cache_key = f"balance:history:days:{days}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        query = '''
            SELECT * FROM balance_history 
            WHERE timestamp >= datetime('now', '-{} days')
            ORDER BY timestamp DESC
        '''.format(days)
        
        result = self._execute_query(query)
        self._set_cached_data(cache_key, result, ttl=300)  # 5분 캐시
        return result