"""
Base DAO Class
모든 DAO 클래스의 기본 클래스
"""

import sqlite3
import threading
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

try:
    import redis
except ImportError:
    redis = None


class BaseDAO:
    """데이터베이스 접근을 위한 기본 DAO 클래스"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_redis()
    
    def _init_redis(self):
        """Redis 캐시 초기화"""
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
                self.logger.info("Redis 캐시 연결 성공")
            else:
                raise ImportError("Redis not available")
        except (ConnectionError, ImportError, Exception) as e:
            self.redis_enabled = False
            self.logger.warning(f"Redis 비활성화: {e}")
            # TTL 캐시로 폴백
            from cachetools import TTLCache
            self._memory_cache = TTLCache(maxsize=1000, ttl=300)  # 5분 TTL
    
    @contextmanager
    def _get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        with self._lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Database error: {e}")
                raise
            finally:
                conn.close()
    
    def _execute_query(self, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = True) -> Optional[Union[Dict, List[Dict]]]:
        """쿼리 실행 헬퍼 메서드"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                if fetch_one:
                    result = cursor.fetchone()
                    return dict(result) if result else None
                elif fetch_all:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                else:
                    return cursor.rowcount
                    
        except sqlite3.Error as e:
            self.logger.error(f"Query execution failed: {query} - Error: {e}")
            raise
    
    def _execute_insert(self, query: str, params: tuple = ()) -> Optional[int]:
        """INSERT 쿼리 실행 및 ID 반환"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.lastrowid
        except sqlite3.Error as e:
            self.logger.error(f"Insert failed: {query} - Error: {e}")
            raise
    
    def _execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """배치 INSERT/UPDATE 실행"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                return cursor.rowcount
        except sqlite3.Error as e:
            self.logger.error(f"Batch execution failed: {query} - Error: {e}")
            raise
    
    def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        try:
            if self.redis_enabled:
                data = self.redis_client.get(cache_key)
                if data:
                    import json
                    return json.loads(data)
            else:
                return self._memory_cache.get(cache_key)
        except Exception as e:
            self.logger.debug(f"Cache get failed: {e}")
        return None
    
    def _set_cached_data(self, cache_key: str, data: Any, ttl: int = 300):
        """캐시에 데이터 저장"""
        try:
            if self.redis_enabled:
                import json
                self.redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
            else:
                self._memory_cache[cache_key] = data
        except Exception as e:
            self.logger.debug(f"Cache set failed: {e}")
    
    def _clear_cache_pattern(self, pattern: str):
        """패턴에 맞는 캐시 키들 삭제"""
        try:
            if self.redis_enabled:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            else:
                # 메모리 캐시는 패턴 매칭 불가능, 전체 클리어
                self._memory_cache.clear()
        except Exception as e:
            self.logger.debug(f"Cache clear failed: {e}")
    
    def _validate_required_fields(self, data: Dict[str, Any], required_fields: List[str]) -> bool:
        """필수 필드 검증"""
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        return True
    
    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """데이터 정제 (SQL 인젝션 방지 등)"""
        sanitized = {}
        for key, value in data.items():
            # 기본적인 타입 검증 및 변환
            if isinstance(value, str):
                # SQL 인젝션 방지를 위한 기본 검증
                if any(dangerous in value.lower() for dangerous in ['drop table', 'delete from', '--', ';']):
                    raise ValueError(f"Potentially dangerous input detected in field: {key}")
                sanitized[key] = value.strip()
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            elif value is None:
                sanitized[key] = None
            else:
                # 다른 타입은 문자열로 변환
                sanitized[key] = str(value)
        
        return sanitized
    
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """테이블 스키마 정보 조회"""
        query = f"PRAGMA table_info({table_name})"
        return self._execute_query(query)
    
    def get_table_count(self, table_name: str, condition: str = "", params: tuple = ()) -> int:
        """테이블 레코드 수 조회"""
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        if condition:
            query += f" WHERE {condition}"
        
        result = self._execute_query(query, params, fetch_one=True)
        return result['count'] if result else 0