"""
재시도 로직 유틸리티
API 호출 및 네트워크 작업에 대한 지수적 백오프 재시도 시스템
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, Optional


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2, max_wait: float = 60):
    """
    지수적 백오프를 적용한 재시도 데코레이터
    
    Args:
        max_retries: 최대 재시도 횟수
        backoff_factor: 백오프 지수 (2^attempt * backoff_factor)
        max_wait: 최대 대기 시간 (초)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(func.__module__)
            
            for attempt in range(max_retries):
                try:
                    logger.debug(f"🔄 {func.__name__} 호출 시도 {attempt + 1}/{max_retries}")
                    result = await func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"✅ {func.__name__} 재시도 성공 (시도 {attempt + 1})")
                    
                    return result
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"❌ {func.__name__} 최종 실패 ({max_retries}회 시도): {e}")
                        raise e
                    
                    wait_time = min(backoff_factor ** attempt, max_wait)
                    logger.warning(f"⚠️ {func.__name__} 실패 (시도 {attempt + 1}), {wait_time:.1f}초 대기 후 재시도: {e}")
                    
                    await asyncio.sleep(wait_time)
            
            return None
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            logger = logging.getLogger(func.__module__)
            
            for attempt in range(max_retries):
                try:
                    logger.debug(f"🔄 {func.__name__} 호출 시도 {attempt + 1}/{max_retries}")
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"✅ {func.__name__} 재시도 성공 (시도 {attempt + 1})")
                    
                    return result
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"❌ {func.__name__} 최종 실패 ({max_retries}회 시도): {e}")
                        raise e
                    
                    wait_time = min(backoff_factor ** attempt, max_wait)
                    logger.warning(f"⚠️ {func.__name__} 실패 (시도 {attempt + 1}), {wait_time:.1f}초 대기 후 재시도: {e}")
                    
                    time.sleep(wait_time)
            
            return None
        
        # async 함수인지 확인하여 적절한 래퍼 반환
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RetryHandler:
    """재시도 로직 유틸리티 클래스"""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = logging.getLogger(__name__)
    
    async def execute_with_retry(self, func: Callable, *args, default_value: Any = None, **kwargs) -> Any:
        """
        함수를 재시도 로직과 함께 실행
        
        Args:
            func: 실행할 함수
            *args: 함수 인자
            default_value: 실패 시 반환할 기본값
            **kwargs: 함수 키워드 인자
            
        Returns:
            성공 시 함수 결과, 실패 시 default_value
        """
        for attempt in range(self.max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"✅ {func.__name__} 재시도 성공 (시도 {attempt + 1})")
                
                return result
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    self.logger.error(f"❌ {func.__name__} 최종 실패: {e}")
                    return default_value
                
                wait_time = min(self.backoff_factor ** attempt, 30)
                self.logger.warning(f"⚠️ {func.__name__} 재시도 {attempt + 1}/{self.max_retries} 실패, {wait_time:.1f}초 대기: {e}")
                
                await asyncio.sleep(wait_time)
        
        return default_value
    
    def get_safe_balance_handler(self):
        """get_balance 전용 안전 핸들러"""
        @retry_with_backoff(max_retries=self.max_retries, backoff_factor=self.backoff_factor)
        async def safe_get_balance(api_client):
            """API 클라이언트의 get_balance를 안전하게 호출"""
            try:
                balance = await api_client.get_balance()
                self.logger.debug(f"💰 잔액 조회 성공: {balance}")
                return balance
            except Exception as e:
                self.logger.error(f"❌ 잔액 조회 오류: {e}")
                # 기본 안전 잔액 반환
                return {
                    'total': 0.0,
                    'available': 0.0,
                    'used': 0.0,
                    'currency': 'USDT',
                    'error': str(e),
                    'is_fallback': True
                }
        
        return safe_get_balance
    
    def get_performance_stats(self) -> dict:
        """재시도 성능 통계 반환"""
        return {
            'max_retries': self.max_retries,
            'backoff_factor': self.backoff_factor,
            'initialized_at': getattr(self, '_init_time', time.time())
        }