"""
System DAO
시스템 관련 데이터베이스 접근 객체
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base_dao import BaseDAO


class SystemDAO(BaseDAO):
    """시스템 관련 데이터베이스 접근 객체"""
    
    def __init__(self, db_path: str):
        super().__init__(db_path)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """시스템 관련 테이블 생성"""
        tables = {
            'system_events': '''
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    severity TEXT DEFAULT 'INFO',
                    is_resolved BOOLEAN DEFAULT 0,
                    resolved_at DATETIME
                )
            ''',
            'system_metrics': '''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    unit TEXT DEFAULT '',
                    component TEXT DEFAULT 'system',
                    tags TEXT DEFAULT '{}'
                )
            ''',
            'api_calls': '''
                CREATE TABLE IF NOT EXISTS api_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    api_name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT DEFAULT 'GET',
                    response_code INTEGER,
                    response_time REAL,
                    request_size INTEGER DEFAULT 0,
                    response_size INTEGER DEFAULT 0,
                    is_success BOOLEAN DEFAULT 1,
                    error_message TEXT
                )
            ''',
            'config_changes': '''
                CREATE TABLE IF NOT EXISTS config_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    config_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT NOT NULL,
                    changed_by TEXT DEFAULT 'system',
                    reason TEXT
                )
            '''
        }
        
        for table_name, create_sql in tables.items():
            self._execute_query(create_sql, fetch_all=False)
    
    def log_system_event(self, event_type: str, component: str, message: str, 
                        details: Dict[str, Any] = None, severity: str = 'INFO') -> int:
        """시스템 이벤트 로깅"""
        import json
        
        sanitized_details = json.dumps(details) if details else None
        
        query = '''
            INSERT INTO system_events (
                event_type, component, message, details, severity
            ) VALUES (?, ?, ?, ?, ?)
        '''
        
        params = (event_type, component, message, sanitized_details, severity)
        
        return self._execute_insert(query, params)
    
    def log_event(self, event_type: str, component: str, message: str, 
                  details: Dict[str, Any] = None, severity: str = 'INFO') -> int:
        """
        호환성을 위한 log_event 메서드 (log_system_event의 별칭)
        """
        return self.log_system_event(event_type, component, message, details, severity)
    
    def get_system_events(self, component: str = None, severity: str = None, 
                         hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """시스템 이벤트 조회"""
        cache_key = f"system_events:{component or 'all'}:{severity or 'all'}:hours:{hours}:limit:{limit}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        conditions = ["timestamp >= datetime('now', '-{} hours')".format(hours)]
        params = []
        
        if component:
            conditions.append("component = ?")
            params.append(component)
        
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        
        query = f'''
            SELECT * FROM system_events 
            WHERE {' AND '.join(conditions)}
            ORDER BY timestamp DESC 
            LIMIT ?
        '''
        params.append(limit)
        
        result = self._execute_query(query, tuple(params))
        self._set_cached_data(cache_key, result, ttl=300)  # 5분 캐시
        return result
    
    def resolve_system_event(self, event_id: int) -> bool:
        """시스템 이벤트 해결 표시"""
        query = '''
            UPDATE system_events 
            SET is_resolved = 1, resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        '''
        
        result = self._execute_query(query, (event_id,), fetch_all=False)
        
        # 캐시 무효화
        self._clear_cache_pattern("system_events:*")
        
        return result > 0
    
    def record_metric(self, metric_name: str, metric_value: float, 
                     unit: str = '', component: str = 'system', tags: Dict[str, Any] = None) -> int:
        """시스템 메트릭 기록"""
        import json
        
        sanitized_tags = json.dumps(tags) if tags else '{}'
        
        query = '''
            INSERT INTO system_metrics (
                metric_name, metric_value, unit, component, tags
            ) VALUES (?, ?, ?, ?, ?)
        '''
        
        params = (metric_name, metric_value, unit, component, sanitized_tags)
        
        return self._execute_insert(query, params)
    
    def get_metrics(self, metric_name: str = None, component: str = None, 
                   hours: int = 24, limit: int = 1000) -> List[Dict[str, Any]]:
        """시스템 메트릭 조회"""
        cache_key = f"metrics:{metric_name or 'all'}:{component or 'all'}:hours:{hours}:limit:{limit}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        conditions = ["timestamp >= datetime('now', '-{} hours')".format(hours)]
        params = []
        
        if metric_name:
            conditions.append("metric_name = ?")
            params.append(metric_name)
        
        if component:
            conditions.append("component = ?")
            params.append(component)
        
        query = f'''
            SELECT * FROM system_metrics 
            WHERE {' AND '.join(conditions)}
            ORDER BY timestamp DESC 
            LIMIT ?
        '''
        params.append(limit)
        
        result = self._execute_query(query, tuple(params))
        self._set_cached_data(cache_key, result, ttl=600)  # 10분 캐시
        return result
    
    def get_metric_stats(self, metric_name: str, component: str = None, hours: int = 24) -> Dict[str, Any]:
        """메트릭 통계 조회"""
        cache_key = f"metric_stats:{metric_name}:{component or 'all'}:hours:{hours}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        conditions = [
            "metric_name = ?",
            "timestamp >= datetime('now', '-{} hours')".format(hours)
        ]
        params = [metric_name]
        
        if component:
            conditions.append("component = ?")
            params.append(component)
        
        query = f'''
            SELECT 
                COUNT(*) as sample_count,
                AVG(metric_value) as avg_value,
                MIN(metric_value) as min_value,
                MAX(metric_value) as max_value,
                (SELECT metric_value FROM system_metrics 
                 WHERE {' AND '.join(conditions)} 
                 ORDER BY timestamp DESC LIMIT 1) as latest_value
            FROM system_metrics 
            WHERE {' AND '.join(conditions)}
        '''
        
        result = self._execute_query(query, tuple(params), fetch_one=True)
        
        if result:
            stats = {
                'metric_name': metric_name,
                'sample_count': result['sample_count'] or 0,
                'avg_value': result['avg_value'] or 0.0,
                'min_value': result['min_value'] or 0.0,
                'max_value': result['max_value'] or 0.0,
                'latest_value': result['latest_value'] or 0.0
            }
        else:
            stats = {
                'metric_name': metric_name,
                'sample_count': 0,
                'avg_value': 0.0,
                'min_value': 0.0,
                'max_value': 0.0,
                'latest_value': 0.0
            }
        
        self._set_cached_data(cache_key, stats, ttl=900)  # 15분 캐시
        return stats
    
    def log_api_call(self, api_name: str, endpoint: str, method: str = 'GET',
                    response_code: int = None, response_time: float = None,
                    request_size: int = 0, response_size: int = 0,
                    is_success: bool = True, error_message: str = None) -> int:
        """API 호출 로깅"""
        query = '''
            INSERT INTO api_calls (
                api_name, endpoint, method, response_code, response_time,
                request_size, response_size, is_success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            api_name, endpoint, method, response_code, response_time,
            request_size, response_size, is_success, error_message
        )
        
        return self._execute_insert(query, params)
    
    def get_api_stats(self, api_name: str = None, hours: int = 24) -> Dict[str, Any]:
        """API 통계 조회"""
        cache_key = f"api_stats:{api_name or 'all'}:hours:{hours}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        if api_name:
            query = '''
                SELECT 
                    COUNT(*) as total_calls,
                    COUNT(CASE WHEN is_success = 1 THEN 1 END) as successful_calls,
                    COUNT(CASE WHEN is_success = 0 THEN 1 END) as failed_calls,
                    AVG(response_time) as avg_response_time,
                    MIN(response_time) as min_response_time,
                    MAX(response_time) as max_response_time,
                    SUM(request_size + response_size) as total_bytes
                FROM api_calls 
                WHERE api_name = ? AND timestamp >= datetime('now', '-{} hours')
            '''.format(hours)
            params = (api_name,)
        else:
            query = '''
                SELECT 
                    COUNT(*) as total_calls,
                    COUNT(CASE WHEN is_success = 1 THEN 1 END) as successful_calls,
                    COUNT(CASE WHEN is_success = 0 THEN 1 END) as failed_calls,
                    AVG(response_time) as avg_response_time,
                    MIN(response_time) as min_response_time,
                    MAX(response_time) as max_response_time,
                    SUM(request_size + response_size) as total_bytes
                FROM api_calls 
                WHERE timestamp >= datetime('now', '-{} hours')
            '''.format(hours)
            params = ()
        
        result = self._execute_query(query, params, fetch_one=True)
        
        if result:
            stats = {
                'api_name': api_name or 'all',
                'total_calls': result['total_calls'] or 0,
                'successful_calls': result['successful_calls'] or 0,
                'failed_calls': result['failed_calls'] or 0,
                'success_rate': (result['successful_calls'] or 0) / max(result['total_calls'] or 1, 1),
                'avg_response_time': result['avg_response_time'] or 0.0,
                'min_response_time': result['min_response_time'] or 0.0,
                'max_response_time': result['max_response_time'] or 0.0,
                'total_bytes': result['total_bytes'] or 0
            }
        else:
            stats = {
                'api_name': api_name or 'all',
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'success_rate': 0.0,
                'avg_response_time': 0.0,
                'min_response_time': 0.0,
                'max_response_time': 0.0,
                'total_bytes': 0
            }
        
        self._set_cached_data(cache_key, stats, ttl=900)  # 15분 캐시
        return stats
    
    def log_config_change(self, config_key: str, old_value: str, new_value: str,
                         changed_by: str = 'system', reason: str = None) -> int:
        """설정 변경 로깅"""
        query = '''
            INSERT INTO config_changes (
                config_key, old_value, new_value, changed_by, reason
            ) VALUES (?, ?, ?, ?, ?)
        '''
        
        params = (config_key, old_value, new_value, changed_by, reason)
        
        return self._execute_insert(query, params)
    
    def get_config_history(self, config_key: str = None, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """설정 변경 히스토리 조회"""
        cache_key = f"config_history:{config_key or 'all'}:days:{days}:limit:{limit}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        if config_key:
            query = '''
                SELECT * FROM config_changes 
                WHERE config_key = ? AND timestamp >= datetime('now', '-{} days')
                ORDER BY timestamp DESC 
                LIMIT ?
            '''.format(days)
            params = (config_key, limit)
        else:
            query = '''
                SELECT * FROM config_changes 
                WHERE timestamp >= datetime('now', '-{} days')
                ORDER BY timestamp DESC 
                LIMIT ?
            '''.format(days)
            params = (limit,)
        
        result = self._execute_query(query, params)
        self._set_cached_data(cache_key, result, ttl=1800)  # 30분 캐시
        return result
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """오래된 데이터 정리"""
        cleanup_queries = {
            'system_events': f'''
                DELETE FROM system_events 
                WHERE timestamp < datetime('now', '-{days_to_keep} days')
                AND is_resolved = 1
            ''',
            'system_metrics': f'''
                DELETE FROM system_metrics 
                WHERE timestamp < datetime('now', '-{days_to_keep} days')
            ''',
            'api_calls': f'''
                DELETE FROM api_calls 
                WHERE timestamp < datetime('now', '-{days_to_keep} days')
            ''',
            'config_changes': f'''
                DELETE FROM config_changes 
                WHERE timestamp < datetime('now', '-{days_to_keep * 2} days')
            '''  # 설정 변경은 더 오래 보관
        }
        
        cleanup_results = {}
        for table_name, query in cleanup_queries.items():
            try:
                result = self._execute_query(query, fetch_all=False)
                cleanup_results[table_name] = result
                self.logger.info(f"Cleaned up {result} records from {table_name}")
            except Exception as e:
                self.logger.error(f"Failed to cleanup {table_name}: {e}")
                cleanup_results[table_name] = 0
        
        # 캐시 전체 무효화
        self._clear_cache_pattern("*")
        
        return cleanup_results